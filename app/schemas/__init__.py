from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    Token,
    TokenPayload,
)
from app.schemas.doctor import (
    DoctorBase,
    DoctorCreate,
    DoctorUpdate,
    DoctorResponse,
    DoctorDetailResponse,
    PatientSummary,
)
from app.schemas.patient import (
    PatientBase,
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientDetailResponse,
    DoctorSummary,
)
from app.schemas.appointment import (
    AppointmentBase,
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AppointmentStatus,
)
from app.schemas.assignment import DoctorPatientAssignmentResponse
from app.schemas.common import (
    MessageResponse,
    ErrorResponse,
    ErrorDetail,
    PaginationMeta,
    PaginatedResponse,
    make_paginated_response,
)

# Aliases for backward compatibility
UserCreate = UserRegister
UserBase = UserRegister
TokenResponse = Token

__all__ = [
    "UserRegister",
    "UserCreate",
    "UserBase",
    "UserLogin",
    "UserResponse",
    "Token",
    "TokenResponse",
    "TokenPayload",
    "DoctorBase",
    "DoctorCreate",
    "DoctorUpdate",
    "DoctorResponse",
    "DoctorDetailResponse",
    "PatientSummary",
    "PatientBase",
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "PatientDetailResponse",
    "DoctorSummary",
    "AppointmentBase",
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentResponse",
    "AppointmentStatus",
    "DoctorPatientAssignmentResponse",
    "MessageResponse",
    "ErrorResponse",
    "ErrorDetail",
    "PaginationMeta",
    "PaginatedResponse",
    "make_paginated_response",
]
