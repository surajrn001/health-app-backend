from datetime import datetime, time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserRole
from app.auth.dependencies import get_current_user, get_doctor_profile
from app.schemas.billing import RevenueReportResponse
from app.services import BillingService

router = APIRouter(prefix="/reports", tags=["Reports"])


def _parse_date_bounds(
    from_str: Optional[str],
    to_str: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    start_dt = None
    end_dt = None
    if from_str:
        try:
            if "T" in from_str:
                start_dt = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
            else:
                d = datetime.strptime(from_str, "%Y-%m-%d").date()
                start_dt = datetime.combine(d, time.min)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format for 'from': '{from_str}'. Expected YYYY-MM-DD.",
            )

    if to_str:
        try:
            if "T" in to_str:
                end_dt = datetime.fromisoformat(to_str.replace("Z", "+00:00"))
            else:
                d = datetime.strptime(to_str, "%Y-%m-%d").date()
                end_dt = datetime.combine(d, time.max)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format for 'to': '{to_str}'. Expected YYYY-MM-DD.",
            )

    return start_dt, end_dt


@router.get("/revenue", response_model=RevenueReportResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def get_revenue_report(
    request: Request,
    doctor_id: Optional[int] = Query(None, description="Doctor ID filter"),
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    from_date_alt: Optional[str] = Query(None, alias="from_date", description="Start date alias"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    to_date_alt: Optional[str] = Query(None, alias="to_date", description="End date alias"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate hospital and doctor revenue report (Level 28).
    - Calculates total revenue per doctor and total revenue per day.
    - Admin: Can query all doctors or filter by any doctor.
    - Doctor: Can only query their own revenue.
    """
    effective_doctor_id = doctor_id

    if current_user.role == UserRole.DOCTOR:
        doctor_profile = get_doctor_profile(current_user, db)
        if not doctor_profile:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found",
            )
        if doctor_id is not None and doctor_id != doctor_profile.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view revenue reports for themselves",
            )
        effective_doctor_id = doctor_profile.id
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied to revenue reports",
        )

    start_str = from_date or from_date_alt
    end_str = to_date or to_date_alt
    start_dt, end_dt = _parse_date_bounds(start_str, end_str)

    return BillingService.get_revenue_report(
        db,
        doctor_id=effective_doctor_id,
        from_date=start_dt,
        to_date=end_dt,
    )
