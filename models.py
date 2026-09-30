"""Request models (input schemas).

These Pydantic models describe the JSON body a client sends to the API.
FastAPI uses them to validate input *before* the endpoint function runs,
and returns a 422 Unprocessable Entity response automatically if the
data is invalid.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


def _reject_blank(value: str) -> str:
    """Make sure a text field is not empty (or only whitespace)."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned


class DoctorCreate(BaseModel):
    """Body accepted by POST /doctors."""

    name: str = Field(
        ...,
        min_length=1,
        description="Full name of the doctor",
        examples=["Dr. Ada Lovelace"],
    )
    specialization: str = Field(
        ...,
        min_length=1,
        description="Area of expertise",
        examples=["Cardiology"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address",
        examples=["ada.lovelace@example.com"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the doctor is currently taking appointments",
    )

    _clean_name = field_validator("name")(_reject_blank)
    _clean_specialization = field_validator("specialization")(_reject_blank)


class PatientCreate(BaseModel):
    """Body accepted by POST /patients."""

    name: str = Field(
        ...,
        min_length=1,
        description="Full name of the patient",
        examples=["Grace Hopper"],
    )
    age: int = Field(
        ...,
        gt=0,
        le=120,
        description="Age in years, must be greater than 0",
        examples=[36],
    )
    phone: str = Field(
        ...,
        min_length=1,
        description="Contact phone number",
        examples=["+1-555-0100"],
    )

    _clean_name = field_validator("name")(_reject_blank)
    _clean_phone = field_validator("phone")(_reject_blank)