import enum
from sqlalchemy import Column, Integer, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import AuditableMixin


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Appointment(Base, AuditableMixin):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(
        Enum(AppointmentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AppointmentStatus.SCHEDULED,
        index=True,
    )

    doctor = relationship("Doctor", back_populates="appointments", lazy="joined")
    patient = relationship("Patient", back_populates="appointments", lazy="joined")

    __table_args__ = (
        Index("ix_appointment_doctor_date", "doctor_id", "appointment_date"),
        Index("ix_appointment_doctor_status", "doctor_id", "status"),
        Index("ix_appointment_patient_status", "patient_id", "status"),
    )
