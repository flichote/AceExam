"""Warnings schemas (M3 §11.7)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WarningItem(BaseModel):
    knowledge_point_id: str
    knowledge_point_name: str
    risk_level: str  # high / medium / low
    reasons: list[str]
    suggestion: str
    days_left: int
    accuracy: float
    practice_count: int


class WarningsResponse(BaseModel):
    overall_risk: str | None = None  # high / medium / low / null (no plan)
    items: list[WarningItem] = []
    generated_at: datetime
