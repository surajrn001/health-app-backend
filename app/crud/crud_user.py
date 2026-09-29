from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.doctor import Doctor
from app.schemas.auth import UserRegister
from app.auth.jwt import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, user_in: UserRegister) -> User:
    normalized_email = user_in.email.lower().strip()
    db_user = User(
        email=normalized_email,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    db.add(db_user)
    db.flush()

    if user_in.role == UserRole.DOCTOR:
        doctor_name = user_in.name or f"Dr. {normalized_email.split('@')[0].capitalize()}"
        specialization = user_in.specialization or "General Medicine"
        
        existing_doctor = db.query(Doctor).filter(Doctor.email == normalized_email).first()
        if existing_doctor:
            existing_doctor.user_id = db_user.id
            if user_in.name:
                existing_doctor.name = user_in.name
            if user_in.specialization:
                existing_doctor.specialization = user_in.specialization
        else:
            db_doctor = Doctor(
                name=doctor_name,
                specialization=specialization,
                email=normalized_email,
                is_active=True,
                user_id=db_user.id,
            )
            db.add(db_doctor)

    db.commit()
    db.refresh(db_user)
    return db_user
