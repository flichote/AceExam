"""M3 挂科预警验收测试 — GET /me/warnings。

验收点（docs/design/flows.md / architecture.md §11.6）：
- 风险等级边界：days_left≤7 → acc<0.4=high / <0.7=medium / ≥0.7=low；
  days_left 7-14 → acc<0.3=high / <0.6=medium / ≥0.6=low；>14 → acc<0.2=high / <0.5=medium / ≥0.5=low
- 趋势调整：近 7 天活跃≤4 天 +1 级（恶化）；近 7 天≥70 题且正确率≥0.8 -1 级（向好）
- 理由可解释：reasons 含正确率/倒计时/活跃天数等人类可读文案
- overall_risk = 所有条目最高等级

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_warnings.py -v --tb=short -p no:warnings
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


async def _seed_subject(db, name: str = "预警科目") -> dict:
    s = Subject(code=_rand("warn"), name=name, description="", config={})
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": str(s.id), "name": s.name}


async def _seed_plan(db, user_id, subject_id: str, exam_date: date) -> None:
    db.add(Plan(
        user_id=user_id, subject_id=uuid.UUID(subject_id), title="期末计划",
        exam_date=exam_date, status="active", config={},
    ))
    await db.commit()


async def _seed_weak_kp(db, user_id, subject_id: str, name: str, status: str, correct: int, wrong: int) -> str:
    kp = KnowledgePoint(subject_id=uuid.UUID(subject_id), name=name, content="", level=3)
    db.add(kp)
    await db.flush()
    db.add(UserKnowledgeState(
        user_id=user_id, knowledge_point_id=kp.id, subject_id=uuid.UUID(subject_id),
        status=status, correct_count=correct, wrong_count=wrong, streak=0,
    ))
    await db.commit()
    return str(kp.id)


async def _seed_activity(db, user_id, subject_id: str, days_ago: list[int], q_per_day: int = 5, c_per_day: int = 5):
    """写入过去几天（days_ago 内）的学习活动。"""
    for offset in days_ago:
        db.add(StudySession(
            user_id=user_id, subject_id=uuid.UUID(subject_id),
            session_date=_d(-offset), questions_practiced=q_per_day,
            correct_count=c_per_day, checked_in=True,
        ))
    await db.commit()


async def _get_warnings(client, headers):
    resp = await client.get("/api/v1/me/warnings", headers=headers)
    assert resp.status_code == 200
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════
# 1. 风险等级边界
# ═══════════════════════════════════════════════════════════════════════

class TestRiskBoundaries:
    async def test_within_7_days_boundaries(
        self, client: AsyncClient, db_session, registered_user
    ):
        """考前 ≤7 天：acc<0.4 → high；0.4≤acc<0.7 → medium；≥0.7 → low。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(5))
        # 中和趋势调整：近 7 天活跃 5 天（不加级），25 题正确率 0.6（不降级）→ trend_adjust=0
        await _seed_activity(db_session, uid, subj["id"], days_ago=[1, 2, 3, 4, 5], q_per_day=5, c_per_day=3)
        await _seed_weak_kp(db_session, uid, subj["id"], "高险点", "weak", 2, 8)      # acc=0.2 → high
        await _seed_weak_kp(db_session, uid, subj["id"], "中险点", "consolidating", 5, 5)  # acc=0.5 → medium
        await _seed_weak_kp(db_session, uid, subj["id"], "低险点", "weak", 8, 2)      # acc=0.8 → low

        data = await _get_warnings(client, headers)
        assert data["overall_risk"] == "high"
        by_name = {it["knowledge_point_name"]: it for it in data["items"]}
        assert by_name["高险点"]["risk_level"] == "high"
        assert by_name["中险点"]["risk_level"] == "medium"
        assert by_name["低险点"]["risk_level"] == "low"
        # 排序：risk 降序 high → medium → low
        levels = [it["risk_level"] for it in data["items"]]
        assert levels == ["high", "medium", "low"]

    async def test_14_days_boundaries(
        self, client: AsyncClient, db_session, registered_user
    ):
        """考前 8-14 天：acc<0.3 → high；0.3≤acc<0.6 → medium；≥0.6 → low。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(10))
        await _seed_activity(db_session, uid, subj["id"], days_ago=[1, 2, 3, 4, 5], q_per_day=5, c_per_day=3)
        await _seed_weak_kp(db_session, uid, subj["id"], "K1", "weak", 2, 8)     # 0.2 → high
        await _seed_weak_kp(db_session, uid, subj["id"], "K2", "weak", 4, 6)     # 0.4 → medium
        await _seed_weak_kp(db_session, uid, subj["id"], "K3", "weak", 8, 2)     # 0.8 → low

        data = await _get_warnings(client, headers)
        by_name = {it["knowledge_point_name"]: it for it in data["items"]}
        assert by_name["K1"]["risk_level"] == "high"
        assert by_name["K2"]["risk_level"] == "medium"
        assert by_name["K3"]["risk_level"] == "low"

    async def test_beyond_14_days_boundaries(
        self, client: AsyncClient, db_session, registered_user
    ):
        """考前 >14 天：acc<0.2 → high；0.2≤acc<0.5 → medium；≥0.5 → low。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(20))
        await _seed_activity(db_session, uid, subj["id"], days_ago=[1, 2, 3, 4, 5], q_per_day=5, c_per_day=3)
        await _seed_weak_kp(db_session, uid, subj["id"], "K1", "weak", 1, 9)     # 0.1 → high
        await _seed_weak_kp(db_session, uid, subj["id"], "K2", "weak", 3, 7)     # 0.3 → medium
        await _seed_weak_kp(db_session, uid, subj["id"], "K3", "weak", 6, 4)     # 0.6 → low

        data = await _get_warnings(client, headers)
        by_name = {it["knowledge_point_name"]: it for it in data["items"]}
        assert by_name["K1"]["risk_level"] == "high"
        assert by_name["K2"]["risk_level"] == "medium"
        assert by_name["K3"]["risk_level"] == "low"

    async def test_reasons_explainable(
        self, client: AsyncClient, db_session, registered_user
    ):
        """reasons 可解释：含正确率、倒计时、练习次数。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(5))
        await _seed_weak_kp(db_session, uid, subj["id"], "可解释点", "weak", 2, 8)

        data = await _get_warnings(client, headers)
        item = data["items"][0]
        reasons = "；".join(item["reasons"])
        assert "正确率" in reasons
        assert "练习" in reasons
        assert "距考试仅 5 天" in reasons
        assert item["practice_count"] == 10
        assert item["accuracy"] == 0.2
        assert item["days_left"] == 5
        assert item["suggestion"], "suggestion 不应为空"


# ═══════════════════════════════════════════════════════════════════════
# 2. 趋势调整
# ═══════════════════════════════════════════════════════════════════════

class TestTrendAdjust:
    async def test_inactive_trend_escalates(
        self, client: AsyncClient, db_session, registered_user
    ):
        """近 7 天活跃 ≤4 天 → +1 级：acc=0.8（base low）升为 medium。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(5))
        await _seed_weak_kp(db_session, uid, subj["id"], "不活跃点", "weak", 8, 2)  # acc=0.8 → base low
        # 近 7 天只有 2 天活动（≤4 → +1）
        await _seed_activity(db_session, uid, subj["id"], days_ago=[1, 3], q_per_day=2, c_per_day=2)

        data = await _get_warnings(client, headers)
        item = data["items"][0]
        assert item["risk_level"] == "medium", "活跃不足应升一级"
        assert any("近 7 天仅做题" in r for r in item["reasons"])

    async def test_improving_trend_downgrades(
        self, client: AsyncClient, db_session, registered_user
    ):
        """近 7 天 ≥70 题且正确率 ≥0.8 → -1 级：acc=0.5（base medium）降为 low。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(5))
        await _seed_weak_kp(db_session, uid, subj["id"], "向好点", "weak", 5, 5)  # acc=0.5 → base medium
        # 连续 7 天，每天 10 题 8 对 → 70 题 56 对（0.8）
        await _seed_activity(db_session, uid, subj["id"], days_ago=[1, 2, 3, 4, 5, 6, 7], q_per_day=10, c_per_day=8)

        data = await _get_warnings(client, headers)
        assert data["items"][0]["risk_level"] == "low", "持续向好应降一级"


# ═══════════════════════════════════════════════════════════════════════
# 3. 边界：无计划 / 无薄弱 / 多计划 overall
# ═══════════════════════════════════════════════════════════════════════

class TestWarningsEdges:
    async def test_no_weak_kps_returns_low(
        self, client: AsyncClient, db_session, registered_user
    ):
        """有计划但无薄弱知识点 → overall_risk=low、items 空。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(10))

        data = await _get_warnings(client, headers)
        assert data["overall_risk"] == "low"
        assert data["items"] == []

    async def test_past_exam_skipped(
        self, client: AsyncClient, db_session, registered_user
    ):
        """考试日已过 → 不产生预警条目。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, subj["id"], _d(-1))
        await _seed_weak_kp(db_session, uid, subj["id"], "过期点", "weak", 2, 8)

        data = await _get_warnings(client, headers)
        assert data["items"] == []
        assert data["overall_risk"] is None

    async def test_plan_without_exam_date_skipped(
        self, client: AsyncClient, db_session, registered_user
    ):
        """计划无 exam_date → 不产生条目。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        db_session.add(Plan(user_id=uid, subject_id=uuid.UUID(subj["id"]), title="无日期计划",
                             exam_date=None, status="active", config={}))
        await db_session.commit()

        data = await _get_warnings(client, headers)
        assert data["items"] == []
        assert data["overall_risk"] is None

    async def test_overall_risk_is_max_across_plans(
        self, client: AsyncClient, db_session, registered_user
    ):
        """多计划 overall_risk 取最高等级。"""
        s1 = await _seed_subject(db_session, "高数")
        s2 = await _seed_subject(db_session, "线代")
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, s1["id"], _d(5))
        await _seed_plan(db_session, uid, s2["id"], _d(20))
        await _seed_weak_kp(db_session, uid, s1["id"], "高危点", "weak", 2, 8)   # high
        await _seed_weak_kp(db_session, uid, s2["id"], "低危点", "weak", 6, 4)   # low

        data = await _get_warnings(client, headers)
        assert data["overall_risk"] == "high"
        assert len(data["items"]) == 2
        assert {it["knowledge_point_name"] for it in data["items"]} == {"高危点", "低危点"}

    async def test_subject_filter(self, client: AsyncClient, db_session, registered_user):
        """subject_id 过滤只返回该科目预警。"""
        s1 = await _seed_subject(db_session, "高数")
        s2 = await _seed_subject(db_session, "线代")
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, s1["id"], _d(5))
        await _seed_plan(db_session, uid, s2["id"], _d(5))
        await _seed_weak_kp(db_session, uid, s1["id"], "高数高危", "weak", 2, 8)
        await _seed_weak_kp(db_session, uid, s2["id"], "线代中危", "weak", 5, 5)

        resp = await client.get(
            f"/api/v1/me/warnings?subject_id={s1['id']}", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert {it["knowledge_point_name"] for it in data["items"]} == {"高数高危"}
