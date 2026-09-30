import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth.jwt import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.limiter import limiter
from app.models import User, UserRole, Doctor, Patient, DoctorPatient, Appointment, Billing
from app.routes import (
    api_v1_router,
    auth_router,
    doctors_router,
    patients_router,
    appointments_router,
    billings_router,
    reports_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s",
)
logger = logging.getLogger("health_app")


def init_db() -> None:
    """Create database tables and ensure a default admin exists."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.query(User).filter(User.role == UserRole.ADMIN).first():
            logger.info("Creating default administrator account...")
            db.add(
                User(
                    email="admin@healthapp.com",
                    hashed_password=hash_password("AdminPassword123"),
                    role=UserRole.ADMIN,
                    is_active=True,
                    created_by="system",
                    updated_by="system",
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Healthcare API service started successfully.")
    yield
    logger.info("Healthcare API service stopped.")


openapi_tags = [
    {
        "name": "Auth",
        "description": "Authentication and authorization operations (JWT tokens, login, user registration).",
    },
    {
        "name": "Doctors",
        "description": "Doctor profile management, patient assignments, and doctor-specific appointments.",
    },
    {
        "name": "Patients",
        "description": "Patient directory management, primary doctor assignments, and appointment history.",
    },
    {
        "name": "Appointments",
        "description": "Appointment scheduling, status lifecycle (scheduled, completed, cancelled), and overlap conflict prevention.",
    },
    {
        "name": "Billings",
        "description": "Billing entity lifecycle, payment tracking, invoices, and doctor/patient financial management.",
    },
    {
        "name": "Reports",
        "description": "Financial reports, aggregated revenue calculations per doctor and per day.",
    },
    {
        "name": "System",
        "description": "System health status and operational metadata.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A robust, enterprise-grade backend for managing healthcare providers, patient records, and appointments.",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting state
app.state.limiter = limiter


# ============================================================================
# Performance & Response Timing Middleware (Level 14)
# ============================================================================
@app.middleware("http")
async def response_time_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000.0

    # Add response headers for performance monitoring
    response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"
    response.headers["X-Response-Time"] = f"{process_time_ms:.2f}ms"

    # Log response duration for list endpoints and slow requests
    if request.method == "GET" or process_time_ms > 100.0:
        logger.info(
            f"HTTP {request.method} {request.url.path} -> Status {response.status_code} "
            f"in {process_time_ms:.2f}ms"
        )
    return response


# ============================================================================
# Global Exception Handlers (Level 13 & Level 16)
# ============================================================================
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Uniform error response for all HTTPExceptions."""
    message = exc.detail if isinstance(exc.detail, str) else "An error occurred"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": message,
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Uniform error response for Pydantic schema validation failures."""
    formatted_errors = []
    for err in exc.errors():
        loc_str = " -> ".join(str(l) for l in err.get("loc", []))
        formatted_errors.append(
            {
                "field": loc_str,
                "message": str(err.get("msg", "Invalid value")),
                "type": str(err.get("type", "value_error")),
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "Request validation failed",
            "detail": jsonable_encoder(exc.errors()),
            "errors": formatted_errors,
        },
    )


@app.exception_handler(IntegrityError)
async def sqlalchemy_integrity_error_handler(request: Request, exc: IntegrityError):
    """Graceful database constraint error handling (Level 13)."""
    logger.warning(f"Database IntegrityError: {str(exc.orig)}")
    err_msg = str(exc.orig).lower()

    if "unique" in err_msg:
        detail = "A record with this unique value already exists."
    elif "foreign key" in err_msg:
        detail = "Referenced entity does not exist or foreign key constraint failed."
    elif "not null" in err_msg:
        detail = "A required database field cannot be null."
    else:
        detail = "Database integrity constraint violation."

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "code": status.HTTP_400_BAD_REQUEST,
            "message": detail,
            "detail": detail,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_generic_error_handler(request: Request, exc: SQLAlchemyError):
    """Gracefully handle any unexpected database errors."""
    logger.error(f"Database error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "A database error occurred while processing your request.",
            "detail": "A database error occurred while processing your request.",
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Uniform rate limit exceeded response."""
    detail = "Rate limit exceeded. Please try again later."
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "status": "error",
            "code": status.HTTP_429_TOO_MANY_REQUESTS,
            "message": detail,
            "detail": detail,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Uniform fallback handler for uncaught server errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "An internal server error occurred.",
            "detail": "An internal server error occurred.",
        },
    )


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Primary API endpoints (v1)
app.include_router(api_v1_router)

# Direct route aliases for root-level access
app.include_router(auth_router, include_in_schema=False)
app.include_router(doctors_router, include_in_schema=False)
app.include_router(patients_router, include_in_schema=False)
app.include_router(appointments_router, include_in_schema=False)
app.include_router(billings_router, include_in_schema=False)
app.include_router(reports_router, include_in_schema=False)


@app.get("/", tags=["System"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}
