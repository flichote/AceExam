"""Leaderboard schemas (M3 §11.6 / M3.5 §12.7)."""
from __future__ import annotations

from pydantic import BaseModel


class LeaderboardItem(BaseModel):
    rank: int
    user_id: str
    username: str
    total_correct: int
    questions_practiced: int
    accuracy: float
    current_streak: int


class LeaderboardMe(BaseModel):
    rank: int | None = None
    total_correct: int
    questions_practiced: int
    accuracy: float


class ClassMeta(BaseModel):
    """班级元信息（scope=class 时返回）"""
    id: str
    name: str
    member_count: int


class LeaderboardResponse(BaseModel):
    scope: str
    items: list[LeaderboardItem]
    page: int
    page_size: int
    total: int
    me: LeaderboardMe | None = None
    class_: ClassMeta | None = None  # M3.5: scope=class 时携带
