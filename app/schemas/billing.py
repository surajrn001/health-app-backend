from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.billing import PaymentStatus, PaymentMode
from app.schemas.doctor import PatientSummary
from app.schemas.patient import DoctorSummary


class BillingBase(BaseModel):
    patient_id: int = Field(
        ...,
        description="Target Patient ID",
        json_schema_extra={"example": 10},
    )
    doctor_id: Optional[int] = Field(
        None,
        description="Assigned Doctor ID. Optional for Doctors (defaults to authenticated doctor). Required for Admins.",
        json_schema_extra={"example": 1},
    )
    appointment_id: Optional[int] = Field(
        None,
        description="Optional associated Appointment ID",
        json_schema_extra={"example": 101},
    )
    consultation_fee: float = Field(
        default=0.0,
        ge=0.0,
        description="Doctor consultation fee (non-negative)",
        json_schema_extra={"example": 150.0},
    )
    additional_charges: float = Field(
        default=0.0,
        ge=0.0,
        description="Additional charges (tests, medication, etc.)",
        json_schema_extra={"example": 25.0},
    )
    payment_status: PaymentStatus = Field(
        default=PaymentStatus.PENDING,
        description="Payment status: pending, paid, cancelled",
        json_schema_extra={"example": "pending"},
    )
    payment_mode: Optional[PaymentMode] = Field(
        default=PaymentMode.CASH,
        description="Payment mode: cash, card, upi",
        json_schema_extra={"example": "cash"},
    )


class BillingCreate(BillingBase):
    total_amount: Optional[float] = Field(
        None,
        description="Total amount (auto-calculated if omitted: consultation_fee + additional_charges)",
        json_schema_extra={"example": 175.0},
    )


class BillingUpdate(BaseModel):
    patient_id: Optional[int] = Field(
        None,
        description="Updated Patient ID",
        json_schema_extra={"example": 10},
    )
    doctor_id: Optional[int] = Field(
        None,
        description="Updated Doctor ID",
        json_schema_extra={"example": 1},
    )
    appointment_id: Optional[int] = Field(
        None,
        description="Updated Appointment ID",
        json_schema_extra={"example": 101},
    )
    consultation_fee: Optional[float] = Field(
        None,
        ge=0.0,
        description="Updated consultation fee",
        json_schema_extra={"example": 200.0},
    )
    additional_charges: Optional[float] = Field(
        None,
        ge=0.0,
        description="Updated additional charges",
        json_schema_extra={"example": 50.0},
    )
    payment_status: Optional[PaymentStatus] = Field(
        None,
        description="Updated payment status: pending, paid, cancelled",
        json_schema_extra={"example": "paid"},
    )
    payment_mode: Optional[PaymentMode] = Field(
        None,
        description="Updated payment mode: cash, card, upi",
        json_schema_extra={"example": "card"},
    )
    is_active: Optional[bool] = Field(
        None,
        description="Active status flag",
        json_schema_extra={"example": True},
    )


class BillingPatch(BillingUpdate):
    pass


class BillingResponse(BaseModel):
    id: int = Field(..., description="Unique billing record ID", json_schema_extra={"example": 1})
    patient_id: int = Field(..., description="Patient ID", json_schema_extra={"example": 10})
    doctor_id: int = Field(..., description="Doctor ID", json_schema_extra={"example": 1})
    appointment_id: Optional[int] = Field(None, description="Linked Appointment ID", json_schema_extra={"example": 101})
    consultation_fee: float = Field(..., description="Doctor consultation fee", json_schema_extra={"example": 150.0})
    additional_charges: float = Field(..., description="Additional charges", json_schema_extra={"example": 25.0})
    total_amount: float = Field(..., description="Auto-calculated total amount", json_schema_extra={"example": 175.0})
    payment_status: PaymentStatus = Field(..., description="Payment status: pending, paid, cancelled", json_schema_extra={"example": "paid"})
    payment_mode: Optional[PaymentMode] = Field(None, description="Payment mode: cash, card, upi", json_schema_extra={"example": "cash"})
    is_active: bool = Field(..., description="Active status", json_schema_extra={"example": True})
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Email/ID of record creator")
    updated_by: Optional[str] = Field(None, description="Email/ID of last updater")
    doctor: Optional[DoctorSummary] = Field(None, description="Doctor summary details")
    patient: Optional[PatientSummary] = Field(None, description="Patient summary details")

    model_config = ConfigDict(from_attributes=True)


class DoctorRevenueItem(BaseModel):
    doctor_id: int = Field(..., description="Doctor ID")
    doctor_name: str = Field(..., description="Doctor's full name")
    total_revenue: float = Field(..., description="Total collected revenue from paid billings")
    paid_billings_count: int = Field(..., description="Number of paid billing records")


class DailyRevenueItem(BaseModel):
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    total_revenue: float = Field(..., description="Total collected revenue from paid billings on this date")
    paid_billings_count: int = Field(..., description="Number of paid billing records on this date")


class RevenueReportResponse(BaseModel):
    total_revenue: float = Field(..., description="Aggregate total revenue from paid billings")
    total_paid_records: int = Field(..., description="Aggregate count of paid billing transactions")
    from_date: Optional[str] = Field(None, description="Start date filter applied")
    to_date: Optional[str] = Field(None, description="End date filter applied")
    doctor_id: Optional[int] = Field(None, description="Doctor ID filter applied (if any)")
    revenue_by_doctor: List[DoctorRevenueItem] = Field(default_factory=list, description="Breakdown of revenue per doctor")
    revenue_by_day: List[DailyRevenueItem] = Field(default_factory=list, description="Breakdown of revenue per day")
