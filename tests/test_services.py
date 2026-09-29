import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from app.services import DoctorService, PatientService, AssignmentService, AppointmentService, UserService
from app.schemas.doctor import DoctorCreate, DoctorUpdate
from app.schemas.patient import PatientCreate, PatientUpdate
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient


def test_doctor_service_crud(db_session):
    # Create doctor
    doc_in = DoctorCreate(
        name="Dr. Service Test",
        specialization="Pediatrics",
        email="service.doc@healthapp.com",
    )
    doc = DoctorService.create_doctor(db_session, doc_in, created_by="admin@healthapp.com")
    assert doc.id is not None
    assert doc.created_by == "admin@healthapp.com"

    # Get doctor by id and email
    fetched = DoctorService.get_doctor(db_session, doc.id)
    assert fetched.name == "Dr. Service Test"
    by_email = DoctorService.get_doctor_by_email(db_session, "service.doc@healthapp.com")
    assert by_email.id == doc.id

    # Update doctor
    update_in = DoctorUpdate(specialization="General Pediatrics")
    updated = DoctorService.update_doctor(db_session, doc, update_in, updated_by="admin@healthapp.com")
    assert updated.specialization == "General Pediatrics"
    assert updated.updated_by == "admin@healthapp.com"

    # Soft delete doctor
    deleted = DoctorService.soft_delete_doctor(db_session, doc, updated_by="admin@healthapp.com")
    assert deleted.is_active is False

    # List doctors
    docs, total = DoctorService.get_doctors(db_session, is_active=False)
    assert total >= 1


def test_patient_service_crud(db_session):
    # Create patient
    p_in = PatientCreate(
        name="Patient Service Test",
        age=35,
        phone="9876543210",
    )
    pat = PatientService.create_patient(db_session, p_in, created_by="doctor@healthapp.com")
    assert pat.id is not None
    assert pat.created_by == "doctor@healthapp.com"

    # Get patient
    fetched = PatientService.get_patient(db_session, pat.id)
    assert fetched.name == "Patient Service Test"

    # Update patient
    up_in = PatientUpdate(age=36)
    updated = PatientService.update_patient(db_session, pat, up_in, updated_by="doctor@healthapp.com")
    assert updated.age == 36

    # Soft delete
    deleted = PatientService.soft_delete_patient(db_session, pat, updated_by="doctor@healthapp.com")
    assert deleted.is_active is False


def test_appointment_service_logic(db_session):
    doc_in = DoctorCreate(name="Dr. Appt Service", specialization="Cardiology", email="appt.service@healthapp.com")
    doc = DoctorService.create_doctor(db_session, doc_in)

    p_in = PatientCreate(name="Appt Service Patient", age=40, phone="1234567890")
    pat = PatientService.create_patient(db_session, p_in)

    appt_date = datetime.now(timezone.utc) + timedelta(days=2)
    appt_in = AppointmentCreate(
        patient_id=pat.id,
        appointment_date=appt_date,
        status=AppointmentStatus.SCHEDULED,
    )

    # Create appointment
    appt = AppointmentService.create_appointment(
        db_session,
        appt_in,
        resolved_doctor_id=doc.id,
        created_by="admin@healthapp.com",
    )
    assert appt.id is not None
    assert appt.doctor_id == doc.id
    assert appt.patient_id == pat.id

    # Check overlap detection
    overlap = AppointmentService.check_overlapping(db_session, doc.id, appt_date)
    assert overlap is not None
    assert overlap.id == appt.id

    # Different time does not overlap
    no_overlap = AppointmentService.check_overlapping(db_session, doc.id, appt_date + timedelta(hours=3))
    assert no_overlap is None

    # Overlapping create raises HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        AppointmentService.create_appointment(
            db_session,
            appt_in,
            resolved_doctor_id=doc.id,
            created_by="admin@healthapp.com",
        )
    assert exc_info.value.status_code == 400


def test_user_service(db_session):
    user = UserService.get_user_by_email(db_session, "nonexistent@healthapp.com")
    assert user is None
