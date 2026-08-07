"""WrongAnswer schemas."""
from datetime import datetime

from pydantic import BaseModel


class WrongAnswerResponse(BaseModel):
    id: str
    question_id: str
    subject_id: str
    wrong_answer: str | None = None
    wrong_reason: str | None = None
    review_count: int
    mastered: bool
    created_at: datetime
    # Joined fields
    question_content: str | None = None
    knowledge_point_name: str | None = None


class WrongAnswerCreate(BaseModel):
    question_id: str
    subject_id: str
    wrong_answer: str | None = None
    wrong_reason: str | None = None
