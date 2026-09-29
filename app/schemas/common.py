import math
from typing import Generic, List, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    type: Optional[str] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    code: int
    message: str
    detail: str
    errors: Optional[List[ErrorDetail]] = None


class PaginationMeta(BaseModel):
    total_items: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    # Backward compatibility with existing tests/clients
    items: List[T]
    meta: PaginationMeta

    # Level 6 specification response fields
    total_records: int
    current_page: int
    limit: int
    total_pages: int
    data: List[T]


def make_paginated_response(items: List[T], total: int, page: int, limit: int) -> PaginatedResponse[T]:
    total_pages = math.ceil(total / limit) if (total > 0 and limit > 0) else 0
    meta = PaginationMeta(
        total_items=total,
        page=page,
        page_size=limit,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1 and total_pages > 0,
    )
    return PaginatedResponse(
        items=items,
        meta=meta,
        total_records=total,
        current_page=page,
        limit=limit,
        total_pages=total_pages,
        data=items,
    )
