"""SQLAlchemy ORM models: users, doctors, patients and doctor-patient links."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    """Roles a user account can hold."""

    ADMIN = "admin"
    DOCTOR = "doctor"


class User(Base):
    """An account able to authenticate against the API."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        default=UserRole.DOCTOR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    doctor_profile: Mapped["Doctor | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


class Doctor(Base):
    """A doctor record, optionally linked to a login account."""

    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialization: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    user: Mapped["User | None"] = relationship(back_populates="doctor_profile")
    assignments: Mapped[list["DoctorPatient"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan", overlaps="patients,doctors"
    )
    patients: Mapped[list["Patient"]] = relationship(
        secondary="doctor_patients", back_populates="doctors", viewonly=True
    )


class Patient(Base):
    """A patient that may be assigned to one or more doctors."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (CheckConstraint("age > 0", name="ck_patients_age_positive"),)

    assignments: Mapped[list["DoctorPatient"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", overlaps="doctors,patients"
    )
    doctors: Mapped[list["Doctor"]] = relationship(
        secondary="doctor_patients", back_populates="patients", viewonly=True
    )


class DoctorPatient(Base):
    """Association row linking a doctor to a patient."""

    __tablename__ = "doctor_patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("doctor_id", "patient_id", name="uq_doctor_patient"),
    )

    doctor: Mapped["Doctor"] = relationship(back_populates="assignments")
    patient: Mapped["Patient"] = relationship(back_populates="assignments")