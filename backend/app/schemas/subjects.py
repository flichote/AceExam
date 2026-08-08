"""Subject & KnowledgePoint schemas."""
from pydantic import BaseModel


class SubjectCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    config: dict | None = None


class SubjectResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    is_active: bool
    is_public: bool = False
    sort_order: int
    config: dict | None = None


class KnowledgePointResponse(BaseModel):
    id: str
    subject_id: str
    parent_id: str | None = None
    name: str
    content: str | None = None
    level: int
    sort_order: int


class KnowledgePointTreeResponse(BaseModel):
    id: str
    name: str
    level: int
    children: list["KnowledgePointTreeResponse"] = []
