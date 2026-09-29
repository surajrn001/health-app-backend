from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import or_

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
    return (
        db.query(Patient)
        .options(
            joinedload(Patient.doctor),
            selectinload(Patient.doctors),
        )
        .filter(Patient.id == patient_id)
        .first()
    )


def get_patients(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    age_gt: Optional[int] = None,
    doctor_id: Optional[int] = None,
) -> Tuple[List[Patient], int]:
    query = (
        db.query(Patient)
        .options(
            joinedload(Patient.doctor),
            selectinload(Patient.doctors),
        )
    )

    if is_active is not None:
        query = query.filter(Patient.is_active == is_active)

    if age_gt is not None:
        query = query.filter(Patient.age > age_gt)

    if doctor_id is not None:
        query = query.filter(Patient.doctor_id == doctor_id)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.name.ilike(search_pattern),
                Patient.phone.ilike(search_pattern),
            )
        )

    total = query.count()
    patients = query.order_by(Patient.id.asc()).offset(skip).limit(limit).all()
    return patients, total


def create_patient(
    db: Session,
    patient_in: PatientCreate,
    doctor_id: Optional[int] = None,
    created_by: Optional[str] = None,
) -> Patient:
    assigned_doc_id = doctor_id if doctor_id is not None else patient_in.doctor_id
    db_patient = Patient(
        name=patient_in.name.strip(),
        age=patient_in.age,
        phone=patient_in.phone.strip(),
        doctor_id=assigned_doc_id,
        is_active=True,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def update_patient(
    db: Session,
    patient: Patient,
    patient_in: PatientUpdate,
    updated_by: Optional[str] = None,
) -> Patient:
    update_data = patient_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"]:
        patient.name = update_data["name"].strip()

    if "age" in update_data and update_data["age"] is not None:
        patient.age = update_data["age"]

    if "phone" in update_data and update_data["phone"]:
        patient.phone = update_data["phone"].strip()

    if "doctor_id" in update_data:
        patient.doctor_id = update_data["doctor_id"]

    if "is_active" in update_data and update_data["is_active"] is not None:
        patient.is_active = update_data["is_active"]

    if updated_by:
        patient.updated_by = updated_by
    patient.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(patient)
    return patient


def soft_delete_patient(
    db: Session,
    patient: Patient,
    updated_by: Optional[str] = None,
) -> Patient:
    patient.is_active = False
    if updated_by:
        patient.updated_by = updated_by
    patient.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patient)
    return patient
