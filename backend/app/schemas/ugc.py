"""UGC schemas (M3.5 §12.3~§12.5)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UGCQuestionRequest(BaseModel):
    subject_id: UUID
    knowledge_point_id: UUID
    type: str = "single"
    content: str = Field(..., min_length=15, description="题干 ≥15 字")
    options: list[dict] | None = None
    answer: str | list[str] | None = None
    analysis: str | None = None
    ocr_upload_id: UUID | None = None


class UGCQuestionResponse(BaseModel):
    question_id: str
    status: str
    duplicated: bool = False


class UGCSubmittedBy(BaseModel):
    user_id: str
    username: str


class UGCQuestionItem(BaseModel):
    question_id: str
    subject_id: str
    subject_name: str
    knowledge_point_id: str
    knowledge_point_name: str
    type: str
    content: str
    options: list[dict] | None = None
    answer: str | list[str] | None = None
    analysis: str | None = None
    submitted_by: UGCSubmittedBy | None = None
    status: str
    created_at: datetime
    reject_reason: str | None = None


class UGCReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    reject_reason: str | None = Field(default=None, min_length=5)


class UGCReviewResponse(BaseModel):
    question_id: str
    status: str
    reviewed_at: datetime
