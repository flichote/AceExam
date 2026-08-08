"""M5 course schemas — 课程别名、匹配、校本课程录入 (api.md §14.1~§14.4)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── 14.1 GET /courses/aliases ──


class CourseAliasItem(BaseModel):
    """课程别名联想条目。"""

    alias: str
    template_subject_id: str
    template_name: str
    template_code: str
    source: str  # seed | ai | manual
    is_verified: bool


class CourseAliasListResponse(BaseModel):
    items: list[CourseAliasItem]
    total: int


# ── 14.2 POST /courses/match ──


class CourseMatchRequest(BaseModel):
    """校本课程名 → 匹配模板课程请求。"""

    name: str = Field(..., min_length=1, max_length=100)
    school: str | None = Field(default=None, max_length=100)
    textbook: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class CourseMatchCandidate(BaseModel):
    """匹配候选条目。"""

    template_subject_id: str
    name: str
    code: str
    confidence: float
    reason: str
    source: str  # alias | ai | manual


class CourseMatchResponse(BaseModel):
    """课程匹配响应。"""

    matched: bool
    candidates: list[CourseMatchCandidate]
    strategy: str  # alias | ai | manual


# ── 14.3 POST /me/courses ──


class CourseCreateRequest(BaseModel):
    """录入校本课程实例请求。"""

    name: str = Field(..., min_length=1, max_length=100)
    school: str | None = Field(default=None, max_length=100)
    template_subject_id: str | None = None


class UserCourseSubjectBrief(BaseModel):
    """课程简要信息。"""

    id: str
    code: str
    name: str
    description: str | None = None
    level: str | None = None
    is_active: bool = True
    is_public: bool = False


class UserCourseUserSubject(BaseModel):
    """用户课程关联信息。"""

    user_id: str
    subject_id: str
    template_subject_id: str | None = None
    created_at: datetime


class UserCourseResponse(BaseModel):
    """录入/获取我的课程响应。"""

    user_subject: UserCourseUserSubject
    subject: UserCourseSubjectBrief
    matched: bool


class UserCourseListResponse(BaseModel):
    """GET /me/courses 响应。"""

    items: list[UserCourseResponse]
    total: int
