from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserRole
from app.models.doctor_patient import DoctorPatient
from app.models.appointment import AppointmentStatus
from app.auth.dependencies import get_current_user, get_doctor_profile, require_admin
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientDetailResponse,
)
from app.models.billing import PaymentStatus
from app.schemas.appointment import AppointmentResponse
from app.schemas.billing import BillingResponse
from app.schemas.common import PaginatedResponse, make_paginated_response
from app.services import PatientService, DoctorService, AssignmentService, AppointmentService, BillingService

router = APIRouter(prefix="/patients", tags=["Patients"])


def _validate_doctor_assignment(db: Session, doctor_id: Optional[int]) -> None:
    if doctor_id is not None:
        doc = DoctorService.get_doctor(db, doctor_id)
        if not doc:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with id {doctor_id} not found",
            )
        if not doc.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign patient to inactive doctor {doc.name}",
            )


@router.post("", response_model=PatientResponse, status_code=http_status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def create_new_patient(
    request: Request,
    patient_in: PatientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new patient record."""
    _validate_doctor_assignment(db, patient_in.doctor_id)

    doctor_id_to_assign = patient_in.doctor_id

    # If created by a doctor and no explicit doctor_id provided, automatically assign to current doctor
    if current_user.role == UserRole.DOCTOR and doctor_id_to_assign is None:
        doctor = get_doctor_profile(current_user, db)
        if doctor and doctor.is_active:
            doctor_id_to_assign = doctor.id

    patient = PatientService.create_patient(
        db,
        patient_in,
        doctor_id=doctor_id_to_assign,
        created_by=current_user.email,
    )

    # Also maintain secondary doctor_patient link for doctor if assigned
    if doctor_id_to_assign is not None:
        existing_link = (
            db.query(DoctorPatient)
            .filter(DoctorPatient.doctor_id == doctor_id_to_assign, DoctorPatient.patient_id == patient.id)
            .first()
        )
        if not existing_link:
            db.add(DoctorPatient(doctor_id=doctor_id_to_assign, patient_id=patient.id))
            db.commit()
            db.refresh(patient)

    return patient


@router.get("", response_model=PaginatedResponse[PatientResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def list_patients(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    search: Optional[str] = None,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    age_gt: Optional[int] = Query(None, description="Filter patients with age greater than value (e.g. age_gt=30)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List patients.
    - Admin: can view all patients across the system.
    - Doctor: can view only their assigned patients.
    """
    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit

    if current_user.role == UserRole.DOCTOR:
        doctor = get_doctor_profile(current_user, db)
        if not doctor:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found",
            )
        patients, total = AssignmentService.get_doctor_patients(
            db,
            doctor_id=doctor.id,
            skip=skip,
            limit=actual_limit,
            is_active=is_active,
            age_gt=age_gt,
            search=search,
        )
    else:
        patients, total = PatientService.get_patients(
            db,
            skip=skip,
            limit=actual_limit,
            is_active=is_active,
            search=search,
            age_gt=age_gt,
        )

    return make_paginated_response(items=patients, total=total, page=page, limit=actual_limit)


@router.get("/{patient_id}", response_model=PatientDetailResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def get_patient_by_id(
    request: Request,
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve single patient details.
    - Doctor: can view only if patient is assigned to them.
    - Admin: full access.
    """
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor = get_doctor_profile(current_user, db)
        if not doctor or not AssignmentService.is_patient_assigned_to_doctor(db, doctor.id, patient_id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own assigned patients",
            )

    return patient


@router.put("/{patient_id}", response_model=PatientResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def update_patient_by_id(
    request: Request,
    patient_id: int,
    patient_in: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full update of patient record."""
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor = get_doctor_profile(current_user, db)
        if not doctor or not AssignmentService.is_patient_assigned_to_doctor(db, doctor.id, patient_id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own assigned patients",
            )

    _validate_doctor_assignment(db, patient_in.doctor_id)
    return PatientService.update_patient(db, patient, patient_in, updated_by=current_user.email)


@router.patch("/{patient_id}", response_model=PatientResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def patch_patient_by_id(
    request: Request,
    patient_id: int,
    patient_in: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partial update of patient record."""
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor = get_doctor_profile(current_user, db)
        if not doctor or not AssignmentService.is_patient_assigned_to_doctor(db, doctor.id, patient_id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own assigned patients",
            )

    _validate_doctor_assignment(db, patient_in.doctor_id)
    return PatientService.update_patient(db, patient, patient_in, updated_by=current_user.email)


@router.delete("/{patient_id}", response_model=PatientResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def delete_patient_by_id(
    request: Request,
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deactivate patient record (Admin only).
    Doctors cannot delete patients (returns 403 Forbidden).
    """
    if current_user.role == UserRole.DOCTOR:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Doctors are not authorized to delete patients",
        )

    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found",
        )

    if not patient.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Patient with id {patient_id} is already deactivated",
        )

    return PatientService.soft_delete_patient(db, patient, updated_by=current_user.email)


@router.get("/{patient_id}/appointments", response_model=PaginatedResponse[AppointmentResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def fetch_patient_appointments(
    request: Request,
    patient_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    status: Optional[AppointmentStatus] = Query(None, description="Filter by status"),
    appointment_date: Optional[datetime] = Query(None, description="Filter by date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve appointments for a specific patient.
    - Admin: can view any patient's appointments.
    - Doctor: can only view appointments for their assigned patients.
    """
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor = get_doctor_profile(current_user, db)
        if not doctor or not AssignmentService.is_patient_assigned_to_doctor(db, doctor.id, patient_id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view appointments for their assigned patients",
            )

    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit
    appointments, total = AppointmentService.get_appointments(
        db,
        skip=skip,
        limit=actual_limit,
        patient_id=patient_id,
        status_filter=status,
        appointment_date=appointment_date,
    )
    return make_paginated_response(items=appointments, total=total, page=page, limit=actual_limit)


@router.get("/{patient_id}/billings", response_model=PaginatedResponse[BillingResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def fetch_patient_billings(
    request: Request,
    patient_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve billing records for a specific patient (Level 27 & 28).
    - Admin: Can view any patient's billings.
    - Doctor: Can only view billings for their assigned patients.
    """
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor = get_doctor_profile(current_user, db)
        if not doctor or not AssignmentService.is_patient_assigned_to_doctor(db, doctor.id, patient_id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view billings for their assigned patients",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to patient billings",
        )

    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit
    billings, total = BillingService.get_billings(
        db,
        skip=skip,
        limit=actual_limit,
        patient_id=patient_id,
        payment_status=payment_status,
        is_active=is_active,
    )
    return make_paginated_response(items=billings, total=total, page=page, limit=actual_limit)

