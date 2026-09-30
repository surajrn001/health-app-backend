from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import AuditableMixin


class Doctor(Base, AuditableMixin):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    specialization = Column(String(150), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)

    user = relationship("User", back_populates="doctor")
    patients = relationship(
        "Patient",
        back_populates="doctor",
        foreign_keys="[Patient.doctor_id]",
        lazy="selectin",
    )
    secondary_patients = relationship(
        "Patient",
        secondary="doctor_patient",
        back_populates="doctors",
        lazy="selectin",
    )
    appointments = relationship(
        "Appointment",
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    billings = relationship(
        "Billing",
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_doctor_email"),
        Index("ix_doctor_spec_active", "specialization", "is_active"),
    )
