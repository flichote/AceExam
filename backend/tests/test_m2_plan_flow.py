"""M2 备考计划端到端验收测试 — 创建 → 今日任务 → 打卡（幂等 + 乐观锁）。

验收点（docs/design/flows.md 流程3 / PRD）：
- 创建计划（会员）→ 今日任务生成（target/focus/done）
- 今日任务随练习进度更新（questions_practiced 累加）
- 打卡状态持久化；重复打卡防抖（already_checked_in）
- 打卡乐观锁：UPDATE ... WHERE checked_in=false，并发下不重复置位
"""
import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.db.models import (
    KnowledgePoint,
    Question,
    StudySession,
    Subject,
)
from app.services.plan_service import get_or_create_session
from tests.conftest import _rand


def _future_date(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


async def _create_plan(client, headers, subject_id: str, title: str = "期末冲刺计划") -> dict:
    resp = await client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "subject_id": subject_id,
            "exam_date": _future_date(30),
            "daily_question_target": 10,
            "title": title,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_question(db, subject_id: str) -> str:
    kp = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="计划测试知识点", content="", level=3)
    db.add(kp)
    await db.flush()
    q = Question(
        subject_id=uuid.UUID(subject_id), knowledge_point_id=kp.id, type="single",
        content="计划测试题：$1+1=$ ?",
        options=[{"key": "A", "text": "$1$"}, {"key": "B", "text": "$2$"}],
        answer="B", analysis="", difficulty=1, source="self_built", status="active",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return str(q.id)


# ═══════════════════════════════════════════════════════════════════════════
# 计划创建
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanCreate:
    async def test_create_plan_member(self, client, member_user, seed_subject):
        _, _, _, headers = member_user
        body = await _create_plan(client, headers, seed_subject["id"])
        assert body["plan"]["status"] == "active"
        assert body["plan"]["days_left"] > 0
        assert body["plan"]["daily_question_target"] == 10
        assert isinstance(body["weak_kps"], list)
        task = body["today_task"]
        assert task["target_questions"] == 10
        assert task["done"]["questions_practiced"] == 0
        assert task["done"]["checked_in"] is False
        assert task["type"].endswith("_practice")

    async def test_create_plan_non_member_403(self, client, registered_user, seed_subject):
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/plans",
            headers=headers,
            json={
                "subject_id": seed_subject["id"],
                "exam_date": _future_date(30),
                "daily_question_target": 10,
                "title": "free",
            },
        )
        assert resp.status_code == 403

    async def test_create_duplicate_active_plan_409(self, client, member_user, seed_subject):
        _, _, _, headers = member_user
        await _create_plan(client, headers, seed_subject["id"], title="第一份")
        resp = await client.post(
            "/api/v1/plans",
            headers=headers,
            json={
                "subject_id": seed_subject["id"],
                "exam_date": _future_date(30),
                "daily_question_target": 10,
                "title": "第二份",
            },
        )
        assert resp.status_code == 409

    async def test_create_past_exam_date_422(self, client, member_user, seed_subject):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/plans",
            headers=headers,
            json={
                "subject_id": seed_subject["id"],
                "exam_date": (date.today() - timedelta(days=1)).isoformat(),
                "daily_question_target": 10,
                "title": "过期",
            },
        )
        assert resp.status_code == 422

    async def test_active_empty(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/plans/active", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] is None
        assert body["today_task"] is None

    async def test_active_after_create(self, client, member_user, seed_subject):
        _, _, _, headers = member_user
        await _create_plan(client, headers, seed_subject["id"])
        resp = await client.get(
            f"/api/v1/plans/active?subject_id={seed_subject['id']}", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] is not None
        assert body["today_task"] is not None
        assert len(body["upcoming"]) == 3


# ═══════════════════════════════════════════════════════════════════════════
# 今日任务进度
# ═══════════════════════════════════════════════════════════════════════════


class TestTodayTaskProgress:
    async def test_practice_increments_session_stats(
        self, client, db_session, member_user, seed_subject
    ):
        """刷题 2 道 → study_sessions 当日行 questions_practiced/correct_count 累加（DB 事实）。"""
        username, _, _, headers = member_user
        await _create_plan(client, headers, seed_subject["id"])
        qid = await _seed_question(db_session, seed_subject["id"])

        for _ in range(2):
            resp = await client.post(
                f"/api/v1/questions/{qid}/answers",
                headers=headers,
                json={"answer": "B", "time_spent_seconds": 5},
            )
            assert resp.status_code == 200

        uid = await _user_id_by_username(db_session, username)
        res = await db_session.execute(
            select(StudySession).where(StudySession.user_id == uid)
        )
        sessions = res.scalars().all()
        # increment_session_stats 以 UTC 日期落账（datetime.now(timezone.utc).date()）
        utc_today = datetime.now(timezone.utc).date()
        s = next(s for s in sessions if s.session_date == utc_today)
        assert s.questions_practiced == 2
        assert s.correct_count == 2

    @pytest.mark.xfail(
        reason="D-17 [P3]: plans 用 date.today()（本地日）vs 刷题统计用 UTC 日，跨时区（本机 UTC+8 深夜）今日任务显示 0",
        strict=False,
    )
    async def test_today_task_reflects_practice(self, client, db_session, member_user, seed_subject):
        """契约：今日任务进度应反映当天刷题量。"""
        _, _, _, headers = member_user
        await _create_plan(client, headers, seed_subject["id"])
        qid = await _seed_question(db_session, seed_subject["id"])
        for _ in range(2):
            resp = await client.post(
                f"/api/v1/questions/{qid}/answers",
                headers=headers,
                json={"answer": "B", "time_spent_seconds": 5},
            )
            assert resp.status_code == 200

        resp = await client.get(
            f"/api/v1/plans/active?subject_id={seed_subject['id']}", headers=headers
        )
        done = resp.json()["today_task"]["done"]
        assert done["questions_practiced"] == 2, (
            "本地日期(plan)与 UTC 日期(统计)不一致时今日任务不反映练习 → D-17"
        )


async def _user_id_by_username(db, username: str) -> uuid.UUID:
    from app.db.models import User
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


# ═══════════════════════════════════════════════════════════════════════════
# 打卡：幂等 + 乐观锁
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckin:
    async def test_checkin_then_antishake(self, client, member_user, seed_subject):
        """打卡成功 → 重复打卡 already_checked_in=True（防抖，不重复写）。"""
        _, _, _, headers = member_user
        plan = await _create_plan(client, headers, seed_subject["id"])
        plan_id = plan["plan"]["id"]

        r1 = await client.post(f"/api/v1/plans/{plan_id}/checkin", headers=headers, json={})
        assert r1.status_code == 200
        body = r1.json()
        assert body["checked_in"] is True
        assert body["already_checked_in"] is False
        assert body["session"]["checked_in"] is True

        r2 = await client.post(f"/api/v1/plans/{plan_id}/checkin", headers=headers, json={})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["checked_in"] is True
        assert body2["already_checked_in"] is True

    async def test_checkin_404_unknown_plan(self, client, member_user):
        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/plans/{uuid.uuid4()}/checkin", headers=headers, json={}
        )
        assert resp.status_code == 404

    async def test_optimistic_lock_sql_guard(self, client, db_session, member_user, seed_subject):
        """乐观锁语义：UPDATE ... WHERE checked_in=false 第二次 rowcount=0。"""
        _, _, _, headers = member_user
        plan = await _create_plan(client, headers, seed_subject["id"])
        plan_id = uuid.UUID(plan["plan"]["id"])

        # 找当前用户 + 当日 session
        from app.db.models import Plan
        res = await db_session.execute(select(Plan).where(Plan.id == plan_id))
        p = res.scalar_one()
        session = await get_or_create_session(
            db_session, p.user_id, p.subject_id, date.today(), plan_id
        )
        assert session.checked_in is False

        now = datetime.now(timezone.utc)
        stmt1 = (
            update(StudySession)
            .where(StudySession.id == session.id, StudySession.checked_in == False)
            .values(checked_in=True, checked_in_at=now)
        )
        res1 = await db_session.execute(stmt1)
        await db_session.commit()
        assert res1.rowcount == 1, "首次置位应命中 1 行"

        stmt2 = (
            update(StudySession)
            .where(StudySession.id == session.id, StudySession.checked_in == False)
            .values(checked_in=True, checked_in_at=now)
        )
        res2 = await db_session.execute(stmt2)
        await db_session.commit()
        assert res2.rowcount == 0, "WHERE checked_in=false 保证第二次不重复置位"

    async def test_concurrent_checkin_single_winner(self, client, member_user, seed_subject):
        """并发打卡：两个并发请求都返回 200 且 checked_in=True，且只有一个 already_checked_in=False。"""
        _, _, _, headers = member_user
        plan = await _create_plan(client, headers, seed_subject["id"])
        plan_id = plan["plan"]["id"]

        async def _checkin():
            return await client.post(
                f"/api/v1/plans/{plan_id}/checkin", headers=headers, json={}
            )

        r1, r2 = await asyncio.gather(_checkin(), _checkin())
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        b1, b2 = r1.json(), r2.json()
        assert b1["checked_in"] is True
        assert b2["checked_in"] is True
        winners = [b for b in (b1, b2) if b["already_checked_in"] is False]
        assert len(winners) == 1, "并发打卡只应有一个首次置位者"
