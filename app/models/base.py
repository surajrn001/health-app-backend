from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func


class AuditableMixin:
    """Mixin to provide audit tracking columns for models."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
