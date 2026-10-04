"""Patient management endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_admin_or_doctor
from app.models import User
from app.schemas import (
    MessageResponse,
    PatientCreate,
    PatientPage,
    PatientResponse,
    PatientUpdate,
)
from app.services import patient_service

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a patient (admin only)",
    description=(
        "Creates a patient. `age` must be greater than 0 and `phone` must be "
        "10-15 digits."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        422: {"description": "Invalid age or phone"},
    },
)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PatientResponse:
    """Create a patient."""
    patient = patient_service.create_patient(db, payload)
    return patient_service.serialize_patient(patient)


@router.get(
    "",
    response_model=PatientPage,
    summary="List patients",
    description=(
        "Admins receive every patient. A doctor only receives the patients "
        "assigned to them."
    ),
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Access denied"}},
)
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_doctor),
) -> PatientPage:
    """List patients scoped to the caller's role."""
    doctor = patient_service.resolve_doctor_scope(db, current_user)
    patients, meta = patient_service.get_patients(db, doctor=doctor, page=page, page_size=page_size)
    return PatientPage(items=[patient_service.serialize_patient(p) for p in patients], meta=meta)


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient details",
    description=(
        "Admins may read any patient. A doctor may read a patient only when that "
        "patient is assigned to them, otherwise 403 is returned."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Patient not assigned to you"},
        404: {"description": "Patient not found"},
    },
)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_doctor),
) -> PatientResponse:
    """Return one patient by id."""
    doctor = patient_service.resolve_doctor_scope(db, current_user)
    patient = patient_service.authorize_patient_access(db, current_user, patient_id, doctor)
    return patient_service.serialize_patient(patient)


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update a patient (admin only)",
    description="Partial update of name, age or phone.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "Patient not found"},
    },
)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PatientResponse:
    """Update a patient."""
    patient = patient_service.update_patient(db, patient_id, payload)
    return patient_service.serialize_patient(patient)


@router.delete(
    "/{patient_id}",
    response_model=MessageResponse,
    summary="Delete a patient (admin only)",
    description="Physically removes the patient and its assignment links.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "Patient not found"},
    },
)
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    """Delete a patient record."""
    patient = patient_service.get_patient_or_404(db, patient_id)
    db.delete(patient)
    db.commit()
    return MessageResponse(message=f"Patient {patient_id} deleted successfully")