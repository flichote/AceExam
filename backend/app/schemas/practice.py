"""Practice schemas -- adaptive question selection + answer submission (M2)."""
from datetime import datetime

from pydantic import BaseModel, Field


class TargetKP(BaseModel):
    id: str
    name: str
    level: int
    status: str
    score: float
    reason: str


class SelectionStrategy(BaseModel):
    target_kps: list[TargetKP]
    weights: dict[str, float]


class PracticeQuestionItem(BaseModel):
    """QuestionPublic -- never includes answer/analysis."""
    id: str
    subject_id: str
    knowledge_point_id: str
    type: str
    content: str
    options: list[dict] | None = None
    difficulty: int
    source: str | None = None
    created_at: datetime


class PracticeQuestionsResponse(BaseModel):
    items: list[PracticeQuestionItem]
    strategy: SelectionStrategy
    requested_at: datetime


class AnswerRequest(BaseModel):
    """Answer submission body."""
    answer: dict | str | list  # single: "C", multi: ["A","C"], blank: "3", essay: text
    time_spent_seconds: int = 0
    source: str = "practice"


class KnowledgeStateSummary(BaseModel):
    status: str
    correct_count: int
    wrong_count: int
    streak: int


class AnswerResponse(BaseModel):
    correct: bool
    correct_answer: dict | str | list | None = None
    analysis: str | None = None
    knowledge_point: dict | None = None
    knowledge_state: KnowledgeStateSummary | None = None
    wrong_answer_id: str | None = None
    explanation_available: bool = False


class OcrConfirmRequest(BaseModel):
    """Confirm OCR result and import to question bank."""
    upload_id: str
    subject_id: str
    knowledge_point_id: str
    structured: dict  # user-edited final question struct
    confirm_answer: bool = True


class OcrConfirmResponse(BaseModel):
    question_id: str
    upload_id: str
    status: str  # "confirmed"
    duplicated: bool = False
