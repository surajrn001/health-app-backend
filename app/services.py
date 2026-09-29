"""Business logic and domain services for the application."""
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.doctor_patient import DoctorPatient
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.doctor import DoctorCreate, DoctorUpdate
from app.schemas.patient import PatientCreate, PatientUpdate
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
import app.crud.crud_doctor as crud_doctor
import app.crud.crud_patient as crud_patient
import app.crud.crud_assignment as crud_assignment
import app.crud.crud_appointment as crud_appointment
import app.crud.crud_user as crud_user


class DoctorService:
    @staticmethod
    def get_doctor(db: Session, doctor_id: int) -> Optional[Doctor]:
        return crud_doctor.get_doctor(db, doctor_id)

    @staticmethod
    def get_doctor_by_email(db: Session, email: str) -> Optional[Doctor]:
        return crud_doctor.get_doctor_by_email(db, email)

    @staticmethod
    def get_doctors(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        specialization: Optional[str] = None,
    ) -> Tuple[List[Doctor], int]:
        return crud_doctor.get_doctors(
            db,
            skip=skip,
            limit=limit,
            is_active=is_active,
            search=search,
            specialization=specialization,
        )

    @staticmethod
    def create_doctor(
        db: Session,
        doctor_in: DoctorCreate,
        created_by: Optional[str] = None,
    ) -> Doctor:
        return crud_doctor.create_doctor(db, doctor_in, created_by=created_by)

    @staticmethod
    def update_doctor(
        db: Session,
        doctor: Doctor,
        doctor_in: DoctorUpdate,
        updated_by: Optional[str] = None,
    ) -> Doctor:
        return crud_doctor.update_doctor(db, doctor, doctor_in, updated_by=updated_by)

    @staticmethod
    def soft_delete_doctor(
        db: Session,
        doctor: Doctor,
        updated_by: Optional[str] = None,
    ) -> Doctor:
        return crud_doctor.soft_delete_doctor(db, doctor, updated_by=updated_by)


class PatientService:
    @staticmethod
    def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
        return crud_patient.get_patient(db, patient_id)

    @staticmethod
    def get_patients(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        age_gt: Optional[int] = None,
        doctor_id: Optional[int] = None,
    ) -> Tuple[List[Patient], int]:
        return crud_patient.get_patients(
            db,
            skip=skip,
            limit=limit,
            is_active=is_active,
            search=search,
            age_gt=age_gt,
            doctor_id=doctor_id,
        )

    @staticmethod
    def create_patient(
        db: Session,
        patient_in: PatientCreate,
        doctor_id: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> Patient:
        return crud_patient.create_patient(
            db,
            patient_in,
            doctor_id=doctor_id,
            created_by=created_by,
        )

    @staticmethod
    def update_patient(
        db: Session,
        patient: Patient,
        patient_in: PatientUpdate,
        updated_by: Optional[str] = None,
    ) -> Patient:
        return crud_patient.update_patient(db, patient, patient_in, updated_by=updated_by)

    @staticmethod
    def soft_delete_patient(
        db: Session,
        patient: Patient,
        updated_by: Optional[str] = None,
    ) -> Patient:
        return crud_patient.soft_delete_patient(db, patient, updated_by=updated_by)


class AssignmentService:
    @staticmethod
    def assign_patient_to_doctor(
        db: Session,
        doctor_id: int,
        patient_id: int,
    ) -> Tuple[Doctor, Patient, DoctorPatient]:
        return crud_assignment.assign_patient_to_doctor(db, doctor_id, patient_id)

    @staticmethod
    def get_doctor_patients(
        db: Session,
        doctor_id: int,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
        age_gt: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Patient], int]:
        return crud_assignment.get_doctor_patients(
            db,
            doctor_id,
            skip=skip,
            limit=limit,
            is_active=is_active,
            age_gt=age_gt,
            search=search,
        )

    @staticmethod
    def is_patient_assigned_to_doctor(db: Session, doctor_id: int, patient_id: int) -> bool:
        return crud_assignment.is_patient_assigned_to_doctor(db, doctor_id, patient_id)


class AppointmentService:
    @staticmethod
    def get_appointment(db: Session, appointment_id: int) -> Optional[Appointment]:
        return crud_appointment.get_appointment(db, appointment_id)

    @staticmethod
    def get_appointments(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        doctor_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        status_filter: Optional[AppointmentStatus] = None,
        appointment_date: Optional[datetime] = None,
    ) -> Tuple[List[Appointment], int]:
        return crud_appointment.get_appointments(
            db,
            skip=skip,
            limit=limit,
            doctor_id=doctor_id,
            patient_id=patient_id,
            status_filter=status_filter,
            appointment_date=appointment_date,
        )

    @staticmethod
    def create_appointment(
        db: Session,
        appointment_in: AppointmentCreate,
        resolved_doctor_id: int,
        created_by: Optional[str] = None,
    ) -> Appointment:
        return crud_appointment.create_appointment(
            db,
            appointment_in,
            resolved_doctor_id=resolved_doctor_id,
            created_by=created_by,
        )

    @staticmethod
    def update_appointment(
        db: Session,
        appointment: Appointment,
        appointment_in: AppointmentUpdate,
        updated_by: Optional[str] = None,
    ) -> Appointment:
        return crud_appointment.update_appointment(
            db,
            appointment,
            appointment_in,
            updated_by=updated_by,
        )

    @staticmethod
    def delete_appointment(db: Session, appointment: Appointment) -> Appointment:
        return crud_appointment.delete_appointment(db, appointment)

    @staticmethod
    def check_overlapping(
        db: Session,
        doctor_id: int,
        appointment_date: datetime,
        exclude_id: Optional[int] = None,
    ) -> Optional[Appointment]:
        return crud_appointment.check_overlapping_appointment(
            db,
            doctor_id,
            appointment_date,
            exclude_id=exclude_id,
        )


class UserService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return crud_user.get_user_by_email(db, email)

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return crud_user.get_user_by_id(db, user_id)
