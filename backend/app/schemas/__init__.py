"""Pydantic v2 schemas — shared types."""
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str | None = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
