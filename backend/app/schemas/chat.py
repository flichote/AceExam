"""Chat schemas."""
from pydantic import BaseModel


class ChatExplainRequest(BaseModel):
    question_id: str
    followup_session_id: str | None = None


class ChatFollowupRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    steps: list[dict]
    conclusion: str | None = None
    citations: list[dict] = []
    uncovered: bool = False
    model: str = "flash"
