import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


PHONE_REGEX = r"^[0-9]{10}$"


class DoctorSummary(BaseModel):
    id: int = Field(..., json_schema_extra={"example": 1})
    name: str = Field(..., json_schema_extra={"example": "Dr. Gregory House"})
    specialization: str = Field(..., json_schema_extra={"example": "Diagnostics"})
    email: str = Field(..., json_schema_extra={"example": "doctor@example.com"})

    model_config = ConfigDict(from_attributes=True)


class PatientBase(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Full name of the patient",
        json_schema_extra={"example": "Jane Doe"},
    )
    age: int = Field(
        ...,
        gt=0,
        le=130,
        description="Age of patient in years (1 - 130)",
        json_schema_extra={"example": 32},
    )
    phone: str = Field(
        ...,
        description="Phone number containing exactly 10 numeric digits",
        json_schema_extra={"example": "9876543210"},
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.match(PHONE_REGEX, cleaned):
            raise ValueError("Phone number must contain exactly 10 digits and only numeric values")
        return cleaned


class PatientCreate(PatientBase):
    doctor_id: Optional[int] = Field(
        None,
        description="Optional assigned doctor ID. If omitted by a doctor, automatically assigned to themselves.",
        json_schema_extra={"example": 1},
    )


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=150,
        description="Updated patient name",
        json_schema_extra={"example": "Jane Doe-Smith"},
    )
    age: Optional[int] = Field(
        None,
        gt=0,
        le=130,
        description="Updated age",
        json_schema_extra={"example": 33},
    )
    phone: Optional[str] = Field(
        None,
        description="Updated 10-digit phone number",
        json_schema_extra={"example": "9876543211"},
    )
    doctor_id: Optional[int] = Field(
        None,
        description="Updated primary assigned doctor ID",
        json_schema_extra={"example": 2},
    )
    is_active: Optional[bool] = Field(
        None,
        description="Active status of the patient record",
        json_schema_extra={"example": True},
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip()
        if not re.match(PHONE_REGEX, cleaned):
            raise ValueError("Phone number must contain exactly 10 digits and only numeric values")
        return cleaned


class PatientResponse(PatientBase):
    id: int = Field(..., description="Unique patient identifier", json_schema_extra={"example": 10})
    doctor_id: Optional[int] = Field(None, description="Primary doctor ID", json_schema_extra={"example": 1})
    is_active: bool = Field(..., description="Active status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User who created the patient")
    updated_by: Optional[str] = Field(None, description="User who last updated the patient")

    model_config = ConfigDict(from_attributes=True)


class PatientDetailResponse(PatientResponse):
    doctor: Optional[DoctorSummary] = Field(None, description="Primary assigned doctor details")
    doctors: List[DoctorSummary] = Field(default_factory=list, description="All assigned doctors")

    model_config = ConfigDict(from_attributes=True)
