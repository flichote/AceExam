"""M4 选课/广场 schemas — ProfileUpdate / SubjectIdsUpdate / UserSubjectItem / PlazaSubject."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """PUT /me/profile 请求体：更新专业。

    api.md §13.1：major 为自由文本 1..100，允许置空（"" 或 None 均表示清除）。
    """

    major: str | None = Field(
        default=None,
        min_length=0,
        max_length=100,
        description="专业名称，空串或 None 表示清除",
    )


class SubjectIdsUpdate(BaseModel):
    """PUT /me/subjects 请求体：全量覆盖本学期课程列表。

    api.md §13.2：幂等覆盖，可为空数组（= 本学期不选课）。
    """

    subject_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="科目 ID 列表，重复 ID 自动去重",
    )


class SubjectBrief(BaseModel):
    """科目简要信息（嵌入 UserSubjectItem）。"""

    id: str
    code: str
    name: str
    description: str | None = None
    is_public: bool = False
    is_active: bool = True


class SubjectStats(BaseModel):
    """学习统计快照（实时聚合，不落表）。"""

    question_count: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    mastery: float = 0.0
    knowledge_points: dict = Field(default_factory=lambda: {"total": 0, "mastered": 0, "weak": 0})
    streak: int = 0


class UserSubjectItem(BaseModel):
    """GET /me/subjects 单条课程（含学习状态）。"""

    subject: SubjectBrief
    joined_at: datetime | None = None
    stats: SubjectStats = Field(default_factory=SubjectStats)


class UserSubjectListResponse(BaseModel):
    """GET /me/subjects 响应。"""

    items: list[UserSubjectItem]
    total: int


class PlazaSubject(BaseModel):
    """GET /subjects/plaza 单条广场课程。

    api.md §13.4：joined = 当前用户是否已加入（未登录恒 false）。
    """

    id: str
    code: str
    name: str
    description: str | None = None
    is_public: bool = True
    is_active: bool = True
    joined: bool = False
    question_count: int = 0


class PlazaListResponse(BaseModel):
    """GET /subjects/plaza 响应。"""

    items: list[PlazaSubject]
    total: int
