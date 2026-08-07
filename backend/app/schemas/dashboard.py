"""Dashboard schemas (M3 §11.4/§11.5)."""
from __future__ import annotations

from pydantic import BaseModel


class DashboardTotals(BaseModel):
    questions_practiced: int
    correct_count: int
    accuracy: float


class DashboardMastery(BaseModel):
    leaf_total: int
    mastered: int
    mastery_pct: float


class DashboardStreak(BaseModel):
    current: int
    longest: int


class DashboardWeakPoints(BaseModel):
    weak: int
    consolidating: int


class PerSubjectStat(BaseModel):
    subject_id: str
    subject_name: str
    questions_practiced: int
    correct_count: int
    accuracy: float
    mastery_pct: float


class DashboardExam(BaseModel):
    has_active_plan: bool
    days_left: int | None = None


class DashboardResponse(BaseModel):
    totals: DashboardTotals
    mastery: DashboardMastery
    streak: DashboardStreak
    weak_points: DashboardWeakPoints
    per_subject: list[PerSubjectStat] = []
    exam: DashboardExam


class TrendItem(BaseModel):
    bucket_start: str  # YYYY-MM-DD
    questions_practiced: int
    correct_count: int
    accuracy: float | None = None
    mastered_kp_count: int
    mastery_pct: float


class DashboardTrendResponse(BaseModel):
    granularity: str
    items: list[TrendItem]
