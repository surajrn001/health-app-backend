from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.appointment import AppointmentStatus
from app.schemas.doctor import PatientSummary
from app.schemas.patient import DoctorSummary


class AppointmentBase(BaseModel):
    doctor_id: Optional[int] = Field(
        None,
        description="Assigned Doctor ID. Optional for Doctors (defaults to authenticated doctor).",
        json_schema_extra={"example": 1},
    )
    patient_id: int = Field(
        ...,
        description="Target Patient ID",
        json_schema_extra={"example": 10},
    )
    appointment_date: datetime = Field(
        ...,
        description="Scheduled appointment date and time (ISO 8601)",
        json_schema_extra={"example": "2026-10-15T14:30:00Z"},
    )
    status: AppointmentStatus = Field(
        default=AppointmentStatus.SCHEDULED,
        description="Appointment status: scheduled, completed, cancelled",
        json_schema_extra={"example": "scheduled"},
    )


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    doctor_id: Optional[int] = Field(
        None,
        description="Updated Doctor ID",
        json_schema_extra={"example": 1},
    )
    patient_id: Optional[int] = Field(
        None,
        description="Updated Patient ID",
        json_schema_extra={"example": 10},
    )
    appointment_date: Optional[datetime] = Field(
        None,
        description="Updated appointment date and time",
        json_schema_extra={"example": "2026-10-16T15:00:00Z"},
    )
    status: Optional[AppointmentStatus] = Field(
        None,
        description="Updated appointment status: scheduled, completed, cancelled",
        json_schema_extra={"example": "completed"},
    )


class AppointmentResponse(BaseModel):
    id: int = Field(..., description="Unique appointment ID", json_schema_extra={"example": 101})
    doctor_id: int = Field(..., description="Doctor ID", json_schema_extra={"example": 1})
    patient_id: int = Field(..., description="Patient ID", json_schema_extra={"example": 10})
    appointment_date: datetime = Field(..., description="Scheduled date-time", json_schema_extra={"example": "2026-10-15T14:30:00Z"})
    status: AppointmentStatus = Field(..., description="Status", json_schema_extra={"example": "scheduled"})
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Email/ID of creator")
    updated_by: Optional[str] = Field(None, description="Email/ID of last updater")
    doctor: Optional[DoctorSummary] = Field(None, description="Doctor summary details")
    patient: Optional[PatientSummary] = Field(None, description="Patient summary details")

    model_config = ConfigDict(from_attributes=True)
