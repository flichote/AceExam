"""M3 排行榜验收测试 — GET /leaderboard。

验收点（docs/design/flows.md / architecture.md §11.6）：
- 入围过滤：做题量 ≥30 且正确率 ≥0.1（低于 0.1 视为异常剔除）
- 排序：total_correct DESC → accuracy DESC
- 分页：page/page_size、rank 连续、total 正确
- me：当前用户排名/统计；无资格用户 me 为 null
- scope=subject 只统计该科目

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_leaderboard.py -v --tb=short -p no:warnings
"""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import StudySession, Subject, User
from tests.conftest import _rand

pytestmark = pytest.mark.anyio


def _d(offset: int) -> date:
    return date.today() + timedelta(days=offset)


async def _register(client, username: str) -> tuple[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "pass123456"},
    )
    assert resp.status_code == 201, resp.text
    return username, resp.json()["access_token"]


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


async def _seed_subject(db, name: str = "排行榜科目") -> dict:
    s = Subject(code=_rand("lb"), name=name, description="", config={})
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": str(s.id), "name": s.name}


async def _seed_sessions(db, user_id, subject_id: str, q_total: int, c_total: int, offset: int = 0):
    """单个 user 一次性写入 (q_total, c_total) 到某天的 session（排行榜按 user 聚合求和）。"""
    db.add(StudySession(
        user_id=user_id, subject_id=uuid.UUID(subject_id),
        session_date=_d(-offset), questions_practiced=q_total, correct_count=c_total, checked_in=True,
    ))
    await db.commit()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════
# 1. 入围过滤 + 排序 + me
# ═══════════════════════════════════════════════════════════════════════

class TestLeaderboardBasic:
    async def test_qualification_and_sort(
        self, client: AsyncClient, db_session, registered_user
    ):
        """做题量≥30 且正确率≥0.1 才入围；total_correct 降序排；me 正确。"""
        subj = await _seed_subject(db_session)
        # A：100 题 80 对（合格，第一）
        username_a, _, token_a, _ = registered_user  # A 是 registered_user
        uid_a = await _user_id(db_session, username_a)
        await _seed_sessions(db_session, uid_a, subj["id"], 100, 80, offset=3)

        # B：50 题 45 对（合格，第二）
        uname_b, token_b = await _register(client, _rand("user_b"))
        uid_b = await _user_id(db_session, uname_b)
        await _seed_sessions(db_session, uid_b, subj["id"], 50, 45, offset=3)

        # C：20 题（<30 不合格，剔除）
        uname_c, _ = await _register(client, _rand("user_c"))
        uid_c = await _user_id(db_session, uname_c)
        await _seed_sessions(db_session, uid_c, subj["id"], 20, 15, offset=3)

        # D：60 题 2 对（正确率 0.033 < 0.1，剔除）
        uname_d, _ = await _register(client, _rand("user_d"))
        uid_d = await _user_id(db_session, uname_d)
        await _seed_sessions(db_session, uid_d, subj["id"], 60, 2, offset=3)

        resp = await client.get("/api/v1/leaderboard", headers=_auth(token_a))
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "global"
        assert data["total"] == 2
        items = data["items"]
        assert len(items) == 2
        # 排序：A(80 对) 在 B(45 对) 前
        assert items[0]["username"] == username_a
        assert items[0]["rank"] == 1
        assert items[0]["total_correct"] == 80
        assert items[0]["questions_practiced"] == 100
        assert items[0]["accuracy"] == 0.8
        assert items[1]["username"] == uname_b
        assert items[1]["rank"] == 2
        assert items[1]["total_correct"] == 45

        # me：A 排第 1
        me = data["me"]
        assert me["rank"] == 1
        assert me["total_correct"] == 80
        assert me["questions_practiced"] == 100
        assert me["accuracy"] == 0.8

    async def test_accuracy_tiebreak(
        self, client: AsyncClient, db_session, registered_user
    ):
        """正确数相同 → 正确率高者在前。"""
        subj = await _seed_subject(db_session)
        # A：50 题 40 对（0.8）
        username_a, _, token_a, _ = registered_user
        uid_a = await _user_id(db_session, username_a)
        await _seed_sessions(db_session, uid_a, subj["id"], 50, 40, offset=3)

        # B：40 题 40 对（1.0）
        uname_b, _ = await _register(client, _rand("user_tb"))
        uid_b = await _user_id(db_session, uname_b)
        await _seed_sessions(db_session, uid_b, subj["id"], 40, 40, offset=3)

        resp = await client.get("/api/v1/leaderboard", headers=_auth(token_a))
        items = resp.json()["items"]
        assert items[0]["username"] == uname_b, "同正确数应正确率高者优先"
        assert items[0]["accuracy"] == 1.0
        assert items[1]["username"] == username_a
        assert items[1]["accuracy"] == 0.8

    async def test_streak_included(self, client: AsyncClient, db_session, registered_user):
        """榜单项 current_streak 来自连续打卡。"""
        subj = await _seed_subject(db_session)
        username, _, token, _ = registered_user
        uid = await _user_id(db_session, username)
        # 连续 3 天打卡
        for i in range(3):
            db_session.add(StudySession(
                user_id=uid, subject_id=uuid.UUID(subj["id"]),
                session_date=_d(-i), questions_practiced=40, correct_count=30, checked_in=True,
            ))
        await db_session.commit()

        resp = await client.get("/api/v1/leaderboard", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["items"][0]["current_streak"] == 3

    async def test_no_activity_me_null(self, client: AsyncClient, registered_user):
        """无任何做题数据 → items 空、me 为 null。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/leaderboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["me"] is None


# ═══════════════════════════════════════════════════════════════════════
# 2. 分页
# ═══════════════════════════════════════════════════════════════════════

class TestLeaderboardPagination:
    async def test_pagination_rank_continuity(
        self, client: AsyncClient, db_session, registered_user
    ):
        """3 人入围，page_size=2：第 1 页 2 人、第 2 页 1 人、rank 连续、total=3。"""
        subj = await _seed_subject(db_session)
        # 当前用户（A）
        username_a, _, token, _ = registered_user
        uid_a = await _user_id(db_session, username_a)
        await _seed_sessions(db_session, uid_a, subj["id"], 100, 80, offset=5)

        stats = [("user_p1", 60, 50), ("user_p2", 40, 30)]
        for uname, q, c in stats:
            await _register(client, uname)
            uid = await _user_id(db_session, uname)
            await _seed_sessions(db_session, uid, subj["id"], q, c, offset=5)

        r1 = await client.get(
            "/api/v1/leaderboard?page=1&page_size=2", headers=_auth(token),
        )
        d1 = r1.json()
        assert d1["total"] == 3
        assert len(d1["items"]) == 2
        assert [it["rank"] for it in d1["items"]] == [1, 2]

        r2 = await client.get(
            "/api/v1/leaderboard?page=2&page_size=2", headers=_auth(token),
        )
        d2 = r2.json()
        assert len(d2["items"]) == 1
        assert d2["items"][0]["rank"] == 3

    async def test_page_out_of_range(self, client: AsyncClient, registered_user):
        """页码超出范围 → 空 items。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/leaderboard?page=99", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []


# ═══════════════════════════════════════════════════════════════════════
# 3. scope=subject
# ═══════════════════════════════════════════════════════════════════════

class TestLeaderboardSubjectScope:
    async def test_subject_scope_filters_sessions(
        self, client: AsyncClient, db_session, registered_user
    ):
        """scope=subject 只聚合该科目做题量。"""
        s1 = await _seed_subject(db_session, "高数")
        s2 = await _seed_subject(db_session, "线代")
        username_a, _, token, _ = registered_user
        uid_a = await _user_id(db_session, username_a)
        # A 在 s1 有 40 题（合格），在 s2 有 10 题
        await _seed_sessions(db_session, uid_a, s1["id"], 40, 30, offset=3)
        await _seed_sessions(db_session, uid_a, s2["id"], 10, 8, offset=9)

        # B 只在 s1 有 30 题
        uname_b, _ = await _register(client, _rand("user_bs"))
        uid_b = await _user_id(db_session, uname_b)
        await _seed_sessions(db_session, uid_b, s1["id"], 30, 20, offset=3)

        resp = await client.get(
            f"/api/v1/leaderboard?scope=subject&subject_id={s1['id']}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "subject"
        assert data["total"] == 2
        # A 的 s1 做题量 40（s2 的 10 题不进入）
        item_a = next(it for it in data["items"] if it["username"] == username_a)
        assert item_a["questions_practiced"] == 40
        assert item_a["total_correct"] == 30
        assert item_a["rank"] == 1

        # B 只在 s1
        item_b = next(it for it in data["items"] if it["username"] == uname_b)
        assert item_b["questions_practiced"] == 30
