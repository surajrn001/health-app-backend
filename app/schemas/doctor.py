from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class DoctorBase(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Full legal name of the doctor",
        json_schema_extra={"example": "Dr. Gregory House"},
    )
    specialization: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Medical specialization or department",
        json_schema_extra={"example": "Diagnostics & Infectious Disease"},
    )
    email: EmailStr = Field(
        ...,
        description="Unique professional email address",
        json_schema_extra={"example": "gregory.house@healthapp.com"},
    )


class DoctorCreate(DoctorBase):
    is_active: bool = Field(True, description="Active status of the doctor profile")
    password: Optional[str] = Field(
        None,
        min_length=6,
        description="Optional initial login password. Defaults to Doctor@123 if omitted.",
        json_schema_extra={"example": "DoctorSecretPass123"},
    )


class DoctorUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=150,
        description="Updated name",
        json_schema_extra={"example": "Dr. Stephen Strange"},
    )
    specialization: Optional[str] = Field(
        None,
        min_length=2,
        max_length=150,
        description="Updated specialization",
        json_schema_extra={"example": "Neuro Surgery"},
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Updated email",
        json_schema_extra={"example": "stephen.strange@healthapp.com"},
    )
    is_active: Optional[bool] = Field(
        None,
        description="Active/inactive status (Admin only)",
        json_schema_extra={"example": True},
    )


class DoctorResponse(DoctorBase):
    id: int = Field(..., description="Unique doctor identifier", json_schema_extra={"example": 1})
    is_active: bool = Field(..., description="Active status")
    user_id: Optional[int] = Field(None, description="Linked user account ID")
    created_at: Optional[datetime] = Field(None, description="Timestamp when record was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when record was last updated")
    created_by: Optional[str] = Field(None, description="Email or ID of user who created this record")
    updated_by: Optional[str] = Field(None, description="Email or ID of user who last modified this record")

    model_config = ConfigDict(from_attributes=True)


class PatientSummary(BaseModel):
    id: int
    name: str
    age: int
    phone: str

    model_config = ConfigDict(from_attributes=True)


class DoctorDetailResponse(DoctorResponse):
    patients: List[PatientSummary] = Field(default_factory=list, description="List of assigned patients")

    model_config = ConfigDict(from_attributes=True)
