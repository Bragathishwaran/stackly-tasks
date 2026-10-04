"""Doctor management and doctor-patient assignment endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import ensure_doctor_access, require_admin, require_admin_or_doctor
from app.models import User
from app.schemas import (
    AssignmentResponse,
    DoctorCreate,
    DoctorPage,
    DoctorResponse,
    DoctorUpdate,
    MessageResponse,
    PatientPage,
)
from app.services import doctor_service, patient_service

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a doctor (admin only)",
    description="Registers a new doctor. Returns 409 if the email is already used.",
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Admin required"}, 409: {"description": "Email already exists"}},
)
def create_doctor(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DoctorResponse:
    """Create a doctor record."""
    return doctor_service.create_doctor(db, payload)


@router.get(
    "",
    response_model=DoctorPage,
    summary="List doctors",
    description=(
        "Paginated listing of doctors. Inactive doctors are hidden unless "
        "`include_inactive=true`. Optionally filter by `specialization` or `search`."
    ),
    responses={401: {"description": "Not authenticated"}},
)
def list_doctors(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    specialization: Optional[str] = Query(None, description="Exact specialization match"),
    search: Optional[str] = Query(None, description="Match doctor name or email"),
    include_inactive: bool = Query(False, description="Include soft-deleted doctors"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_doctor),
) -> DoctorPage:
    """Return a page of doctors."""
    doctors, meta = doctor_service.get_doctors(
        db,
        page=page,
        page_size=page_size,
        specialization=specialization,
        include_inactive=include_inactive,
        search=search,
    )
    return DoctorPage(items=[DoctorResponse.model_validate(d) for d in doctors], meta=meta)


@router.get(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Get doctor details",
    description="Returns a single doctor. 404 when the doctor does not exist.",
    responses={401: {"description": "Not authenticated"}, 404: {"description": "Doctor not found"}},
)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_doctor),
) -> DoctorResponse:
    """Return one doctor by id."""
    doctor = doctor_service.get_doctor_or_404(db, doctor_id)
    return DoctorResponse.model_validate(doctor)


@router.put(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Update a doctor (admin only)",
    description="Partial update of name, specialization, email or active state.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "Doctor not found"},
        409: {"description": "Email already exists"},
    },
)
def update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DoctorResponse:
    """Update a doctor."""
    doctor = doctor_service.update_doctor(db, doctor_id, payload)
    return DoctorResponse.model_validate(doctor)


@router.delete(
    "/{doctor_id}",
    response_model=MessageResponse,
    summary="Deactivate a doctor (admin only, soft delete)",
    description=(
        "Soft delete: sets `is_active=false` on the doctor (and its linked user "
        "account) without removing any row. Use "
        "`PUT /doctors/{doctor_id}` with `is_active=true` to restore."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "Doctor not found"},
        400: {"description": "Doctor already inactive"},
    },
)
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    """Soft delete a doctor."""
    doctor = doctor_service.soft_delete_doctor(db, doctor_id)
    return MessageResponse(message=f"Doctor {doctor.id} deactivated successfully")


# ------------------------------------------------------------- assignments ---
@router.post(
    "/{doctor_id}/patients/{patient_id}",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a patient to a doctor (admin only)",
    description=(
        "Creates the doctor-patient link. The doctor must exist and be active, the "
        "patient must exist, and the pair must not already be assigned (409)."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "Doctor or patient not found"},
        409: {"description": "Patient already assigned to this doctor"},
    },
)
def assign_patient(
    doctor_id: int,
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AssignmentResponse:
    """Assign a patient to a doctor."""
    assignment = doctor_service.assign_patient(db, doctor_id, patient_id)
    return AssignmentResponse.model_validate(assignment)


@router.get(
    "/{doctor_id}/patients",
    response_model=PatientPage,
    summary="List a doctor's patients",
    description=(
        "Admins may list any doctor's patients. A doctor may only list their own "
        "patients; requesting another doctor returns 403."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not your doctor"},
        404: {"description": "Doctor not found"},
    },
)
def list_doctor_patients(
    doctor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_doctor),
) -> PatientPage:
    """List the patients assigned to a doctor."""
    doctor = ensure_doctor_access(current_user, doctor_id, db)
    patients, meta = doctor_service.get_doctor_patients(db, doctor.id, page=page, page_size=page_size)
    return PatientPage(items=[patient_service.serialize_patient(p) for p in patients], meta=meta)


@router.delete(
    "/{doctor_id}/patients/{patient_id}",
    response_model=MessageResponse,
    summary="Unassign a patient from a doctor (admin only)",
    description="Removes the doctor-patient link. The patient record is kept.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "Doctor not found or assignment missing"},
    },
)
def unassign_patient(
    doctor_id: int,
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    """Remove a doctor-patient assignment."""
    doctor_service.remove_assignment(db, doctor_id, patient_id)
    return MessageResponse(message="Patient unassigned from doctor successfully")