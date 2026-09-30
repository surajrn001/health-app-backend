import sys
import os
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import Base, engine, SessionLocal
from app.models.user import User, UserRole
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_patient import DoctorPatient
from app.models.appointment import Appointment, AppointmentStatus
from app.models.billing import Billing, PaymentStatus, PaymentMode
from app.auth.jwt import hash_password


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.query(Doctor).count() > 0:
            print("Database already has records.")
            return

        admin = db.query(User).filter(User.email == "admin@healthapp.com").first()
        if not admin:
            admin = User(
                email="admin@healthapp.com",
                hashed_password=hash_password("AdminPassword123"),
                role=UserRole.ADMIN,
                is_active=True,
                created_by="system",
                updated_by="system",
            )
            db.add(admin)
            db.flush()

        user_doc1 = User(
            email="dr.strange@healthapp.com",
            hashed_password=hash_password("Doctor@123"),
            role=UserRole.DOCTOR,
            is_active=True,
            created_by=admin.email,
            updated_by=admin.email,
        )
        db.add(user_doc1)
        db.flush()

        doc1 = Doctor(
            name="Dr. Stephen Strange",
            specialization="Neuro Surgery",
            email="dr.strange@healthapp.com",
            is_active=True,
            user_id=user_doc1.id,
            created_by=admin.email,
            updated_by=admin.email,
        )
        db.add(doc1)
        db.flush()

        user_doc2 = User(
            email="dr.house@healthapp.com",
            hashed_password=hash_password("Doctor@123"),
            role=UserRole.DOCTOR,
            is_active=True,
            created_by=admin.email,
            updated_by=admin.email,
        )
        db.add(user_doc2)
        db.flush()

        doc2 = Doctor(
            name="Dr. Gregory House",
            specialization="Diagnostic Medicine",
            email="dr.house@healthapp.com",
            is_active=True,
            user_id=user_doc2.id,
            created_by=admin.email,
            updated_by=admin.email,
        )
        db.add(doc2)
        db.flush()

        p1 = Patient(name="John Doe", age=34, phone="9876543210", doctor_id=doc1.id, is_active=True, created_by=admin.email, updated_by=admin.email)
        p2 = Patient(name="Jane Smith", age=29, phone="9876543211", doctor_id=doc1.id, is_active=True, created_by=admin.email, updated_by=admin.email)
        p3 = Patient(name="Robert Brown", age=52, phone="9876543212", doctor_id=doc2.id, is_active=True, created_by=admin.email, updated_by=admin.email)
        p4 = Patient(name="Emily Davis", age=41, phone="9876543213", doctor_id=doc2.id, is_active=True, created_by=admin.email, updated_by=admin.email)
        p5 = Patient(name="Michael Green", age=68, phone="9876543214", is_active=True, created_by=admin.email, updated_by=admin.email)

        db.add_all([p1, p2, p3, p4, p5])
        db.flush()

        a1 = DoctorPatient(doctor_id=doc1.id, patient_id=p1.id)
        a2 = DoctorPatient(doctor_id=doc1.id, patient_id=p2.id)
        a3 = DoctorPatient(doctor_id=doc2.id, patient_id=p3.id)
        a4 = DoctorPatient(doctor_id=doc2.id, patient_id=p4.id)
        db.add_all([a1, a2, a3, a4])

        now = datetime.now(timezone.utc)
        appt1 = Appointment(
            doctor_id=doc1.id,
            patient_id=p1.id,
            appointment_date=now + timedelta(days=1, hours=2),
            status=AppointmentStatus.SCHEDULED,
            created_by=admin.email,
            updated_by=admin.email,
        )
        appt2 = Appointment(
            doctor_id=doc1.id,
            patient_id=p2.id,
            appointment_date=now + timedelta(days=2, hours=4),
            status=AppointmentStatus.SCHEDULED,
            created_by=admin.email,
            updated_by=admin.email,
        )
        appt3 = Appointment(
            doctor_id=doc2.id,
            patient_id=p3.id,
            appointment_date=now + timedelta(days=1, hours=3),
            status=AppointmentStatus.SCHEDULED,
            created_by=admin.email,
            updated_by=admin.email,
        )
        db.add_all([appt1, appt2, appt3])
        db.flush()

        bill1 = Billing(
            patient_id=p1.id,
            doctor_id=doc1.id,
            appointment_id=appt1.id,
            consultation_fee=150.0,
            additional_charges=25.0,
            total_amount=175.0,
            payment_status=PaymentStatus.PAID,
            payment_mode=PaymentMode.CARD,
            is_active=True,
            created_by=admin.email,
            updated_by=admin.email,
        )
        bill2 = Billing(
            patient_id=p2.id,
            doctor_id=doc1.id,
            appointment_id=None,
            consultation_fee=200.0,
            additional_charges=0.0,
            total_amount=200.0,
            payment_status=PaymentStatus.PENDING,
            payment_mode=PaymentMode.CASH,
            is_active=True,
            created_by=user_doc1.email,
            updated_by=user_doc1.email,
        )
        bill3 = Billing(
            patient_id=p3.id,
            doctor_id=doc2.id,
            appointment_id=appt3.id,
            consultation_fee=300.0,
            additional_charges=50.0,
            total_amount=350.0,
            payment_status=PaymentStatus.PAID,
            payment_mode=PaymentMode.UPI,
            is_active=True,
            created_by=user_doc2.email,
            updated_by=user_doc2.email,
        )
        db.add_all([bill1, bill2, bill3])
        db.commit()

        print("Seeding completed successfully with doctors, patients, appointments, and billings.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
