from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserRole
from app.models.appointment import AppointmentStatus
from app.auth.dependencies import (
    get_current_user,
    require_admin,
    get_doctor_profile,
)
from app.schemas.doctor import (
    DoctorCreate,
    DoctorUpdate,
    DoctorResponse,
    DoctorDetailResponse,
)
from app.models.billing import PaymentStatus
from app.schemas.patient import PatientResponse
from app.schemas.assignment import DoctorPatientAssignmentResponse
from app.schemas.appointment import AppointmentResponse
from app.schemas.billing import BillingResponse
from app.schemas.common import PaginatedResponse, make_paginated_response
from app.services import DoctorService, AssignmentService, AppointmentService, BillingService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post("", response_model=DoctorResponse, status_code=http_status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def create_new_doctor(
    request: Request,
    doctor_in: DoctorCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Register a new doctor (Admin only)."""
    if DoctorService.get_doctor_by_email(db, doctor_in.email):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor with email '{doctor_in.email}' already exists",
        )
    return DoctorService.create_doctor(db, doctor_in, created_by=current_user.email)


@router.get("", response_model=PaginatedResponse[DoctorResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def list_doctors(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    search: Optional[str] = None,
    specialization: Optional[str] = Query(None, description="Filter by specialization (e.g. cardiology)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status (true/false)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve paginated list of doctors with search and filtering."""
    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit
    doctors, total = DoctorService.get_doctors(
        db,
        skip=skip,
        limit=actual_limit,
        is_active=is_active,
        search=search,
        specialization=specialization,
    )
    return make_paginated_response(items=doctors, total=total, page=page, limit=actual_limit)


@router.get("/{doctor_id}", response_model=DoctorDetailResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def get_doctor_by_id(
    request: Request,
    doctor_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed doctor profile including assigned patients."""
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )
    return doctor


@router.put("/{doctor_id}", response_model=DoctorResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def update_doctor_by_id(
    request: Request,
    doctor_id: int,
    doctor_in: DoctorUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full update of doctor profile."""
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        user_doctor = get_doctor_profile(current_user, db)
        if not user_doctor or user_doctor.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="You can only update your own profile",
            )
        if doctor_in.is_active is not None and doctor_in.is_active != doctor.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only admin can modify active status",
            )

    if doctor_in.email and doctor_in.email.lower().strip() != doctor.email.lower():
        existing = DoctorService.get_doctor_by_email(db, doctor_in.email)
        if existing and existing.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{doctor_in.email}' is already in use",
            )

    return DoctorService.update_doctor(db, doctor, doctor_in, updated_by=current_user.email)


@router.patch("/{doctor_id}", response_model=DoctorResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def patch_doctor_by_id(
    request: Request,
    doctor_id: int,
    doctor_in: DoctorUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partial update of doctor profile."""
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        user_doctor = get_doctor_profile(current_user, db)
        if not user_doctor or user_doctor.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="You can only update your own profile",
            )
        if doctor_in.is_active is not None and doctor_in.is_active != doctor.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only admin can modify active status",
            )

    if doctor_in.email and doctor_in.email.lower().strip() != doctor.email.lower():
        existing = DoctorService.get_doctor_by_email(db, doctor_in.email)
        if existing and existing.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{doctor_in.email}' is already in use",
            )

    return DoctorService.update_doctor(db, doctor, doctor_in, updated_by=current_user.email)


@router.delete("/{doctor_id}", response_model=DoctorResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def delete_doctor(
    request: Request,
    doctor_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft delete (deactivate) doctor account (Admin only)."""
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    if not doctor.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor with id {doctor_id} is already deactivated",
        )

    return DoctorService.soft_delete_doctor(db, doctor, updated_by=current_user.email)


@router.post("/{doctor_id}/patients/{patient_id}", response_model=DoctorPatientAssignmentResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def assign_patient(
    request: Request,
    doctor_id: int,
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign patient to doctor."""
    if current_user.role == UserRole.DOCTOR:
        user_doctor = get_doctor_profile(current_user, db)
        if not user_doctor or user_doctor.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only assign patients to themselves",
            )

    doctor, patient, assignment = AssignmentService.assign_patient_to_doctor(db, doctor_id, patient_id)
    return DoctorPatientAssignmentResponse(
        message="Patient assigned successfully to doctor",
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        patient_id=patient.id,
        patient_name=patient.name,
        assigned_at=assignment.assigned_at,
    )


@router.get("/{doctor_id}/patients", response_model=PaginatedResponse[PatientResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def fetch_doctor_patients(
    request: Request,
    doctor_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all patients assigned to a doctor."""
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )
    if not doctor.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor with id {doctor_id} is inactive",
        )

    if current_user.role == UserRole.DOCTOR:
        user_doctor = get_doctor_profile(current_user, db)
        if not user_doctor or user_doctor.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own assigned patients",
            )

    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit
    patients, total = AssignmentService.get_doctor_patients(db, doctor_id=doctor_id, skip=skip, limit=actual_limit)
    return make_paginated_response(items=patients, total=total, page=page, limit=actual_limit)


@router.get("/{doctor_id}/appointments", response_model=PaginatedResponse[AppointmentResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def fetch_doctor_appointments(
    request: Request,
    doctor_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    status: Optional[AppointmentStatus] = Query(None, description="Filter by status"),
    appointment_date: Optional[datetime] = Query(None, description="Filter by date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve appointments for a specific doctor.
    - Admin: can view any doctor's appointments.
    - Doctor: can only view their own appointments.
    """
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        user_doctor = get_doctor_profile(current_user, db)
        if not user_doctor or user_doctor.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own appointments",
            )

    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit
    appointments, total = AppointmentService.get_appointments(
        db,
        skip=skip,
        limit=actual_limit,
        doctor_id=doctor_id,
        status_filter=status,
        appointment_date=appointment_date,
    )
    return make_paginated_response(items=appointments, total=total, page=page, limit=actual_limit)


@router.get("/{doctor_id}/billings", response_model=PaginatedResponse[BillingResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def fetch_doctor_billings(
    request: Request,
    doctor_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve billing records for a specific doctor (Level 27 & 28).
    - Admin: Can view any doctor's billings.
    - Doctor: Can only view their own billings.
    """
    doctor = DoctorService.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        user_doctor = get_doctor_profile(current_user, db)
        if not user_doctor or user_doctor.id != doctor_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own billing records",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to doctor billing records",
        )

    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit
    billings, total = BillingService.get_billings(
        db,
        skip=skip,
        limit=actual_limit,
        doctor_id=doctor_id,
        payment_status=payment_status,
        is_active=is_active,
    )
    return make_paginated_response(items=billings, total=total, page=page, limit=actual_limit)

