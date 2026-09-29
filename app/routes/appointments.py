from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserRole
from app.models.appointment import AppointmentStatus
from app.auth.dependencies import get_current_user, get_doctor_profile
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
)
from app.schemas.common import PaginatedResponse, make_paginated_response, MessageResponse
from app.services import AppointmentService, DoctorService, PatientService, AssignmentService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("", response_model=AppointmentResponse, status_code=http_status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def create_appointment(
    request: Request,
    appointment_in: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Schedule a new appointment.
    - Doctor: can schedule appointments for themselves with any patient.
    - Admin: can schedule appointments for any active doctor.
    - Validates doctor & patient exist and are active.
    - Prevents overlapping appointments for the same doctor.
    """
    resolved_doctor_id = appointment_in.doctor_id

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found for authenticated user",
            )
        if resolved_doctor_id is not None and resolved_doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only schedule appointments for themselves",
            )
        resolved_doctor_id = doctor_profile.id
    else:
        if resolved_doctor_id is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="doctor_id is required when creating an appointment as admin",
            )

    return AppointmentService.create_appointment(
        db,
        appointment_in=appointment_in,
        resolved_doctor_id=resolved_doctor_id,
        created_by=current_user.email,
    )


@router.get("", response_model=PaginatedResponse[AppointmentResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def list_appointments(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    doctor_id: Optional[int] = Query(None, description="Filter by Doctor ID"),
    patient_id: Optional[int] = Query(None, description="Filter by Patient ID"),
    status: Optional[AppointmentStatus] = Query(None, description="Filter by status (scheduled, completed, cancelled)"),
    appointment_date: Optional[datetime] = Query(None, description="Filter by specific date (ISO 8601)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List appointments with filtering and pagination.
    - Admin: full visibility over all appointments.
    - Doctor: restricted to viewing their own appointments.
    """
    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit

    effective_doctor_id = doctor_id
    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found",
            )
        if doctor_id is not None and doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own appointments",
            )
        effective_doctor_id = doctor_profile.id

    appointments, total = AppointmentService.get_appointments(
        db,
        skip=skip,
        limit=actual_limit,
        doctor_id=effective_doctor_id,
        patient_id=patient_id,
        status_filter=status,
        appointment_date=appointment_date,
    )
    return make_paginated_response(items=appointments, total=total, page=page, limit=actual_limit)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def get_appointment_by_id(
    request: Request,
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get appointment by ID."""
    appointment = AppointmentService.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile or appointment.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own appointments",
            )

    return appointment


@router.put("/{appointment_id}", response_model=AppointmentResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def update_appointment_by_id(
    request: Request,
    appointment_id: int,
    appointment_in: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full update for appointment details."""
    appointment = AppointmentService.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile or appointment.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own appointments",
            )
        if appointment_in.doctor_id is not None and appointment_in.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors cannot reassign appointments to other doctors",
            )

    return AppointmentService.update_appointment(
        db,
        appointment,
        appointment_in,
        updated_by=current_user.email,
    )


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def patch_appointment_by_id(
    request: Request,
    appointment_id: int,
    appointment_in: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partial update for appointment details."""
    appointment = AppointmentService.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile or appointment.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own appointments",
            )
        if appointment_in.doctor_id is not None and appointment_in.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors cannot reassign appointments to other doctors",
            )

    return AppointmentService.update_appointment(
        db,
        appointment,
        appointment_in,
        updated_by=current_user.email,
    )


@router.delete("/{appointment_id}", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def delete_appointment_by_id(
    request: Request,
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete or cancel an appointment."""
    appointment = AppointmentService.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile or appointment.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only delete their own appointments",
            )

    AppointmentService.delete_appointment(db, appointment)
    return MessageResponse(message=f"Appointment with id {appointment_id} successfully deleted")
