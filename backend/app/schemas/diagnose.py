"""Diagnose schemas -- self-test + report (M2)."""
from datetime import datetime

from pydantic import BaseModel, Field


class SelfTestRequest(BaseModel):
    subject_id: str
    count: int = Field(default=10, ge=5, le=20)
    include_weak: bool = True


class SelfTestQuestionItem(BaseModel):
    id: str
    knowledge_point_id: str
    type: str
    content: str
    options: list[dict] | None = None
    difficulty: int


class ChapterCoverage(BaseModel):
    chapter_id: str
    chapter_name: str
    questions: int


class SelfTestResponse(BaseModel):
    report_id: str
    subject_id: str
    status: str  # "in_progress"
    questions: list[SelfTestQuestionItem]
    coverage: list[ChapterCoverage]


class SelfTestStatusResponse(BaseModel):
    report_id: str
    subject_id: str
    status: str  # "in_progress" | "completed"
    questions: list[SelfTestQuestionItem] | None = None
    weak_top5: list[dict] | None = None


class ReportAnswer(BaseModel):
    question_id: str
    answer: str | list[str]


class ReportRequest(BaseModel):
    report_id: str
    answers: list[ReportAnswer]


class WeakTopItem(BaseModel):
    rank: int
    knowledge_point_id: str
    knowledge_point_name: str
    level: int
    accuracy: float
    practice_count: int
    status: str
    suggestion: str


class StrengthItem(BaseModel):
    knowledge_point_name: str
    accuracy: float


class NotStartedItem(BaseModel):
    knowledge_point_name: str
    level: int


class ReportResponse(BaseModel):
    report_id: str
    status: str  # "completed"
    summary: str
    weak_top5: list[WeakTopItem]
    strengths: list[StrengthItem]
    not_started: list[NotStartedItem]
    suggested_next_steps: list[str]
