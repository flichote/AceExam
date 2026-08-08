"""Classroom schemas (M3.5 §12.6/§12.7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ClassCreateRequest(BaseModel):
    name: str | None = None
    invite_code: str | None = None


class ClassInfo(BaseModel):
    id: str
    name: str
    invite_code: str | None = None  # 仅建班人返回
    member_count: int
    is_creator: bool


class ClassRank(BaseModel):
    rank: int | None = None
    total_correct: int


class MeClassResponse(BaseModel):
    class_: ClassInfo | None = Field(default=None, alias="class")
    my_rank: ClassRank | None = None

    model_config = {"populate_by_name": True}


class JoinClassResponse(BaseModel):
    class_: ClassInfo = Field(alias="class")
    joined: bool = True

    model_config = {"populate_by_name": True}
