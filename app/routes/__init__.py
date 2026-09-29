from fastapi import APIRouter
from app.routes.auth import router as auth_router
from app.routes.doctors import router as doctors_router
from app.routes.patients import router as patients_router
from app.routes.appointments import router as appointments_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(doctors_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(appointments_router)

__all__ = [
    "auth_router",
    "doctors_router",
    "patients_router",
    "appointments_router",
    "api_v1_router",
]
