"""Reusable FastAPI dependencies: authentication and role-based authorization."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.database import get_db
from app.models import Doctor, User, UserRole


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow only admin accounts."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


def require_doctor(current_user: User = Depends(get_current_user)) -> User:
    """Allow only accounts holding the doctor role."""
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Doctor role required"
        )
    return current_user


def require_admin_or_doctor(current_user: User = Depends(get_current_user)) -> User:
    """Allow any authenticated account (both roles are covered today)."""
    if current_user.role not in (UserRole.ADMIN, UserRole.DOCTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role"
        )
    return current_user


def get_current_doctor(
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
) -> Doctor:
    """Return the doctor profile bound to the logged-in doctor account.

    A doctor account without a linked ``doctors`` row cannot access any
    patient data, so a 403 is raised in that case.
    """
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id)
        .one_or_none()
    )
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No doctor profile is linked to this account",
        )
    return doctor


def ensure_doctor_access(current_user: User, doctor_id: int, db: Session) -> Doctor:
    """Authorize access to a doctor's patient list.

    Admins may access any doctor; a doctor may only access their own profile.
    Missing or mismatched identities are reported as 403 without leaking
    whether the other doctor exists.
    """
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )
    if current_user.role == UserRole.ADMIN:
        return doctor

    own = db.query(Doctor).filter(Doctor.user_id == current_user.id).one_or_none()
    if own is None or own.id != doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this doctor's patients",
        )
    return doctor