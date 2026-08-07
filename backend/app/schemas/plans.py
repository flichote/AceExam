"""Plans schemas -- create + active + checkin (M2)."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    subject_id: str
    exam_date: date
    daily_question_target: int = Field(default=10, ge=5, le=50)
    title: str = "Final sprint plan"


class PlanDetail(BaseModel):
    id: str
    subject_id: str
    title: str
    exam_date: date
    days_left: int
    status: str
    daily_question_target: int


class WeakKPItem(BaseModel):
    id: str
    name: str
    status: str
    accuracy: float


class FocusKP(BaseModel):
    id: str
    name: str
    reason: str


class TaskDone(BaseModel):
    questions_practiced: int
    correct_count: int
    checked_in: bool


class TodayTask(BaseModel):
    date: date
    target_questions: int
    focus_kps: list[FocusKP]
    type: str
    reason: str
    done: TaskDone


class PlanCreateResponse(BaseModel):
    plan: PlanDetail
    weak_kps: list[WeakKPItem]
    today_task: TodayTask


class UpcomingTask(BaseModel):
    date: date
    target_questions: int
    focus_kps: list[FocusKP]
    type: str


class ActivePlanResponse(BaseModel):
    plan: PlanDetail | None = None
    today_task: TodayTask | None = None
    upcoming: list[UpcomingTask] = []


class CheckinResponse(BaseModel):
    checked_in: bool = True
    already_checked_in: bool = False
    session: dict | None = None
