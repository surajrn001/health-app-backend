from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from app.auth.jwt import create_access_token
from app.auth.dependencies import get_current_user, get_doctor_profile
from app.crud.crud_user import get_user_by_email, create_user, authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(
    request: Request,
    response: Response,
    user_in: UserRegister,
    db: Session = Depends(get_db),
):
    if get_user_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = create_user(db, user_in)
    doctor = get_doctor_profile(user, db)

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        doctor_id=doctor.id if doctor else None,
        created_at=user.created_at,
    )


@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(
    request: Request,
    response: Response,
    login_data: UserLogin,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    doctor = get_doctor_profile(user, db)
    doctor_id = doctor.id if doctor else None

    token_payload = {
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
        "doctor_id": doctor_id,
    }
    access_token = create_access_token(
        data=token_payload,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            doctor_id=doctor_id,
            created_at=user.created_at,
        ),
    )


@router.post("/token", response_model=Token, include_in_schema=False)
def login_for_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    doctor = get_doctor_profile(user, db)
    doctor_id = doctor.id if doctor else None

    token_payload = {
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
        "doctor_id": doctor_id,
    }
    access_token = create_access_token(
        data=token_payload,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            doctor_id=doctor_id,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doctor = get_doctor_profile(current_user, db)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        doctor_id=doctor.id if doctor else None,
        created_at=current_user.created_at,
    )
