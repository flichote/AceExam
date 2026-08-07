"""Sprint (考前突击) schemas (M3 §11.2/§11.3)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SprintActivateResponse(BaseModel):
    sprint: dict  # SprintSession public view
    created: bool


class HighFreqKPItem(BaseModel):
    id: str
    name: str
    heat: int
    avg_accuracy: float
    has_past_exam: bool = False


class SprintSummary(BaseModel):
    high_freq_questions: int
    wrong_review_questions: int
    deduped: int
    total: int


class SprintMockMeta(BaseModel):
    duration_min: int = 120
    total_score: int = 100
    started_at: datetime | None = None


class SprintQuestionsResponse(BaseModel):
    sprint_id: str
    status: str
    days_left: int | None = None
    high_freq_kps: list[HighFreqKPItem] = []
    items: list[dict] = []  # QuestionPublic items (no answer/analysis)
    summary: SprintSummary
    mock: SprintMockMeta | None = None
