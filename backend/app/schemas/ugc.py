"""UGC schemas (M3.5 §12.3~§12.5 + M5 §14.5~§14.6)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── M3.5: UGC question submission ──


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


# ── M5: UGC upload + AI review ──


class AIReviewResult(BaseModel):
    """AI 初审结果（T31 ugc_review 服务返回契约，M5 接口占位）。"""

    verdict: str  # pass | flag
    confidence: float  # 0~1
    reasons: list[str] = Field(default_factory=list)


class UGCUploadRequest(BaseModel):
    """M5 POST /ugc/upload 请求体（api.md §14.5）。"""

    subject_id: UUID
    knowledge_point_id: UUID
    type: str = "single"
    content: str = Field(..., min_length=15, description="题干 ≥15 字")
    options: list[dict] | None = None
    answer: str | list[str] | None = None
    analysis: str | None = None
    ocr_upload_id: UUID | None = None
    skip_ai_review: bool = False


class UGCUploadResponse(BaseModel):
    """M5 POST /ugc/upload 响应（api.md §14.5）。"""

    question_id: str
    status: str  # pending | active
    duplicated: bool = False
    ai_review: AIReviewResult | None = None


class UgcStatusItem(BaseModel):
    """M5 GET /ugc/status 单条（api.md §14.6）。"""

    question_id: str
    subject_id: str
    subject_name: str
    knowledge_point_id: str
    knowledge_point_name: str
    type: str
    content: str  # 截断 50 字，由 API 层做
    status: str  # pending | active | rejected
    reject_reason: str | None = None
    ai_review: AIReviewResult | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None


class UgcStatusListResponse(BaseModel):
    """GET /ugc/status 响应（统一分页）。"""

    items: list[UgcStatusItem]
    page: int
    page_size: int
    total: int
