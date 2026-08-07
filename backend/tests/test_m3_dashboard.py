"""M3 学习数据看板验收测试 — GET /me/dashboard + GET /me/dashboard/trend。

验收点（docs/design/flows.md / architecture.md §11.4/§11.5）：
- /me/dashboard 汇总正确性：totals（做题量/正确数/正确率）、mastery（叶子掌握率）、
  streak（当前/最长连胜）、weak_points、per_subject 分解、exam（计划与倒计时）
- /me/dashboard/trend 时间序列：按日/周/月分桶、空数据边界（全 0 / accuracy=None）

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_dashboard.py -v --tb=short -p no:warnings
"""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import KnowledgePoint, Plan, StudySession, Subject, User, UserKnowledgeState
from tests.conftest import _rand

pytestmark = pytest.mark.anyio


def _d(offset: int) -> date:
    return date.today() + timedelta(days=offset)


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


async def _seed_subject(db, name: str = "看板科目") -> dict:
    s = Subject(code=_rand("dash"), name=name, description="", config={})
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": str(s.id), "name": s.name}


async def _seed_leaf_kp(db, subject_id: str, name: str) -> str:
    kp = KnowledgePoint(subject_id=uuid.UUID(subject_id), name=name, content="", level=3)
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    return str(kp.id)


async def _seed_state(db, user_id, kp_id: str, subject_id: str, status: str, correct: int, wrong: int) -> None:
    db.add(UserKnowledgeState(
        user_id=user_id, knowledge_point_id=uuid.UUID(kp_id), subject_id=uuid.UUID(subject_id),
        status=status, correct_count=correct, wrong_count=wrong, streak=0,
    ))
    await db.commit()


async def _seed_session(db, user_id, subject_id: str, d: date, q: int, c: int, checked_in: bool = True) -> None:
    db.add(StudySession(
        user_id=user_id, subject_id=uuid.UUID(subject_id), session_date=d,
        questions_practiced=q, correct_count=c, checked_in=checked_in,
    ))
    await db.commit()


async def _seed_plan(db, user_id, subject_id: str, exam_date: date) -> None:
    db.add(Plan(
        user_id=user_id, subject_id=uuid.UUID(subject_id), title="期末计划",
        exam_date=exam_date, status="active", config={},
    ))
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════
# 1. /me/dashboard 汇总正确性
# ═══════════════════════════════════════════════════════════════════════

class TestDashboardSummary:
    async def test_totals_mastery_streak_weak_exam(
        self, client: AsyncClient, db_session, registered_user
    ):
        """汇总各字段：totals 求和、mastery 叶子掌握率、streak 连续、weak_points、exam 倒计时。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)

        kp_ids = [await _seed_leaf_kp(db_session, subj["id"], f"KP{i}") for i in range(4)]
        await _seed_state(db_session, uid, kp_ids[0], subj["id"], "mastered", 20, 1)
        await _seed_state(db_session, uid, kp_ids[1], subj["id"], "weak", 2, 8)
        await _seed_state(db_session, uid, kp_ids[2], subj["id"], "consolidating", 5, 5)
        # kp_ids[3] 无状态 → untouched

        # 连续 3 天打卡：today-2/today-1/today，合计 q=20 c=16
        await _seed_session(db_session, uid, subj["id"], _d(-2), 1, 1)
        await _seed_session(db_session, uid, subj["id"], _d(-1), 1, 1)
        await _seed_session(db_session, uid, subj["id"], _d(0), 18, 14)

        await _seed_plan(db_session, uid, subj["id"], _d(20))

        resp = await client.get("/api/v1/me/dashboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["totals"] == {"questions_practiced": 20, "correct_count": 16, "accuracy": 0.8}
        assert data["mastery"] == {"leaf_total": 4, "mastered": 1, "mastery_pct": 0.25}
        assert data["streak"] == {"current": 3, "longest": 3}
        assert data["weak_points"] == {"weak": 1, "consolidating": 1}
        assert data["exam"] == {"has_active_plan": True, "days_left": 20}

        assert len(data["per_subject"]) == 1
        ps = data["per_subject"][0]
        assert ps["subject_id"] == subj["id"]
        assert ps["subject_name"] == subj["name"]
        assert ps["questions_practiced"] == 20
        assert ps["correct_count"] == 16
        assert ps["accuracy"] == 0.8
        assert ps["mastery_pct"] == 0.25

    async def test_streak_interrupted_longest_kept(
        self, client: AsyncClient, db_session, registered_user
    ):
        """中断判定：today-2 断档 → current 只数最近连续段，longest 保留最长段。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        # 两段：today-6/today-5（2 天），today-2/today-1/today（3 天）
        await _seed_session(db_session, uid, subj["id"], _d(-6), 1, 1)
        await _seed_session(db_session, uid, subj["id"], _d(-5), 1, 1)
        await _seed_session(db_session, uid, subj["id"], _d(-2), 1, 1)
        await _seed_session(db_session, uid, subj["id"], _d(-1), 1, 1)
        await _seed_session(db_session, uid, subj["id"], _d(0), 1, 1)

        resp = await client.get("/api/v1/me/dashboard", headers=headers)
        assert resp.status_code == 200
        streak = resp.json()["streak"]
        assert streak["current"] == 3
        assert streak["longest"] == 3

    async def test_accuracy_zero_when_no_practice(
        self, client: AsyncClient, registered_user
    ):
        """无练习数据 → accuracy=0.0（非除零错误）。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/me/dashboard", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["totals"]["accuracy"] == 0.0
        assert resp.json()["totals"]["questions_practiced"] == 0

    async def test_per_subject_breakdown_and_filter(
        self, client: AsyncClient, db_session, registered_user
    ):
        """多科目 per_subject 分解 + subject_id 过滤只统计该科目。"""
        s1 = await _seed_subject(db_session, "高数")
        s2 = await _seed_subject(db_session, "线代")
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        # 不同日期避免 (user_id, session_date) 唯一冲突
        await _seed_session(db_session, uid, s1["id"], _d(-2), 5, 4)
        await _seed_session(db_session, uid, s1["id"], _d(-1), 5, 4)
        await _seed_session(db_session, uid, s2["id"], _d(0), 10, 9)

        resp = await client.get("/api/v1/me/dashboard", headers=headers)
        assert resp.status_code == 200
        per = {p["subject_name"]: p for p in resp.json()["per_subject"]}
        assert set(per.keys()) == {"高数", "线代"}
        assert per["高数"]["questions_practiced"] == 10
        assert per["高数"]["correct_count"] == 8
        assert per["高数"]["accuracy"] == 0.8
        assert per["线代"]["questions_practiced"] == 10
        assert per["线代"]["accuracy"] == 0.9

        resp2 = await client.get(
            f"/api/v1/me/dashboard?subject_id={s1['id']}", headers=headers,
        )
        d2 = resp2.json()
        assert d2["totals"]["questions_practiced"] == 10
        assert d2["totals"]["correct_count"] == 8
        # subject 过滤下不返回 per_subject 分解
        assert d2["per_subject"] == []

    async def test_dashboard_subject_with_no_kps_no_breakdown(
        self, client: AsyncClient, db_session, registered_user
    ):
        """无叶子知识点科目：mastery_pct=0、per_subject 不炸。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_session(db_session, uid, subj["id"], _d(0), 3, 2)

        resp = await client.get(
            f"/api/v1/me/dashboard?subject_id={subj['id']}", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mastery"]["leaf_total"] == 0
        assert data["mastery"]["mastery_pct"] == 0.0
        assert data["totals"]["questions_practiced"] == 3


# ═══════════════════════════════════════════════════════════════════════
# 2. /me/dashboard/trend 时间序列
# ═══════════════════════════════════════════════════════════════════════

class TestDashboardTrend:
    async def test_trend_day_bucketing(
        self, client: AsyncClient, db_session, registered_user
    ):
        """按日分桶：区间长度=days、命中桶数据正确、空桶 accuracy=None。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_session(db_session, uid, subj["id"], _d(-5), 10, 6)
        await _seed_session(db_session, uid, subj["id"], _d(-3), 2, 0)
        await _seed_session(db_session, uid, subj["id"], _d(0), 5, 4)

        resp = await client.get(
            f"/api/v1/me/dashboard/trend?days=7&subject_id={subj['id']}", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "day"
        items = data["items"]
        assert len(items) == 7
        # 桶起点 = 今天-6
        assert items[0]["bucket_start"] == _d(-6).isoformat()

        by_date = {it["bucket_start"]: it for it in items}
        assert by_date[_d(-5).isoformat()]["questions_practiced"] == 10
        assert by_date[_d(-5).isoformat()]["correct_count"] == 6
        assert by_date[_d(-5).isoformat()]["accuracy"] == 0.6
        assert by_date[_d(-3).isoformat()]["questions_practiced"] == 2
        assert by_date[_d(-3).isoformat()]["accuracy"] == 0.0
        assert by_date[_d(0).isoformat()]["questions_practiced"] == 5
        assert by_date[_d(0).isoformat()]["accuracy"] == 0.8
        # 空桶
        assert by_date[_d(-6).isoformat()]["questions_practiced"] == 0
        assert by_date[_d(-6).isoformat()]["accuracy"] is None
        # 字段齐全
        for it in items:
            assert "mastered_kp_count" in it
            assert "mastery_pct" in it

    async def test_trend_empty_data_boundary(
        self, client: AsyncClient, registered_user
    ):
        """空数据边界：无任何 session → 每天 0 题 / accuracy=None / mastery_pct=0。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/me/dashboard/trend?days=7", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 7
        for it in items:
            assert it["questions_practiced"] == 0
            assert it["correct_count"] == 0
            assert it["accuracy"] is None
            assert it["mastery_pct"] == 0.0

    async def test_trend_week_granularity(
        self, client: AsyncClient, db_session, registered_user
    ):
        """周粒度：分桶数为覆盖天数所需周数，桶起点严格递增。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_session(db_session, uid, subj["id"], _d(0), 5, 4)

        resp = await client.get(
            f"/api/v1/me/dashboard/trend?days=30&granularity=week&subject_id={subj['id']}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "week"
        items = data["items"]
        assert 1 <= len(items) <= 6
        starts = [it["bucket_start"] for it in items]
        assert starts == sorted(starts)
        # 今天所在周桶有数据
        assert any(it["questions_practiced"] == 5 for it in items)

    async def test_trend_month_granularity(
        self, client: AsyncClient, registered_user
    ):
        """月粒度：正常返回且桶起点递增。"""
        _, _, _, headers = registered_user
        resp = await client.get(
            "/api/v1/me/dashboard/trend?days=90&granularity=month", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "month"
        assert len(data["items"]) >= 1

    async def test_trend_days_bounds(self, client: AsyncClient, registered_user):
        """days 参数越界 → 422。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/me/dashboard/trend?days=0", headers=headers)
        assert resp.status_code == 422
        resp = await client.get("/api/v1/me/dashboard/trend?days=181", headers=headers)
        assert resp.status_code == 422
