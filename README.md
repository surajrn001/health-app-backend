# Healthcare Management Backend API (Levels 1 – 18)

An enterprise-grade, production-ready healthcare management backend built with **FastAPI**, **SQLAlchemy ORM**, **Pydantic v2**, and **JWT Authentication**. Provides complete management for Doctors, Patients, Assignments, Appointments, Role-Based Access Control (RBAC), Performance Optimization, Auditing, and Global Error Handling.

---

## Tech Stack
- **Python:** 3.9+ (Tested on Python 3.13)
- **Framework:** FastAPI
- **Validation & Serialization:** Pydantic v2
- **ORM & Database:** SQLAlchemy 2.0 & SQLite / PostgreSQL
- **Security & Auth:** PyJWT, Passlib with Bcrypt
- **Rate Limiting:** SlowAPI
- **Testing:** Pytest (58 passing tests with 89% code coverage)
- **ASGI Server:** Uvicorn
- **Containerization:** Docker & Docker Compose

---

## Project Structure (Modular Clean Architecture)

```
Health_app/
├── app/
│   ├── main.py                  # FastAPI application entrypoint with middleware, exception handlers & lifespan
│   ├── config.py                # Environment configuration via pydantic-settings
│   ├── database.py              # SQLite database engine, session local & get_db dependency (foreign key pragma enabled)
│   ├── services.py              # Business logic domain services (DoctorService, PatientService, AppointmentService, etc.)
│   ├── limiter.py               # SlowAPI rate limiter
│   ├── auth/                    # Authentication and RBAC
│   │   ├── jwt.py               # Bcrypt password hashing and JWT token creation/decoding
│   │   └── dependencies.py      # Current user and role dependencies
│   ├── models/                  # SQLAlchemy models
│   │   ├── base.py              # AuditableMixin (created_at, updated_at, created_by, updated_by)
│   │   ├── user.py              # User model (admin/doctor)
│   │   ├── doctor.py            # Doctor model (with patients and appointments relations)
│   │   ├── patient.py           # Patient model (with doctor_id foreign key)
│   │   ├── doctor_patient.py    # Doctor-Patient association
│   │   └── appointment.py       # Appointment model with status lifecycle and composite indexes
│   ├── schemas/                 # Pydantic validation schemas
│   │   ├── auth.py              # Register, Login, Token schemas
│   │   ├── doctor.py            # DoctorCreate, DoctorUpdate, DoctorResponse, DoctorDetailResponse
│   │   ├── patient.py           # PatientCreate, PatientUpdate (10-digit phone regex), PatientResponse
│   │   ├── appointment.py       # AppointmentCreate, AppointmentUpdate, AppointmentResponse
│   │   ├── assignment.py        # Doctor-Patient assignment schemas
│   │   └── common.py            # PaginatedResponse, MessageResponse, ErrorResponse schemas
│   ├── crud/                    # Database CRUD operations
│   │   ├── crud_user.py
│   │   ├── crud_doctor.py
│   │   ├── crud_patient.py
│   │   ├── crud_assignment.py
│   │   └── crud_appointment.py
│   └── routes/                  # API route handlers
│       ├── __init__.py          # Exports api_v1_router and individual routers
│       ├── auth.py              # /auth endpoints
│       ├── doctors.py           # /doctors endpoints
│       ├── patients.py          # /patients endpoints
│       └── appointments.py      # /appointments endpoints
├── alembic/                     # Database migrations
│   └── versions/                # Migration scripts
├── tests/                       # Automated test suite (58 passing tests, 89% coverage)
│   ├── conftest.py              # Test database engine and fixtures
│   ├── test_auth.py             # Authentication & token tests
│   ├── test_doctors.py          # Doctor CRUD, PATCH, filters, versioning tests
│   ├── test_patients.py         # Patient CRUD, PATCH, regex phone, age_gt filter tests
│   ├── test_assignments.py     # Assignment & doctor-patient relationship tests
│   ├── test_appointments.py    # Appointment CRUD, overlaps, and subroutes tests
│   ├── test_roles.py           # Role restrictions (Doctor cannot delete doctors or patients)
│   ├── test_audit_and_hardening.py # Audit fields, response time, and error format tests
│   └── test_services.py        # Service layer unit tests
├── .env.example                 # Environment variables template
├── .env                         # Local environment configuration
├── Dockerfile                   # Multi-stage production Dockerfile
├── docker-compose.yml           # Docker Compose definition
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Project dependencies
├── seed_data.py                 # Sample database seeder
└── README.md
```

---

## Implemented Enhancements by Level

### Level 11: Role-Based Authorization (RBAC)
- Enhanced JWT authentication with claims for `role` (`admin`, `doctor`), `user_id`, and `doctor_id`.
- **Admin**: Full access across all Doctor, Patient, and Appointment APIs.
- **Doctor**:
  - Can view only their assigned patients (`GET /patients`, `GET /patients/{id}`, `GET /doctors/{id}/patients`).
  - Cannot delete doctors (`DELETE /doctors/{id}` -> HTTP 403 Forbidden).
  - Cannot delete patients (`DELETE /patients/{id}` -> HTTP 403 Forbidden).
  - Returns HTTP 403 Forbidden for any unauthorized boundary breach.

### Level 12: Appointment Module
- **Model**: `appointments` (`id`, `doctor_id`, `patient_id`, `appointment_date`, `status`, `created_at`, `updated_at`, `created_by`, `updated_by`).
- **Status Lifecycle**: `scheduled`, `completed`, `cancelled`.
- **Validation Rules**:
  - Doctor and Patient must exist in the database (HTTP 404).
  - Doctor must be active; Patient must be active (HTTP 400).
  - Overlap Prevention: Blocks overlapping appointments for the same doctor within a 30-minute window unless cancelled.
- **APIs**:
  - Full CRUD: `POST`, `GET`, `GET /{id}`, `PUT /{id}`, `PATCH /{id}`, `DELETE /{id}` under `/api/v1/appointments`.
  - Doctor Appointments: `GET /api/v1/doctors/{doctor_id}/appointments`.
  - Patient Appointments: `GET /api/v1/patients/{patient_id}/appointments`.

### Level 13: Data Integrity & Constraints
- Database-level unique constraints on `doctors.email` and `users.email`.
- SQLite foreign key constraints actively enforced (`PRAGMA foreign_keys = ON;`).
- Cascading delete on appointments (`ondelete="CASCADE"`) when referenced records are deleted.
- Graceful database exception handling (`IntegrityError`, `SQLAlchemyError`) returning clean, user-friendly JSON error messages instead of raw SQL traces.

### Level 14: Performance & Query Optimization
- SQLAlchemy query optimization eliminating N+1 queries using `joinedload` and `selectinload`.
- Database indexes on query fields and composite indexes (`(doctor_id, appointment_date)`, `(doctor_id, is_active)`).
- Custom timing middleware measuring execution duration and attaching `X-Process-Time` and `X-Response-Time` headers.

### Level 15: Audit & Tracking
- `AuditableMixin` providing `created_at`, `updated_at`, `created_by`, `updated_by`.
- Automatically populates `created_by` and `updated_by` with the authenticated JWT user.
- Timestamps automatically updated on record updates.

### Level 16: API Hardening & Reliability
- Global exception handlers for `HTTPException`, `RequestValidationError`, `IntegrityError`, `RateLimitExceeded`, and generic `Exception`.
- Standardized custom error response format:
  ```json
  {
    "status": "error",
    "code": 404,
    "message": "Doctor with id 999 not found",
    "detail": "Doctor with id 999 not found",
    "errors": []
  }
  ```
- SlowAPI rate limiting enabled across all endpoints.

### Level 17: Testing & Coverage
- Comprehensive test suite covering services, validation logic, auth flows, and role restrictions.
- **58 automated tests** passing.
- **89% overall code coverage** (Services: 99%, Schemas: 100%, Appointments: 89%).

### Level 18: Documentation & Maintainability
- OpenAPI tags with rich descriptions.
- Pydantic V2 `json_schema_extra` request and response examples for all schemas.
- Interactive Swagger UI (`/docs`) and ReDoc (`/redoc`).

---

## Setup & Running Instructions

### 1. Local Setup

Create and activate virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\activate
```

Install dependencies:
```powershell
pip install -r requirements.txt
```

Seed initial sample data:
```powershell
python seed_data.py
```

Run development server:
```powershell
uvicorn app.main:app --reload --port 8000
```

### 2. Swagger UI Documentation
Open your browser to:
- **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## Running Automated Tests

Run the test suite with pytest and code coverage:
```powershell
pytest -v --cov=app --cov-report=term-missing
```

Expected result: **58 passed in ~32s** with **89% coverage**.

---

## Default Seed Test Accounts

| Role | Email | Password | Privileges / Assigned Patients |
|---|---|---|---|
| **Admin** | `admin@healthapp.com` | `AdminPassword123` | Full admin privileges across all endpoints |
| **Doctor** | `dr.strange@healthapp.com` | `Doctor@123` | Assigned to John Doe, Jane Smith |
| **Doctor** | `dr.house@healthapp.com` | `Doctor@123` | Assigned to Robert Brown, Emily Davis |
