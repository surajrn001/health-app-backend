from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.models.doctor import Doctor
from app.models.user import User, UserRole
from app.schemas.doctor import DoctorCreate, DoctorUpdate
from app.auth.jwt import hash_password


def get_doctor(db: Session, doctor_id: int) -> Optional[Doctor]:
    return (
        db.query(Doctor)
        .options(selectinload(Doctor.patients))
        .filter(Doctor.id == doctor_id)
        .first()
    )


def get_doctor_by_email(db: Session, email: str) -> Optional[Doctor]:
    return db.query(Doctor).filter(Doctor.email == email.lower().strip()).first()


def get_doctors(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    specialization: Optional[str] = None,
) -> Tuple[List[Doctor], int]:
    query = db.query(Doctor)

    if is_active is not None:
        query = query.filter(Doctor.is_active == is_active)

    if specialization:
        query = query.filter(Doctor.specialization.ilike(f"%{specialization.strip()}%"))

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Doctor.name.ilike(search_pattern),
                Doctor.specialization.ilike(search_pattern),
                Doctor.email.ilike(search_pattern),
            )
        )

    total = query.count()
    doctors = query.order_by(Doctor.id.asc()).offset(skip).limit(limit).all()
    return doctors, total


def create_doctor(
    db: Session,
    doctor_in: DoctorCreate,
    created_by: Optional[str] = None,
) -> Doctor:
    normalized_email = doctor_in.email.lower().strip()

    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        password_to_hash = doctor_in.password or "Doctor@123"
        user = User(
            email=normalized_email,
            hashed_password=hash_password(password_to_hash),
            role=UserRole.DOCTOR,
            is_active=doctor_in.is_active,
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(user)
        db.flush()

    db_doctor = Doctor(
        name=doctor_in.name.strip(),
        specialization=doctor_in.specialization.strip(),
        email=normalized_email,
        is_active=doctor_in.is_active,
        user_id=user.id,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor


def update_doctor(
    db: Session,
    doctor: Doctor,
    doctor_in: DoctorUpdate,
    updated_by: Optional[str] = None,
) -> Doctor:
    update_data = doctor_in.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"]:
        new_email = update_data["email"].lower().strip()
        doctor.email = new_email
        if doctor.user:
            doctor.user.email = new_email

    if "name" in update_data and update_data["name"]:
        doctor.name = update_data["name"].strip()

    if "specialization" in update_data and update_data["specialization"]:
        doctor.specialization = update_data["specialization"].strip()

    if "is_active" in update_data and update_data["is_active"] is not None:
        doctor.is_active = update_data["is_active"]
        if doctor.user:
            doctor.user.is_active = update_data["is_active"]

    if updated_by:
        doctor.updated_by = updated_by
        if doctor.user:
            doctor.user.updated_by = updated_by
    doctor.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(doctor)
    return doctor


def soft_delete_doctor(
    db: Session,
    doctor: Doctor,
    updated_by: Optional[str] = None,
) -> Doctor:
    doctor.is_active = False
    if doctor.user:
        doctor.user.is_active = False
    if updated_by:
        doctor.updated_by = updated_by
        if doctor.user:
            doctor.user.updated_by = updated_by
    doctor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doctor)
    return doctor
