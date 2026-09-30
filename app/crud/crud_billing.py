from datetime import datetime, time
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date
from fastapi import HTTPException, status

from app.models.billing import Billing, PaymentStatus, PaymentMode
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.billing import (
    BillingCreate,
    BillingUpdate,
    DoctorRevenueItem,
    DailyRevenueItem,
    RevenueReportResponse,
)


def get_billing(db: Session, billing_id: int) -> Optional[Billing]:
    """Retrieve a billing record with eagerly loaded relations."""
    return (
        db.query(Billing)
        .options(
            joinedload(Billing.doctor),
            joinedload(Billing.patient),
            joinedload(Billing.appointment),
        )
        .filter(Billing.id == billing_id)
        .first()
    )


def get_billings(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    doctor_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    appointment_id: Optional[int] = None,
    payment_status: Optional[PaymentStatus] = None,
    payment_mode: Optional[PaymentMode] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    is_active: Optional[bool] = None,
) -> Tuple[List[Billing], int]:
    """Query billing records with filtering and pagination."""
    query = db.query(Billing).options(
        joinedload(Billing.doctor),
        joinedload(Billing.patient),
        joinedload(Billing.appointment),
    )

    if is_active is not None:
        query = query.filter(Billing.is_active == is_active)

    if doctor_id is not None:
        query = query.filter(Billing.doctor_id == doctor_id)

    if patient_id is not None:
        query = query.filter(Billing.patient_id == patient_id)

    if appointment_id is not None:
        query = query.filter(Billing.appointment_id == appointment_id)

    if payment_status is not None:
        query = query.filter(Billing.payment_status == payment_status)

    if payment_mode is not None:
        query = query.filter(Billing.payment_mode == payment_mode)

    if from_date is not None:
        query = query.filter(Billing.created_at >= from_date)

    if to_date is not None:
        query = query.filter(Billing.created_at <= to_date)

    total = query.count()
    billings = (
        query.order_by(Billing.created_at.desc(), Billing.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return billings, total


def create_billing(
    db: Session,
    billing_in: BillingCreate,
    resolved_doctor_id: int,
    created_by: Optional[str] = None,
) -> Billing:
    """
    Create a new billing record with transaction consistency (Level 27 & 29).
    - Validates Patient and Doctor exist and are active.
    - Validates Appointment belongs to same Doctor & Patient.
    - Prevents billing for cancelled appointments.
    - Prevents duplicate billing for the same appointment.
    - Auto-calculates total_amount.
    - Updates appointment status to COMPLETED inside atomic transaction.
    """
    # 1. Validate Patient
    patient = db.query(Patient).filter(Patient.id == billing_in.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {billing_in.patient_id} not found",
        )
    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient with id {billing_in.patient_id} is inactive",
        )

    # 2. Validate Doctor
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

    # 3. Validate Appointment (if provided)
    appointment = None
    if billing_in.appointment_id is not None:
        appointment = db.query(Appointment).filter(Appointment.id == billing_in.appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment with id {billing_in.appointment_id} not found",
            )

        if appointment.doctor_id != resolved_doctor_id or appointment.patient_id != billing_in.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment does not belong to specified doctor and patient",
            )

        if appointment.status == AppointmentStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create billing for a cancelled appointment",
            )

        # Prevent duplicate billing for the same appointment
        existing_billing = (
            db.query(Billing)
            .filter(
                Billing.appointment_id == billing_in.appointment_id,
                Billing.is_active == True,
            )
            .first()
        )
        if existing_billing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Billing record already exists for appointment {billing_in.appointment_id}",
            )

    # 4. Auto-calculate total_amount
    consultation_fee = round(float(billing_in.consultation_fee), 2)
    additional_charges = round(float(billing_in.additional_charges), 2)
    total_amount = round(consultation_fee + additional_charges, 2)

    # 5. Atomic DB Transaction (Level 29)
    try:
        billing = Billing(
            patient_id=billing_in.patient_id,
            doctor_id=resolved_doctor_id,
            appointment_id=billing_in.appointment_id,
            consultation_fee=consultation_fee,
            additional_charges=additional_charges,
            total_amount=total_amount,
            payment_status=billing_in.payment_status,
            payment_mode=billing_in.payment_mode,
            is_active=True,
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(billing)

        # When creating billing for a scheduled appointment, transition appointment status to completed
        if appointment and appointment.status == AppointmentStatus.SCHEDULED:
            appointment.status = AppointmentStatus.COMPLETED
            appointment.updated_by = created_by

        db.commit()
        db.refresh(billing)
        return billing
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise exc


def update_billing(
    db: Session,
    billing: Billing,
    billing_in: BillingUpdate,
    updated_by: Optional[str] = None,
) -> Billing:
    """Update a billing record with validation and total_amount recalculation."""
    update_data = billing_in.model_dump(exclude_unset=True)

    new_patient_id = update_data.get("patient_id", billing.patient_id)
    new_doctor_id = update_data.get("doctor_id", billing.doctor_id)
    new_appointment_id = update_data.get("appointment_id", billing.appointment_id)

    # Validate patient if modified
    if "patient_id" in update_data and update_data["patient_id"] != billing.patient_id:
        patient = db.query(Patient).filter(Patient.id == update_data["patient_id"]).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {update_data['patient_id']} not found",
            )
        if not patient.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Patient with id {update_data['patient_id']} is inactive",
            )

    # Validate doctor if modified
    if "doctor_id" in update_data and update_data["doctor_id"] != billing.doctor_id:
        doctor = db.query(Doctor).filter(Doctor.id == update_data["doctor_id"]).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with id {update_data['doctor_id']} not found",
            )
        if not doctor.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor with id {update_data['doctor_id']} is inactive",
            )

    # Validate appointment if modified
    if new_appointment_id is not None:
        appointment = db.query(Appointment).filter(Appointment.id == new_appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment with id {new_appointment_id} not found",
            )
        if appointment.doctor_id != new_doctor_id or appointment.patient_id != new_patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment does not belong to specified doctor and patient",
            )
        if appointment.status == AppointmentStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot associate billing with a cancelled appointment",
            )
        if new_appointment_id != billing.appointment_id:
            existing = (
                db.query(Billing)
                .filter(
                    Billing.appointment_id == new_appointment_id,
                    Billing.id != billing.id,
                    Billing.is_active == True,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Billing record already exists for appointment {new_appointment_id}",
                )

    try:
        for field, value in update_data.items():
            setattr(billing, field, value)

        # Auto-recalculate total_amount
        consultation_fee = round(float(billing.consultation_fee), 2)
        additional_charges = round(float(billing.additional_charges), 2)
        billing.total_amount = round(consultation_fee + additional_charges, 2)
        billing.updated_by = updated_by

        db.commit()
        db.refresh(billing)
        return billing
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise exc


def soft_delete_billing(
    db: Session,
    billing: Billing,
    updated_by: Optional[str] = None,
) -> Billing:
    """Soft delete a billing record."""
    try:
        billing.is_active = False
        billing.updated_by = updated_by
        db.commit()
        db.refresh(billing)
        return billing
    except Exception as exc:
        db.rollback()
        raise exc


def get_revenue_report(
    db: Session,
    doctor_id: Optional[int] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> RevenueReportResponse:
    """
    Calculate revenue statistics (Level 28):
    - Total revenue per doctor
    - Total revenue per day
    - Aggregate total revenue and paid transactions count
    """
    base_query = db.query(Billing).filter(
        Billing.payment_status == PaymentStatus.PAID,
        Billing.is_active == True,
    )

    if doctor_id is not None:
        base_query = base_query.filter(Billing.doctor_id == doctor_id)

    if from_date is not None:
        base_query = base_query.filter(Billing.created_at >= from_date)

    if to_date is not None:
        base_query = base_query.filter(Billing.created_at <= to_date)

    # Aggregate total revenue & paid count
    all_paid_billings = base_query.all()
    total_rev = round(sum(b.total_amount for b in all_paid_billings), 2)
    total_count = len(all_paid_billings)

    # 1. Total revenue per doctor
    doctor_query = (
        db.query(
            Billing.doctor_id,
            Doctor.name.label("doctor_name"),
            func.sum(Billing.total_amount).label("total_revenue"),
            func.count(Billing.id).label("paid_billings_count"),
        )
        .join(Doctor, Doctor.id == Billing.doctor_id)
        .filter(
            Billing.payment_status == PaymentStatus.PAID,
            Billing.is_active == True,
        )
    )
    if doctor_id is not None:
        doctor_query = doctor_query.filter(Billing.doctor_id == doctor_id)
    if from_date is not None:
        doctor_query = doctor_query.filter(Billing.created_at >= from_date)
    if to_date is not None:
        doctor_query = doctor_query.filter(Billing.created_at <= to_date)

    doctor_results = (
        doctor_query.group_by(Billing.doctor_id, Doctor.name)
        .order_by(func.sum(Billing.total_amount).desc())
        .all()
    )

    revenue_by_doctor = [
        DoctorRevenueItem(
            doctor_id=row.doctor_id,
            doctor_name=row.doctor_name,
            total_revenue=round(float(row.total_revenue), 2),
            paid_billings_count=row.paid_billings_count,
        )
        for row in doctor_results
    ]

    # 2. Total revenue per day
    day_query = (
        db.query(
            func.date(Billing.created_at).label("day"),
            func.sum(Billing.total_amount).label("total_revenue"),
            func.count(Billing.id).label("paid_billings_count"),
        )
        .filter(
            Billing.payment_status == PaymentStatus.PAID,
            Billing.is_active == True,
        )
    )
    if doctor_id is not None:
        day_query = day_query.filter(Billing.doctor_id == doctor_id)
    if from_date is not None:
        day_query = day_query.filter(Billing.created_at >= from_date)
    if to_date is not None:
        day_query = day_query.filter(Billing.created_at <= to_date)

    day_results = (
        day_query.group_by(func.date(Billing.created_at))
        .order_by(func.date(Billing.created_at).asc())
        .all()
    )

    revenue_by_day = [
        DailyRevenueItem(
            date=str(row.day),
            total_revenue=round(float(row.total_revenue), 2),
            paid_billings_count=row.paid_billings_count,
        )
        for row in day_results
    ]

    return RevenueReportResponse(
        total_revenue=total_rev,
        total_paid_records=total_count,
        from_date=from_date.strftime("%Y-%m-%d") if from_date else None,
        to_date=to_date.strftime("%Y-%m-%d") if to_date else None,
        doctor_id=doctor_id,
        revenue_by_doctor=revenue_by_doctor,
        revenue_by_day=revenue_by_day,
    )
