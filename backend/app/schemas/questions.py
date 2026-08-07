"""Question schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    type: str = "single"
    content: str
    options: dict | None = None
    answer: dict | None = None
    analysis: str | None = None
    difficulty: int = Field(default=3, ge=1, le=5)
    source: str | None = None
    knowledge_point_id: str | None = None


class QuestionResponse(BaseModel):
    """Returned in lists — never includes answer/analysis."""
    id: str
    subject_id: str
    knowledge_point_id: str | None = None
    type: str
    content: str
    options: dict | None = None
    difficulty: int
    source: str | None = None
    created_at: datetime


class QuestionDetailResponse(QuestionResponse):
    """Includes answer/analysis only after submission."""
    answer: dict | None = None
    analysis: str | None = None


class SubmitAnswerRequest(BaseModel):
    answer: dict


class SubmitAnswerResponse(BaseModel):
    correct: bool
    correct_answer: dict | None = None
    analysis: str | None = None
    wrong_answer_id: str | None = None
