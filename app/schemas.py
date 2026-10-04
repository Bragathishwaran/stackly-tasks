"""Pydantic schemas for request validation and response serialization."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import UserRole

PHONE_PATTERN = re.compile(r"^\d{10,15}$")


def validate_phone(value: str) -> str:
    """Ensure a phone number contains only 10-15 digits."""
    if not isinstance(value, str) or not PHONE_PATTERN.match(value.strip()):
        raise ValueError("phone must contain only digits and be between 10 and 15 characters long")
    return value.strip()


# ---------------------------------------------------------------- messages ---
class MessageResponse(BaseModel):
    message: str


# ------------------------------------------------------------------- auth ---
class UserRegister(BaseModel):
    """Payload used to create a new account."""

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.DOCTOR

    @field_validator("password")
    @classmethod
    def _password_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("password must not be blank")
        return value

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class UserLogin(BaseModel):
    """OAuth2-style credentials payload."""

    email: EmailStr
    password: str = Field(min_length=1)


class Token(BaseModel):
    """Issued JWT."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public representation of an account (never includes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime


# --------------------------------------------------------------- pagination ---
class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


class DoctorPage(BaseModel):
    items: list["DoctorResponse"]
    meta: PageMeta


class PatientPage(BaseModel):
    items: list["PatientResponse"]
    meta: PageMeta


# ---------------------------------------------------------------- doctors ---
class DoctorBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    specialization: str = Field(min_length=2, max_length=120)
    email: EmailStr

    @field_validator("name", "specialization")
    @classmethod
    def _strip_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class DoctorCreate(DoctorBase):
    """Admin payload to create a doctor."""

    user_id: Optional[int] = Field(default=None, ge=1)


class DoctorUpdate(BaseModel):
    """Partial update; unset fields are left untouched."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    specialization: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

    @field_validator("name", "specialization")
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class DoctorResponse(BaseModel):
    """Doctor as exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialization: str
    email: EmailStr
    is_active: bool
    user_id: Optional[int] = None


# --------------------------------------------------------------- patients ---
class PatientCreate(BaseModel):
    """Admin payload to create a patient."""

    name: str = Field(min_length=2, max_length=120)
    age: Annotated[int, Field(gt=0, le=130)]
    phone: str = Field(min_length=10, max_length=15)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return validate_phone(value)


class PatientUpdate(BaseModel):
    """Partial patient update."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    age: Optional[Annotated[int, Field(gt=0, le=130)]] = None
    phone: Optional[str] = Field(default=None, min_length=10, max_length=15)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_phone(value)


class PatientResponse(BaseModel):
    """Patient as exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    phone: str
    created_at: datetime
    doctor_ids: list[int] = Field(default_factory=list)


# ------------------------------------------------------------- assignment ---
class AssignmentCreate(BaseModel):
    doctor_id: Annotated[int, Field(gt=0)]
    patient_id: Annotated[int, Field(gt=0)]


class AssignmentResponse(BaseModel):
    """Confirmation payload returned after an assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int


DoctorPage.model_rebuild()
PatientPage.model_rebuild()