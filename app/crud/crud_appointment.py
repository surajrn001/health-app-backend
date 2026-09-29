from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


def _to_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def check_overlapping_appointment(
    db: Session,
    doctor_id: int,
    appointment_date: datetime,
    exclude_id: Optional[int] = None,
) -> Optional[Appointment]:
    """
    Check if the doctor already has an active (non-cancelled) appointment
    scheduled at or overlapping the target appointment_date (30-minute window).
    """
    target_utc = _to_utc(appointment_date)
    
    # Query candidate appointments for this doctor that are not cancelled
    query = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
    )
    if exclude_id is not None:
        query = query.filter(Appointment.id != exclude_id)
        
    candidates = query.all()
    for appt in candidates:
        appt_utc = _to_utc(appt.appointment_date)
        diff_seconds = abs((appt_utc - target_utc).total_seconds())
        # Overlap if within 30 minutes (1800 seconds)
        if diff_seconds < 1800:
            return appt
    return None


def get_appointment(db: Session, appointment_id: int) -> Optional[Appointment]:
    """Retrieve appointment with eagerly loaded relationships to prevent N+1 queries."""
    return (
        db.query(Appointment)
        .options(
            joinedload(Appointment.doctor),
            joinedload(Appointment.patient),
        )
        .filter(Appointment.id == appointment_id)
        .first()
    )


def get_appointments(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    doctor_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status_filter: Optional[AppointmentStatus] = None,
    appointment_date: Optional[datetime] = None,
) -> Tuple[List[Appointment], int]:
    """List appointments with filtering and eager loading for performance."""
    query = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.doctor),
            joinedload(Appointment.patient),
        )
    )

    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)

    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)

    if status_filter is not None:
        query = query.filter(Appointment.status == status_filter)

    if appointment_date is not None:
        target_utc = _to_utc(appointment_date)
        start_day = target_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = start_day + timedelta(days=1)
        query = query.filter(
            Appointment.appointment_date >= start_day,
            Appointment.appointment_date < end_day,
        )

    total = query.count()
    appointments = (
        query.order_by(Appointment.appointment_date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return appointments, total


def create_appointment(
    db: Session,
    appointment_in: AppointmentCreate,
    resolved_doctor_id: int,
    created_by: Optional[str] = None,
) -> Appointment:
    """Create and validate a new appointment."""
    doctor = db.query(Doctor).filter(Doctor.id == resolved_doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {resolved_doctor_id} not found",
        )
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor with id {resolved_doctor_id} is inactive",
        )

    patient = db.query(Patient).filter(Patient.id == appointment_in.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {appointment_in.patient_id} not found",
        )
    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient with id {appointment_in.patient_id} is inactive",
        )

    # Check for overlapping appointment
    overlap = check_overlapping_appointment(
        db,
        doctor_id=resolved_doctor_id,
        appointment_date=appointment_in.appointment_date,
    )
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor '{doctor.name}' already has an overlapping appointment at this time",
        )

    appointment = Appointment(
        doctor_id=resolved_doctor_id,
        patient_id=appointment_in.patient_id,
        appointment_date=_to_utc(appointment_in.appointment_date),
        status=appointment_in.status or AppointmentStatus.SCHEDULED,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def update_appointment(
    db: Session,
    appointment: Appointment,
    appointment_in: AppointmentUpdate,
    updated_by: Optional[str] = None,
) -> Appointment:
    """Update appointment details with constraint validation."""
    update_data = appointment_in.model_dump(exclude_unset=True)

    target_doctor_id = update_data.get("doctor_id", appointment.doctor_id)
    if "doctor_id" in update_data and update_data["doctor_id"] != appointment.doctor_id:
        doc = db.query(Doctor).filter(Doctor.id == target_doctor_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with id {target_doctor_id} not found",
            )
        if not doc.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor with id {target_doctor_id} is inactive",
            )
        appointment.doctor_id = target_doctor_id

    if "patient_id" in update_data and update_data["patient_id"] != appointment.patient_id:
        pat = db.query(Patient).filter(Patient.id == update_data["patient_id"]).first()
        if not pat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {update_data['patient_id']} not found",
            )
        if not pat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Patient with id {update_data['patient_id']} is inactive",
            )
        appointment.patient_id = update_data["patient_id"]

    target_date = update_data.get("appointment_date")
    target_status = update_data.get("status", appointment.status)

    if target_date is not None or target_doctor_id != appointment.doctor_id:
        eval_date = _to_utc(target_date) if target_date else appointment.appointment_date
        if target_status != AppointmentStatus.CANCELLED:
            overlap = check_overlapping_appointment(
                db,
                doctor_id=target_doctor_id,
                appointment_date=eval_date,
                exclude_id=appointment.id,
            )
            if overlap:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Doctor already has an overlapping appointment at this time",
                )
        if target_date is not None:
            appointment.appointment_date = _to_utc(target_date)

    if "status" in update_data and update_data["status"] is not None:
        appointment.status = update_data["status"]

    if updated_by:
        appointment.updated_by = updated_by
    appointment.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(appointment)
    return appointment


def delete_appointment(db: Session, appointment: Appointment) -> Appointment:
    """Delete an appointment record."""
    db.delete(appointment)
    db.commit()
    return appointment
