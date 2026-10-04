"""User account service: registration, authentication and doctor linking."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.auth import hash_password, verify_password
from app.models import Doctor, User, UserRole
from app.schemas import UserRegister

# Specialization used when a doctor account is created through /auth/register
# without going through POST /doctors first.
DEFAULT_SPECIALIZATION = "General Medicine"


def get_user_by_email(db: Session, email: str) -> User | None:
    """Case-insensitive lookup by email."""
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, payload: UserRegister) -> User:
    """Register a new user, hashing the password and validating uniqueness.

    Doctor accounts are linked to a ``doctors`` row (reusing an existing one
    with the same email when present) so they can access their assigned
    patients.
    """
    email = payload.email.strip().lower()
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    user = User(
        name=payload.name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    if user.role == UserRole.DOCTOR:
        _ensure_doctor_profile(db, user)

    db.commit()
    db.refresh(user)
    return user


def _ensure_doctor_profile(db: Session, user: User) -> None:
    """Attach the doctor account to a doctor record."""
    doctor = db.scalar(select(Doctor).where(func.lower(Doctor.email) == user.email))
    if doctor is None:
        doctor = Doctor(
            name=user.name,
            specialization=DEFAULT_SPECIALIZATION,
            email=user.email,
            is_active=True,
        )
        db.add(doctor)
        db.flush()
    doctor.user_id = user.id
    db.flush()


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the active user."""
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )
    return user