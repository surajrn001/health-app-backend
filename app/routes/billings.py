from datetime import datetime, time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserRole
from app.models.billing import PaymentStatus, PaymentMode
from app.auth.dependencies import get_current_user, get_doctor_profile
from app.schemas.billing import (
    BillingCreate,
    BillingUpdate,
    BillingPatch,
    BillingResponse,
    RevenueReportResponse,
)
from app.schemas.common import PaginatedResponse, make_paginated_response, MessageResponse
from app.services import BillingService, DoctorService, PatientService, AssignmentService

router = APIRouter(prefix="/billings", tags=["Billings"])


def _parse_date_bounds(
    from_str: Optional[str],
    to_str: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse date query strings into start-of-day and end-of-day datetimes."""
    start_dt = None
    end_dt = None
    if from_str:
        try:
            # Handle YYYY-MM-DD or ISO strings
            if "T" in from_str:
                start_dt = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
            else:
                d = datetime.strptime(from_str, "%Y-%m-%d").date()
                start_dt = datetime.combine(d, time.min)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format for 'from': '{from_str}'. Expected YYYY-MM-DD.",
            )

    if to_str:
        try:
            if "T" in to_str:
                end_dt = datetime.fromisoformat(to_str.replace("Z", "+00:00"))
            else:
                d = datetime.strptime(to_str, "%Y-%m-%d").date()
                end_dt = datetime.combine(d, time.max)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format for 'to': '{to_str}'. Expected YYYY-MM-DD.",
            )

    return start_dt, end_dt


@router.post("", response_model=BillingResponse, status_code=http_status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def create_billing(
    request: Request,
    billing_in: BillingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new billing record.
    - Admin: Full access to create billing for any doctor.
    - Doctor: Can create billing for their own patients.
    - Non-admin/non-doctor: 403 Forbidden.
    """
    resolved_doctor_id = billing_in.doctor_id

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
                detail="Doctors can only create billing records for their own patients",
            )
        resolved_doctor_id = doctor_profile.id
    elif current_user.role == UserRole.ADMIN:
        if resolved_doctor_id is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="doctor_id is required when creating billing as admin",
            )
    else:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to billing creation",
        )

    return BillingService.create_billing(
        db,
        billing_in=billing_in,
        resolved_doctor_id=resolved_doctor_id,
        created_by=current_user.email,
    )


@router.get("", response_model=PaginatedResponse[BillingResponse])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def list_billings(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit"),
    doctor_id: Optional[int] = Query(None, description="Filter by Doctor ID"),
    patient_id: Optional[int] = Query(None, description="Filter by Patient ID"),
    appointment_id: Optional[int] = Query(None, description="Filter by Appointment ID"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    payment_mode: Optional[PaymentMode] = Query(None, description="Filter by payment mode"),
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    from_date_alt: Optional[str] = Query(None, alias="from_date", description="Start date alias"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    to_date_alt: Optional[str] = Query(None, alias="to_date", description="End date alias"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List billings with filtering and pagination (Level 28).
    - Admin: Full visibility over all billings.
    - Doctor: Restricted to viewing billings for their patients.
    """
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
                detail="Doctors can only view their own billing records",
            )
        effective_doctor_id = doctor_profile.id
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to billing records",
        )

    actual_limit = page_size if page_size is not None else limit
    skip = (page - 1) * actual_limit

    start_str = from_date or from_date_alt
    end_str = to_date or to_date_alt
    start_dt, end_dt = _parse_date_bounds(start_str, end_str)

    billings, total = BillingService.get_billings(
        db,
        skip=skip,
        limit=actual_limit,
        doctor_id=effective_doctor_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        payment_status=payment_status,
        payment_mode=payment_mode,
        from_date=start_dt,
        to_date=end_dt,
        is_active=is_active,
    )

    return make_paginated_response(billings, total, page, actual_limit)


@router.get("/{billing_id}", response_model=BillingResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def get_billing_by_id(
    request: Request,
    billing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve single billing record by ID.
    - Admin: Can view any billing record.
    - Doctor: Can view billings related to their patients.
    """
    billing = BillingService.get_billing(db, billing_id)
    if not billing:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Billing record with id {billing_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found",
            )
        is_own_billing = billing.doctor_id == doctor_profile.id
        is_assigned_patient = AssignmentService.is_patient_assigned_to_doctor(
            db, doctor_profile.id, billing.patient_id
        )
        if not (is_own_billing or is_assigned_patient):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Access denied to this billing record",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to billing records",
        )

    return billing


@router.put("/{billing_id}", response_model=BillingResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def update_billing_by_id(
    request: Request,
    billing_id: int,
    billing_in: BillingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full update of a billing record.
    - Admin: Full access.
    - Doctor: Can update billings related to their patients.
    """
    billing = BillingService.get_billing(db, billing_id)
    if not billing:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Billing record with id {billing_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile or billing.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own billing records",
            )
        if billing_in.doctor_id is not None and billing_in.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors cannot reassign billings to other doctors",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to update billing record",
        )

    return BillingService.update_billing(
        db,
        billing=billing,
        billing_in=billing_in,
        updated_by=current_user.email,
    )


@router.patch("/{billing_id}", response_model=BillingResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def patch_billing_by_id(
    request: Request,
    billing_id: int,
    billing_in: BillingPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Partial update of a billing record.
    - Admin: Full access.
    - Doctor: Can update billings related to their patients.
    """
    billing = BillingService.get_billing(db, billing_id)
    if not billing:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Billing record with id {billing_id} not found",
        )

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile or billing.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own billing records",
            )
        if billing_in.doctor_id is not None and billing_in.doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors cannot reassign billings to other doctors",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to patch billing record",
        )

    return BillingService.update_billing(
        db,
        billing=billing,
        billing_in=billing_in,
        updated_by=current_user.email,
    )


@router.delete("/{billing_id}", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def delete_billing_by_id(
    request: Request,
    billing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Soft delete a billing record.
    - Admin: Allowed.
    - Doctor: 403 Forbidden (Cannot delete billing records).
    """
    if current_user.role == UserRole.DOCTOR:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Doctors are not permitted to delete billing records",
        )
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to delete billing records",
        )

    billing = BillingService.get_billing(db, billing_id)
    if not billing:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Billing record with id {billing_id} not found",
        )

    BillingService.soft_delete_billing(db, billing, updated_by=current_user.email)
    return MessageResponse(message=f"Billing record {billing_id} successfully deleted")
