import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import AuditableMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"


class User(Base, AuditableMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.DOCTOR,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    doctor = relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
    )
