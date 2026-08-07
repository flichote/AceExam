"""Leaderboard schemas (M3 §11.6)."""
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


class LeaderboardResponse(BaseModel):
    scope: str
    items: list[LeaderboardItem]
    page: int
    page_size: int
    total: int
    me: LeaderboardMe | None = None
