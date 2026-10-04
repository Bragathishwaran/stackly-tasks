"""CRUD and business logic for patients."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Doctor, DoctorPatient, Patient, User, UserRole
from app.schemas import PageMeta, PatientCreate, PatientResponse, PatientUpdate


def get_patient(db: Session, patient_id: int) -> Patient | None:
    return db.get(Patient, patient_id)


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    """Create a patient record."""
    patient = Patient(name=payload.name, age=payload.age, phone=payload.phone)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(db: Session, patient_id: int, payload: PatientUpdate) -> Patient:
    patient = get_patient_or_404(db, patient_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


def serialize_patient(patient: Patient) -> PatientResponse:
    """Build the API representation, including the assigned doctor ids."""
    return PatientResponse(
        id=patient.id,
        name=patient.name,
        age=patient.age,
        phone=patient.phone,
        created_at=patient.created_at,
        doctor_ids=sorted(doctor.id for doctor in patient.doctors),
    )


def get_patients(
    db: Session,
    doctor: Doctor | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Patient], PageMeta]:
    """List patients.

    When ``doctor`` is given only that doctor's patients are returned, which is
    how the doctor role is prevented from seeing the whole patient list.
    """
    if doctor is None:
        query = select(Patient)
        count_query = select(func.count(Patient.id))
    else:
        query = select(Patient).join(
            DoctorPatient, Patient.id == DoctorPatient.patient_id
        ).where(DoctorPatient.doctor_id == doctor.id)
        count_query = (
            select(func.count(Patient.id))
            .select_from(DoctorPatient)
            .join(Patient, Patient.id == DoctorPatient.patient_id)
            .where(DoctorPatient.doctor_id == doctor.id)
        )

    total = db.scalar(count_query) or 0
    rows = (
        db.scalars(
            query.options(selectinload(Patient.doctors))
            .order_by(Patient.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )
    meta = PageMeta(
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
    )
    return list(rows), meta


def resolve_doctor_scope(db: Session, user: User) -> Doctor | None:
    """Return the doctor profile scoping this user's patient visibility.

    Admins get ``None`` (no restriction). A doctor account without a linked
    ``doctors`` row is rejected with 403 so it can never fall back to the
    unrestricted listing.
    """
    if user.role == UserRole.ADMIN:
        return None

    doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a doctor profile",
        )
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Doctor profile is inactive"
        )
    return doctor


def patient_is_assigned_to_doctor(db: Session, patient_id: int, doctor_id: int) -> bool:
    return (
        db.scalar(
            select(DoctorPatient.id).where(
                DoctorPatient.doctor_id == doctor_id,
                DoctorPatient.patient_id == patient_id,
            )
        )
        is not None
    )


def authorize_patient_access(
    db: Session, user: User, patient_id: int, doctor: Doctor | None = None
) -> Patient:
    """Return the patient if the user may access it, otherwise raise 403/404."""
    patient = get_patient_or_404(db, patient_id)

    if user.role == UserRole.ADMIN:
        return patient

    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a doctor profile",
        )

    if not patient_is_assigned_to_doctor(db, patient.id, doctor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this patient",
        )
    return patient