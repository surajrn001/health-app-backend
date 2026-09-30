import enum
from sqlalchemy import Column, Integer, Float, Enum, ForeignKey, Index, Boolean, CheckConstraint, String
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import AuditableMixin


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentMode(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"


class Billing(Base, AuditableMixin):
    __tablename__ = "billings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    consultation_fee = Column(Float, nullable=False, default=0.0)
    additional_charges = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    payment_status = Column(
        Enum(PaymentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    payment_mode = Column(
        Enum(PaymentMode, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        default=PaymentMode.CASH,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    patient = relationship("Patient", back_populates="billings", lazy="joined")
    doctor = relationship("Doctor", back_populates="billings", lazy="joined")
    appointment = relationship("Appointment", back_populates="billing", lazy="joined")

    __table_args__ = (
        CheckConstraint("consultation_fee >= 0", name="chk_billing_consultation_fee_non_negative"),
        CheckConstraint("additional_charges >= 0", name="chk_billing_additional_charges_non_negative"),
        CheckConstraint("total_amount >= 0", name="chk_billing_total_amount_non_negative"),
        Index("ix_billing_doctor_status", "doctor_id", "payment_status"),
        Index("ix_billing_patient_status", "patient_id", "payment_status"),
        Index("ix_billing_created_active", "created_at", "is_active"),
        Index("ix_billing_appointment", "appointment_id"),
    )
