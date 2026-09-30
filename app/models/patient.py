from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import AuditableMixin


class Patient(Base, AuditableMixin):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    age = Column(Integer, nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True)

    doctor = relationship("Doctor", back_populates="patients", foreign_keys=[doctor_id], lazy="joined")
    doctors = relationship(
        "Doctor",
        secondary="doctor_patient",
        back_populates="secondary_patients",
        lazy="selectin",
    )
    appointments = relationship(
        "Appointment",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    billings = relationship(
        "Billing",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_patient_doc_active", "doctor_id", "is_active"),
    )
