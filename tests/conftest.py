import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, UserRole, Doctor, Patient, DoctorPatient, Appointment, AppointmentStatus, Billing, PaymentStatus, PaymentMode
from app.auth.jwt import hash_password, create_access_token
from sqlalchemy import event
from sqlalchemy.engine import Engine

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(db_session, client):
    admin = User(
        email="test_admin@example.com",
        hashed_password=hash_password("AdminPass123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    token = create_access_token({"sub": admin.email, "user_id": admin.id, "role": admin.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def doctor1_fixture(db_session):
    user = User(
        email="doctor1@example.com",
        hashed_password=hash_password("DoctorPass123"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        name="Dr. Stephen Strange",
        specialization="Neuro Surgery",
        email="doctor1@example.com",
        is_active=True,
        user_id=user.id,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    token = create_access_token({
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
        "doctor_id": doctor.id,
    })
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "doctor": doctor, "headers": headers}


@pytest.fixture
def doctor2_fixture(db_session):
    user = User(
        email="doctor2@example.com",
        hashed_password=hash_password("DoctorPass123"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        name="Dr. Gregory House",
        specialization="Diagnostics",
        email="doctor2@example.com",
        is_active=True,
        user_id=user.id,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    token = create_access_token({
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
        "doctor_id": doctor.id,
    })
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "doctor": doctor, "headers": headers}
