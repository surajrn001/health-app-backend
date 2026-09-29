from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base


class DoctorPatient(Base):
    __tablename__ = "doctor_patient"

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
