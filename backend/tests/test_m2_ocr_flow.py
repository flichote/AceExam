"""M2 拍照录题端到端验收测试 — /ocr/upload + /questions/from-ocr（mock OCR 服务）。

验收点（docs/design/flows.md 流程2 / PRD）：
- 上传图片 → 结构化识别结果（可编辑预览）
- 轮询识别状态
- 确认入库 → 题目进入题库（source=ugc）
- 幂等：同一 upload 重复确认不产生重复题目
- 免费用户每日 5 次限流
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models import Question
from tests.conftest import _rand


def _image_bytes(name: str = "photo.jpg") -> tuple[str, bytes, str]:
    return name, b"\xff\xd8\xff\xe0fake-jpeg-content", "image/jpeg"


def _confirm_payload(upload_id: str, subject_id: str, kp_id: str, content: str) -> dict:
    return {
        "upload_id": upload_id,
        "subject_id": subject_id,
        "knowledge_point_id": kp_id,
        "structured": {
            "type": "single",
            "content": content,
            "options": [
                {"key": "A", "text": "0"},
                {"key": "B", "text": "2x"},
            ],
            "answer": "B",
            "analysis": "求导",
            "confidence": 0.85,
        },
        "confirm_answer": True,
    }


async def _do_upload(client, headers, subject_id: str) -> dict:
    resp = await client.post(
        "/api/v1/ocr/upload",
        headers=headers,
        files={"file": _image_bytes()},
        data={"subject_id": subject_id, "source": "photo"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# 上传 / 轮询
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrUpload:
    async def test_upload_parsed(self, client, registered_user, seed_subject):
        _, _, _, headers = registered_user
        body = await _do_upload(client, headers, seed_subject["id"])
        assert body["status"] == "parsed"
        assert body["upload_id"]
        assert body["structured"]["type"] == "single"
        assert "Mock question content" in body["structured"]["content"]
        assert body["structured"]["confidence"] > 0

    async def test_upload_invalid_content_type(self, client, registered_user, seed_subject):
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/ocr/upload",
            headers=headers,
            files={"file": ("doc.txt", b"not an image", "text/plain")},
            data={"subject_id": seed_subject["id"], "source": "photo"},
        )
        assert resp.status_code == 400

    async def test_upload_requires_auth(self, client, seed_subject):
        resp = await client.post(
            "/api/v1/ocr/upload",
            files={"file": _image_bytes()},
            data={"subject_id": seed_subject["id"], "source": "photo"},
        )
        assert resp.status_code == 401

    async def test_poll_parsed(self, client, registered_user, seed_subject):
        _, _, _, headers = registered_user
        up = await _do_upload(client, headers, seed_subject["id"])
        resp = await client.get(f"/api/v1/ocr/upload/{up['upload_id']}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "parsed"
        assert body["structured"]["content"]
        assert body["raw_text"]

    async def test_poll_other_user_404(self, client, registered_user, seed_subject):
        """他人上传记录不可见（数据隔离）。"""
        _, _, _, headers_a = registered_user
        up = await _do_upload(client, headers_a, seed_subject["id"])
        from tests.conftest import _register_user
        _, _, token_b = await _register_user(client, _rand("user_b"))
        headers_b = {"Authorization": f"Bearer {token_b}"}
        resp = await client.get(f"/api/v1/ocr/upload/{up['upload_id']}", headers=headers_b)
        assert resp.status_code == 404

    async def test_free_rate_limit_5_per_day(self, client, registered_user, seed_subject):
        """免费用户每日 5 次：第 6 次 429。"""
        _, _, _, headers = registered_user
        for i in range(5):
            resp = await client.post(
                "/api/v1/ocr/upload",
                headers=headers,
                files={"file": _image_bytes(f"p{i}.jpg")},
                data={"subject_id": seed_subject["id"], "source": "photo"},
            )
            assert resp.status_code == 200, resp.text
        resp = await client.post(
            "/api/v1/ocr/upload",
            headers=headers,
            files={"file": _image_bytes("p6.jpg")},
            data={"subject_id": seed_subject["id"], "source": "photo"},
        )
        assert resp.status_code == 429

    async def test_member_no_rate_limit(self, client, member_user, seed_subject):
        """会员不受每日 5 次限制（验证 is_member 分支）。"""
        _, _, _, headers = member_user
        for i in range(6):
            resp = await client.post(
                "/api/v1/ocr/upload",
                headers=headers,
                files={"file": _image_bytes(f"m{i}.jpg")},
                data={"subject_id": seed_subject["id"], "source": "photo"},
            )
            assert resp.status_code == 200, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# 确认入库 / 幂等
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrConfirm:
    async def test_confirm_creates_question(
        self, client, db_session, registered_user, seed_subject, seed_kp
    ):
        """确认入库 → questions 新增 source=ugc 题目，upload 置 confirmed。"""
        _, _, _, headers = registered_user
        up = await _do_upload(client, headers, seed_subject["id"])
        content = f"OCR确认题：求 $f(x)=x^2$ 的导数（{uuid.uuid4().hex[:6]}）"
        resp = await client.post(
            "/api/v1/questions/from-ocr",
            headers=headers,
            json=_confirm_payload(up["upload_id"], seed_subject["id"], seed_kp["id"], content),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "confirmed"
        assert body["duplicated"] is False
        assert body["question_id"]

        # 题目入库（source=ugc）；注意：GET /questions/{id} 对 list 格式 options 500，见 D-16
        qid = body["question_id"]
        res = await db_session.execute(
            select(Question).where(Question.id == uuid.UUID(qid))
        )
        q = res.scalar_one()
        assert q.source == "ugc"
        assert q.status == "active"
        assert content in q.content

        # DB 统计：ugc 题目恰 1 条
        cnt = await db_session.execute(
            select(func.count()).select_from(Question).where(Question.source == "ugc")
        )
        assert cnt.scalar_one() == 1

        # 轮询 upload 状态已 confirmed 且回填 question_id
        poll = await client.get(f"/api/v1/ocr/upload/{up['upload_id']}", headers=headers)
        assert poll.json()["status"] == "confirmed"

    @pytest.mark.xfail(
        reason="D-16 [P2]: QuestionResponse.options 类型为 dict，生产 options 为 list → GET /questions/{id} 500",
        strict=False,
    )
    async def test_confirmed_question_viewable(
        self, client, db_session, registered_user, seed_subject, seed_kp
    ):
        """契约：确认入库后的题目可通过 GET /questions/{id} 查看。"""
        _, _, _, headers = registered_user
        up = await _do_upload(client, headers, seed_subject["id"])
        content = f"OCR可查看题：{uuid.uuid4().hex[:6]}"
        resp = await client.post(
            "/api/v1/questions/from-ocr",
            headers=headers,
            json=_confirm_payload(up["upload_id"], seed_subject["id"], seed_kp["id"], content),
        )
        assert resp.status_code == 200
        qid = resp.json()["question_id"]
        resp = await client.get(f"/api/v1/questions/{qid}", headers=headers)
        assert resp.status_code == 200, (
            "当前对 list 格式 options 500 → D-16：QuestionResponse.options 应接受 list"
        )
        assert resp.json()["source"] == "ugc"

    async def test_confirm_idempotent(
        self, client, db_session, registered_user, seed_subject, seed_kp
    ):
        """同一 upload 重复确认 → duplicated=True，不产生第二条题目。"""
        _, _, _, headers = registered_user
        up = await _do_upload(client, headers, seed_subject["id"])
        content = f"OCR幂等题：$\\int_0^1 x dx$（{uuid.uuid4().hex[:6]}）"
        payload = _confirm_payload(up["upload_id"], seed_subject["id"], seed_kp["id"], content)

        r1 = await client.post("/api/v1/questions/from-ocr", headers=headers, json=payload)
        assert r1.status_code == 200
        assert r1.json()["duplicated"] is False

        r2 = await client.post("/api/v1/questions/from-ocr", headers=headers, json=payload)
        assert r2.status_code == 200
        assert r2.json()["duplicated"] is True
        assert r2.json()["question_id"] == r1.json()["question_id"]

        cnt = await db_session.execute(
            select(func.count()).select_from(Question).where(Question.source == "ugc")
        )
        assert cnt.scalar_one() == 1

    async def test_confirm_unknown_upload_404(self, client, registered_user, seed_subject, seed_kp):
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/questions/from-ocr",
            headers=headers,
            json=_confirm_payload(str(uuid.uuid4()), seed_subject["id"], seed_kp["id"], "题"),
        )
        assert resp.status_code == 404

    async def test_confirm_other_user_upload_404(
        self, client, registered_user, seed_subject, seed_kp
    ):
        """不能确认他人的 upload（数据隔离）。"""
        _, _, _, headers_a = registered_user
        up = await _do_upload(client, headers_a, seed_subject["id"])
        from tests.conftest import _register_user
        _, _, token_b = await _register_user(client, _rand("user_b"))
        headers_b = {"Authorization": f"Bearer {token_b}"}
        resp = await client.post(
            "/api/v1/questions/from-ocr",
            headers=headers_b,
            json=_confirm_payload(up["upload_id"], seed_subject["id"], seed_kp["id"], "题"),
        )
        assert resp.status_code == 404
