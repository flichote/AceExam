"""OCR schemas -- photo upload + polling (M2)."""
from datetime import datetime

from pydantic import BaseModel


class OcrStructuredResult(BaseModel):
    type: str
    content: str
    options: list[dict] | None = None
    answer: str | list[str] | None = None
    analysis: str | None = None
    confidence: float = 0.0


class SuggestedKP(BaseModel):
    id: str
    name: str
    score: float


class OcrUploadResponse(BaseModel):
    upload_id: str
    status: str  # pending / parsed / failed
    raw_text: str | None = None
    structured: OcrStructuredResult | None = None
    suggested_kps: list[SuggestedKP] | None = None
    error: str | None = None
    message: str | None = None


class OcrPollResponse(BaseModel):
    upload_id: str
    status: str  # pending / parsed / failed / confirmed
    raw_text: str | None = None
    structured: OcrStructuredResult | None = None
    suggested_kps: list[SuggestedKP] | None = None
    error: str | None = None
