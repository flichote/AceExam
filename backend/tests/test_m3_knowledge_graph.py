"""M3 知识图谱验收测试 — GET /subjects/{id}/knowledge-graph。

验收点（docs/design/flows.md / architecture.md §11.1）：
- 树结构完整性：章→节→知识点三级树、节点 id/name/level/question_count 正确
- 节点状态正确映射：user_knowledge_states 落到叶子节点（weak/mastered/untouched）
- 父节点自底向上聚合：worst-child-wins（任一 weak → weak；任一 consolidating → consolidating；全 mastered → mastered；否则 untouched）
- stats 只统计叶子节点；question_count 自底向上求和
- 多章科目 root 丢失缺陷（D-20）用 xfail 固化契约

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_knowledge_graph.py -v --tb=short -p no:warnings
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import KnowledgePoint, Question, User, UserKnowledgeState
from tests.conftest import _rand

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════
# 种子：三级树 subject → chapter(C1) → section(S1/S2) → leaf(KP1..KP4)
# ═══════════════════════════════════════════════════════════════════════

async def _seed_tree(db, subject_id: str) -> dict:
    """建 1 章 2 节 4 叶子 的树，返回各节点 id。"""
    c1 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="第一章", content="", level=1, sort_order=1)
    db.add(c1)
    await db.flush()
    s1 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="第一节", content="", level=2, parent_id=c1.id, sort_order=1)
    db.add(s1)
    await db.flush()
    s2 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="第二节", content="", level=2, parent_id=c1.id, sort_order=2)
    db.add(s2)
    await db.flush()
    kp1 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="知识点1", content="", level=3, parent_id=s1.id, sort_order=1)
    kp2 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="知识点2", content="", level=3, parent_id=s1.id, sort_order=2)
    kp3 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="知识点3", content="", level=3, parent_id=s2.id, sort_order=1)
    kp4 = KnowledgePoint(subject_id=uuid.UUID(subject_id), name="知识点4", content="", level=3, parent_id=s2.id, sort_order=2)
    db.add_all([kp1, kp2, kp3, kp4])
    await db.commit()
    for k in (c1, s1, s2, kp1, kp2, kp3, kp4):
        await db.refresh(k)
    return {
        "c1": str(c1.id), "s1": str(s1.id), "s2": str(s2.id),
        "kp1": str(kp1.id), "kp2": str(kp2.id), "kp3": str(kp3.id), "kp4": str(kp4.id),
    }


async def _seed_question(db, subject_id: str, kp_id: str, source: str = "self_built", status: str = "active") -> None:
    db.add(Question(
        subject_id=uuid.UUID(subject_id), knowledge_point_id=uuid.UUID(kp_id), type="single",
        content=f"题-{_rand('q')}", options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        answer="B", analysis="", difficulty=3, source=source, status=status,
    ))
    await db.commit()


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


async def _set_state(db, user_id, kp_id: str, subject_id: str, status: str, correct: int, wrong: int) -> None:
    db.add(UserKnowledgeState(
        user_id=user_id, knowledge_point_id=uuid.UUID(kp_id), subject_id=uuid.UUID(subject_id),
        status=status, correct_count=correct, wrong_count=wrong, streak=0,
    ))
    await db.commit()


def _find_node(root: dict, node_id: str) -> dict | None:
    """在树中按 id 找节点。"""
    if root.get("id") == node_id:
        return root
    for child in root.get("children", []):
        hit = _find_node(child, node_id)
        if hit:
            return hit
    return None


# ═══════════════════════════════════════════════════════════════════════
# 1. 树结构完整性
# ═══════════════════════════════════════════════════════════════════════

class TestTreeStructure:
    async def test_full_tree_structure(self, client: AsyncClient, db_session, registered_user, seed_subject):
        """三级树完整：root=章，children=节，children=叶子。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_id"] == seed_subject["id"]
        assert data["subject_name"] == seed_subject["name"]

        root = data["root"]
        assert root is not None
        assert root["id"] == ids["c1"]
        assert root["level"] == 1

        s1, s2 = root["children"]
        assert {n["id"] for n in root["children"]} == {ids["s1"], ids["s2"]}
        assert {n["level"] for n in root["children"]} == {2}

        s1_kps = {n["id"] for n in s1["children"]}
        s2_kps = {n["id"] for n in s2["children"]}
        assert s1_kps == {ids["kp1"], ids["kp2"]}
        assert s2_kps == {ids["kp3"], ids["kp4"]}
        assert all(n["level"] == 3 for n in s1["children"] + s2["children"])

    async def test_stats_counts(self, client: AsyncClient, db_session, registered_user, seed_subject):
        """stats 只统计叶子节点：4 叶子、mastered/weak/consolidating/untouched 各 1。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _set_state(db_session, uid, ids["kp1"], seed_subject["id"], "weak", 2, 8)
        await _set_state(db_session, uid, ids["kp2"], seed_subject["id"], "mastered", 20, 1)
        await _set_state(db_session, uid, ids["kp4"], seed_subject["id"], "consolidating", 5, 5)
        # kp3 无状态 → untouched

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        stats = resp.json()["stats"]
        assert stats["total_nodes"] == 7
        assert stats["leaf_count"] == 4
        assert stats["mastered_count"] == 1
        assert stats["weak_count"] == 1
        assert stats["consolidating_count"] == 1
        assert stats["untouched_count"] == 1

    async def test_no_kp_404(self, client: AsyncClient, registered_user, seed_subject):
        """无知识点 → 404（smoke 已覆盖，这里再确认一次响应体）。"""
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 2. 节点状态映射 + 父节点聚合
# ═══════════════════════════════════════════════════════════════════════

class TestNodeStatus:
    async def test_leaf_status_mapping(self, client: AsyncClient, db_session, registered_user, seed_subject):
        """叶子节点状态映射：weak / mastered / consolidating / untouched。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _set_state(db_session, uid, ids["kp1"], seed_subject["id"], "weak", 2, 8)
        await _set_state(db_session, uid, ids["kp2"], seed_subject["id"], "mastered", 20, 1)
        await _set_state(db_session, uid, ids["kp4"], seed_subject["id"], "consolidating", 5, 5)

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        root = resp.json()["root"]
        assert _find_node(root, ids["kp1"])["status"] == "weak"
        assert _find_node(root, ids["kp2"])["status"] == "mastered"
        assert _find_node(root, ids["kp3"])["status"] == "untouched"
        assert _find_node(root, ids["kp4"])["status"] == "consolidating"

    async def test_parent_aggregation_worst_child_wins(
        self, client: AsyncClient, db_session, registered_user, seed_subject
    ):
        """父节点聚合：weak 子 → 父 weak；consolidating 子 → 父 consolidating；根也 weak。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        # S1 下：kp1 weak + kp2 mastered → S1 weak
        await _set_state(db_session, uid, ids["kp1"], seed_subject["id"], "weak", 2, 8)
        await _set_state(db_session, uid, ids["kp2"], seed_subject["id"], "mastered", 20, 1)
        # S2 下：kp3 untouched + kp4 consolidating → S2 consolidating
        await _set_state(db_session, uid, ids["kp4"], seed_subject["id"], "consolidating", 5, 5)
        # 根：S1 weak → C1 weak（worst-child-wins）

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        root = resp.json()["root"]
        assert _find_node(root, ids["s1"])["status"] == "weak"
        assert _find_node(root, ids["s2"])["status"] == "consolidating"
        assert root["status"] == "weak"

    async def test_parent_aggregation_all_mastered(
        self, client: AsyncClient, db_session, registered_user, seed_subject
    ):
        """全 mastered 子 → 父 mastered。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        for kp in (ids["kp1"], ids["kp2"]):
            await _set_state(db_session, uid, kp, seed_subject["id"], "mastered", 20, 1)
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        root = resp.json()["root"]
        assert _find_node(root, ids["s1"])["status"] == "mastered"


# ═══════════════════════════════════════════════════════════════════════
# 3. question_count / practice_count / accuracy / include_questions
# ═══════════════════════════════════════════════════════════════════════

class TestCountsAndAccuracy:
    async def test_question_count_aggregation(
        self, client: AsyncClient, db_session, registered_user, seed_subject
    ):
        """question_count 自底向上求和；archived 题不计。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        # kp1: 2 active；kp2: 1 active + 1 archived；kp3: 0；kp4: 3 active
        for _ in range(2):
            await _seed_question(db_session, seed_subject["id"], ids["kp1"])
        await _seed_question(db_session, seed_subject["id"], ids["kp2"])
        await _seed_question(db_session, seed_subject["id"], ids["kp2"], status="archived")
        for _ in range(3):
            await _seed_question(db_session, seed_subject["id"], ids["kp4"])

        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        root = resp.json()["root"]
        assert _find_node(root, ids["kp1"])["question_count"] == 2
        assert _find_node(root, ids["kp2"])["question_count"] == 1
        assert _find_node(root, ids["kp3"])["question_count"] == 0
        assert _find_node(root, ids["kp4"])["question_count"] == 3
        assert _find_node(root, ids["s1"])["question_count"] == 3
        assert _find_node(root, ids["s2"])["question_count"] == 3
        assert root["question_count"] == 6

    async def test_leaf_practice_accuracy(self, client: AsyncClient, db_session, registered_user, seed_subject):
        """叶子节点带状态 → practice_count / accuracy；无状态 → None。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _set_state(db_session, uid, ids["kp1"], seed_subject["id"], "weak", 2, 8)
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        root = resp.json()["root"]
        kp1 = _find_node(root, ids["kp1"])
        assert kp1["practice_count"] == 10
        assert kp1["accuracy"] == 0.2
        kp3 = _find_node(root, ids["kp3"])
        assert kp3["practice_count"] is None
        assert kp3["accuracy"] is None

    async def test_include_questions_false(
        self, client: AsyncClient, db_session, registered_user, seed_subject
    ):
        """include_questions=false → question_count 全 0、叶子不输出 practice_count。"""
        ids = await _seed_tree(db_session, seed_subject["id"])
        await _seed_question(db_session, seed_subject["id"], ids["kp1"])
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _set_state(db_session, uid, ids["kp1"], seed_subject["id"], "weak", 2, 8)

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph?include_questions=false",
            headers=headers,
        )
        assert resp.status_code == 200
        root = resp.json()["root"]
        assert _find_node(root, ids["kp1"])["question_count"] == 0
        # schema 默认序列化为 null（键仍存在）
        assert _find_node(root, ids["kp1"])["practice_count"] is None
        assert _find_node(root, ids["kp1"])["accuracy"] is None


# ═══════════════════════════════════════════════════════════════════════
# 4. 多章（多 root）缺陷契约 — D-20
# ═══════════════════════════════════════════════════════════════════════

class TestMultiRoot:
    async def test_stats_still_correct_with_two_roots(
        self, client: AsyncClient, db_session, registered_user, seed_subject
    ):
        """两个平级章（多 root）时 stats 仍然正确（stats 不依赖 root 字段）。"""
        c1 = KnowledgePoint(subject_id=uuid.UUID(seed_subject["id"]), name="第一章", content="", level=1, sort_order=1)
        c2 = KnowledgePoint(subject_id=uuid.UUID(seed_subject["id"]), name="第二章", content="", level=1, sort_order=2)
        db_session.add_all([c1, c2])
        await db_session.commit()
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        stats = resp.json()["stats"]
        assert stats["total_nodes"] == 2
        assert stats["leaf_count"] == 0

    @pytest.mark.xfail(
        reason="D-20 [P2]: 多章科目 build_knowledge_graph 在 len(roots)>1 时返回 root=None，整棵树对前端不可见",
        strict=False,
    )
    async def test_multi_root_keeps_all_roots(
        self, client: AsyncClient, db_session, registered_user, seed_subject
    ):
        """契约：多章科目 root 不应为 None（前端 series-tree 需要可渲染的根）。

        期望：root 为合成根节点（children 含全部章）或返回 roots 数组；
        实际：root=None，两章节点全部丢失。
        """
        c1 = KnowledgePoint(subject_id=uuid.UUID(seed_subject["id"]), name="第一章", content="", level=1, sort_order=1)
        c2 = KnowledgePoint(subject_id=uuid.UUID(seed_subject["id"]), name="第二章", content="", level=1, sort_order=2)
        db_session.add_all([c1, c2])
        await db_session.commit()
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"] is not None, "多章科目 root 丢失 → D-20"
        assert len(data["root"]["children"]) == 2, "root 应包含全部章"
