"""Share card schema (M3.5 §12.8)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ShareCardTotals(BaseModel):
    questions_practiced: int
    correct_count: int
    accuracy: float


class ShareCardStreak(BaseModel):
    current: int
    longest: int


class ShareCardMastery(BaseModel):
    overall_pct: float
    best_subject: dict | None = None  # {subject_id, subject_name, mastery_pct}


class ShareCardWeakPoints(BaseModel):
    weak: int
    consolidating: int


class ShareCardClass(BaseModel):
    id: str
    name: str


class ShareCardExam(BaseModel):
    subject_name: str
    days_left: int


class ShareCardResponse(BaseModel):
    username: str
    generated_at: datetime
    share_card_version: int = 1
    totals: ShareCardTotals
    recent_7d: ShareCardTotals
    streak: ShareCardStreak
    mastery: ShareCardMastery
    weak_points: ShareCardWeakPoints
    class_: ShareCardClass | None = None
    exam: ShareCardExam | None = None
