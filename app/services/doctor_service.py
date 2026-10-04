"""CRUD and business logic for doctors and doctor-patient assignments."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Doctor, DoctorPatient, Patient, User, UserRole
from app.schemas import DoctorCreate, DoctorUpdate, PageMeta


def get_doctor_by_email(db: Session, email: str) -> Doctor | None:
    return db.scalar(select(Doctor).where(func.lower(Doctor.email) == email.strip().lower()))


def get_doctor(db: Session, doctor_id: int, include_inactive: bool = True) -> Doctor | None:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        return None
    if not include_inactive and not doctor.is_active:
        return None
    return doctor


def get_doctor_or_404(db: Session, doctor_id: int) -> Doctor:
    doctor = get_doctor(db, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor


def get_active_doctor_or_404(db: Session, doctor_id: int) -> Doctor:
    doctor = get_doctor(db, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is inactive"
        )
    return doctor


def create_doctor(db: Session, payload: DoctorCreate) -> Doctor:
    """Create a doctor record, optionally linking an existing doctor account."""
    email = payload.email.strip().lower()
    if get_doctor_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Doctor email already exists"
        )

    user = db.get(User, payload.user_id) if payload.user_id else None
    if payload.user_id and user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Linked user not found"
        )

    doctor = Doctor(
        name=payload.name,
        specialization=payload.specialization,
        email=email,
        is_active=True,
        user_id=user.id if user else None,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def get_doctors(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    specialization: str | None = None,
    include_inactive: bool = False,
    search: str | None = None,
) -> tuple[list[Doctor], PageMeta]:
    """Return a page of doctors plus pagination metadata."""
    filters = []
    if not include_inactive:
        filters.append(Doctor.is_active.is_(True))
    if specialization:
        filters.append(func.lower(Doctor.specialization) == specialization.strip().lower())
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            func.lower(Doctor.name).like(pattern) | func.lower(Doctor.email).like(pattern)
        )

    total = db.scalar(select(func.count(Doctor.id)).where(*filters)) or 0
    rows = (
        db.scalars(
            select(Doctor)
            .where(*filters)
            .order_by(Doctor.id)
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


def update_doctor(db: Session, doctor_id: int, payload: DoctorUpdate) -> Doctor:
    """Apply a partial update to a doctor."""
    doctor = get_doctor_or_404(db, doctor_id)

    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        email = data["email"].strip().lower()
        existing = get_doctor_by_email(db, email)
        if existing and existing.id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Doctor email already exists"
            )
        data["email"] = email

    for field, value in data.items():
        setattr(doctor, field, value)

    db.commit()
    db.refresh(doctor)
    return doctor


def soft_delete_doctor(db: Session, doctor_id: int) -> Doctor:
    """Deactivate a doctor without removing the row."""
    doctor = get_doctor_or_404(db, doctor_id)
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is already inactive"
        )
    doctor.is_active = False
    if doctor.user_id:
        user = db.get(User, doctor.user_id)
        if user is not None:
            user.is_active = False
    db.commit()
    db.refresh(doctor)
    return doctor


# ------------------------------------------------------------- assignments ---
def assign_patient(db: Session, doctor_id: int, patient_id: int) -> DoctorPatient:
    """Assign a patient to a doctor, rejecting duplicates and inactive doctors."""
    get_active_doctor_or_404(db, doctor_id)

    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    duplicate = db.scalar(
        select(DoctorPatient).where(
            DoctorPatient.doctor_id == doctor_id, DoctorPatient.patient_id == patient_id
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient is already assigned to this doctor",
        )

    assignment = DoctorPatient(doctor_id=doctor_id, patient_id=patient_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_assignment_or_404(db: Session, doctor_id: int, patient_id: int) -> DoctorPatient:
    assignment = db.scalar(
        select(DoctorPatient).where(
            DoctorPatient.doctor_id == doctor_id, DoctorPatient.patient_id == patient_id
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient is not assigned to this doctor",
        )
    return assignment


def remove_assignment(db: Session, doctor_id: int, patient_id: int) -> None:
    assignment = get_assignment_or_404(db, doctor_id, patient_id)
    db.delete(assignment)
    db.commit()


def get_doctor_patients(
    db: Session, doctor_id: int, page: int = 1, page_size: int = 10
) -> tuple[list[Patient], PageMeta]:
    """Return the patients assigned to a doctor."""
    filters = [DoctorPatient.doctor_id == doctor_id]
    total = db.scalar(select(func.count(Patient.id)).join(DoctorPatient, Patient.id == DoctorPatient.patient_id).where(*filters)) or 0
    rows = (
        db.scalars(
            select(Patient)
            .join(DoctorPatient, Patient.id == DoctorPatient.patient_id)
            .where(*filters)
            .options(selectinload(Patient.doctors))
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


def get_doctor_for_user(db: Session, user: User) -> Doctor | None:
    """Resolve the doctor profile that belongs to a logged-in doctor account."""
    if user.role != UserRole.DOCTOR:
        return None
    return db.scalar(select(Doctor).where(Doctor.user_id == user.id))