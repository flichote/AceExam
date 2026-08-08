"""Tests for M5 AI course_matcher service (T31).

Covers:
  - Name normalization
  - Alias exact match (strategy='alias')
  - AI semantic match (mocked LLM)
  - JSON parsing robustness
  - Empty/no-match edge cases
  - Error fallback

All external dependencies (LLM gateway) are mocked.
"""

import json
import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.ai.course_matcher import (
    CourseCandidate,
    CourseMatcherService,
    normalize_course_name,
    course_matcher,
)

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════════
# Normalization
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeCourseName:
    """Test course name normalization."""

    def test_strips_brackets(self):
        assert normalize_course_name("高等数学（上）") == "高等数学"

    def test_strips_semester(self):
        assert normalize_course_name("2026春 高等数学A") == "高等数学a"

    def test_strips_whitespace(self):
        assert normalize_course_name("  高等 数学  ") == "高等数学"

    def test_strips_parens(self):
        assert normalize_course_name("高等数学(同济第七版)") == "高等数学"

    def test_lowercase(self):
        assert normalize_course_name("Advanced Math") == "advancedmath"

    def test_empty(self):
        assert normalize_course_name("") == ""

    def test_complex_name(self):
        name = "清华大学 2026春 高等数学A（上）"
        result = normalize_course_name(name)
        assert "2026" not in result
        assert "春" not in result
        assert "（" not in result
        assert ")" not in result
        assert "清华大学" in result


# ═══════════════════════════════════════════════════════════════════════════
# Alias match
# ═══════════════════════════════════════════════════════════════════════════


class TestAliasMatch:
    """Test alias exact-match strategy."""

    async def test_alias_hit_single_candidate(self, db_session):
        """Normalized name matches a verified alias → source='alias', confidence=1.0."""
        from app.db.models import CourseAlias, Subject

        # Seed a template subject
        subj = Subject(
            id=uuid.uuid4(),
            code="math_gaoshu",
            name="高等数学",
            level="public",
            is_active=True,
            is_public=True,
        )
        db_session.add(subj)

        # Seed an alias
        alias = CourseAlias(
            id=uuid.uuid4(),
            alias="高等数学a",
            template_subject_id=subj.id,
            source="seed",
            is_verified=True,
        )
        db_session.add(alias)
        await db_session.commit()

        svc = CourseMatcherService()
        # Input normalizes to "高等数学a" which matches the alias
        result = await svc.match(db_session, "高等数学A")

        assert result.strategy == "alias"
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.confidence == 1.0
        assert c.source == "alias"
        assert "精确命中" in c.reason
        assert c.name == "高等数学"

    async def test_alias_no_match_falls_to_ai(self, db_session):
        """No alias hit → falls through to AI match."""
        from app.db.models import Subject

        subj = Subject(
            id=uuid.uuid4(),
            code="math_xiandai",
            name="线性代数",
            level="public",
            is_active=True,
            is_public=True,
        )
        db_session.add(subj)
        await db_session.commit()

        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps([
                {
                    "template_subject_id": str(subj.id),
                    "name": "线性代数",
                    "code": "math_xiandai",
                    "confidence": 0.85,
                    "reason": "语义匹配",
                }
            ]),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 50, "completion_tokens": 30},
        }

        svc = CourseMatcherService(gateway=mock_gateway)
        result = await svc.match(db_session, "线性代数B")

        assert result.strategy == "ai"
        assert len(result.candidates) == 1
        assert result.candidates[0].source == "ai"
        assert result.candidates[0].confidence == 0.85


# ═══════════════════════════════════════════════════════════════════════════
# AI match (mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════


class TestAIMatch:
    """Test AI semantic matching with mocked LLM."""

    async def test_ai_match_returns_candidates(self, db_session):
        """AI returns valid candidates → parsed correctly."""
        from app.db.models import Subject

        subj = Subject(
            id=uuid.uuid4(),
            code="math_gaoshu",
            name="高等数学",
            level="public",
            is_active=True,
            is_public=True,
        )
        db_session.add(subj)
        await db_session.commit()

        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps([
                {
                    "template_subject_id": str(subj.id),
                    "name": "高等数学",
                    "code": "math_gaoshu",
                    "confidence": 0.92,
                    "reason": "课程名高度相似",
                }
            ]),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 60, "completion_tokens": 40},
        }

        svc = CourseMatcherService(gateway=mock_gateway)
        result = await svc.match(db_session, "高等数学一")

        assert result.strategy == "ai"
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.template_subject_id == str(subj.id)
        assert c.name == "高等数学"
        assert c.confidence == 0.92
        assert c.source == "ai"

    async def test_ai_match_multiple_candidates(self, db_session):
        """AI returns multiple candidates → sorted by confidence."""
        from app.db.models import Subject

        s1 = Subject(id=uuid.uuid4(), code="math_gaoshu", name="高等数学", level="public", is_active=True, is_public=True)
        s2 = Subject(id=uuid.uuid4(), code="math_xiandai", name="线性代数", level="public", is_active=True, is_public=True)
        db_session.add_all([s1, s2])
        await db_session.commit()

        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps([
                {"template_subject_id": str(s2.id), "name": "线性代数", "code": "math_xiandai", "confidence": 0.6, "reason": "部分匹配"},
                {"template_subject_id": str(s1.id), "name": "高等数学", "code": "math_gaoshu", "confidence": 0.88, "reason": "语义匹配"},
            ]),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 50, "completion_tokens": 60},
        }

        svc = CourseMatcherService(gateway=mock_gateway)
        result = await svc.match(db_session, "高等数学A")

        assert result.strategy == "ai"
        assert len(result.candidates) == 2
        assert result.candidates[0].confidence == 0.88  # higher first
        assert result.candidates[1].confidence == 0.6

    async def test_ai_match_no_candidates(self, db_session):
        """AI returns empty list → no candidates."""
        from app.db.models import Subject

        subj = Subject(id=uuid.uuid4(), code="math_gaoshu", name="高等数学", level="public", is_active=True, is_public=True)
        db_session.add(subj)
        await db_session.commit()

        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": "[]",
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 40, "completion_tokens": 5},
        }

        svc = CourseMatcherService(gateway=mock_gateway)
        result = await svc.match(db_session, "量子力学")

        assert result.strategy == "ai"
        assert result.candidates == []

    async def test_ai_match_empty_template_pool(self, db_session):
        """No public template subjects → no candidates."""
        # No subjects seeded
        svc = CourseMatcherService(gateway=AsyncMock())
        result = await svc.match(db_session, "高等数学")

        assert result.strategy == "ai"
        assert result.candidates == []

    async def test_ai_match_llm_error_fallback(self, db_session):
        """LLM error → graceful fallback with empty candidates."""
        from app.db.models import Subject

        subj = Subject(id=uuid.uuid4(), code="math_gaoshu", name="高等数学", level="public", is_active=True, is_public=True)
        db_session.add(subj)
        await db_session.commit()

        mock_gateway = AsyncMock()
        mock_gateway.chat.side_effect = Exception("Network error")

        svc = CourseMatcherService(gateway=mock_gateway)
        result = await svc.match(db_session, "高等数学")

        assert result.strategy == "ai"
        assert result.candidates == []  # graceful fallback


# ═══════════════════════════════════════════════════════════════════════════
# JSON parsing robustness
# ═══════════════════════════════════════════════════════════════════════════


class TestJSONParsing:
    """Test robust JSON extraction from LLM outputs."""

    def test_plain_json_array(self):
        content = json.dumps([
            {"template_subject_id": "abc", "name": "高数", "code": "math_gaoshu", "confidence": 0.9, "reason": "匹配"}
        ])
        result = CourseMatcherService._parse_candidates_json(content, limit=5)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_markdown_fenced_json(self):
        content = '```json\n[{"template_subject_id": "abc", "name": "高数", "code": "math_gaoshu", "confidence": 0.85, "reason": "匹配"}]\n```'
        result = CourseMatcherService._parse_candidates_json(content, limit=5)
        assert len(result) == 1
        assert result[0].confidence == 0.85

    def test_json_with_surrounding_text(self):
        content = '根据分析，以下是匹配结果：\n[{"template_subject_id": "abc", "name": "高数", "code": "math_gaoshu", "confidence": 0.88, "reason": "匹配"}]'
        result = CourseMatcherService._parse_candidates_json(content, limit=5)
        assert len(result) == 1

    def test_garbled_text(self):
        result = CourseMatcherService._parse_candidates_json("这不是 JSON", limit=5)
        assert result == []

    def test_empty_input(self):
        result = CourseMatcherService._parse_candidates_json("", limit=5)
        assert result == []

    def test_filters_low_confidence(self):
        content = json.dumps([
            {"template_subject_id": "abc", "name": "高数", "code": "math_gaoshu", "confidence": 0.92, "reason": "高匹配"},
            {"template_subject_id": "def", "name": "其他", "code": "other", "confidence": 0.3, "reason": "低匹配"},
        ])
        result = CourseMatcherService._parse_candidates_json(content, limit=5)
        assert len(result) == 1
        assert result[0].confidence == 0.92

    def test_clamps_confidence(self):
        content = json.dumps([
            {"template_subject_id": "abc", "name": "高数", "code": "math_gaoshu", "confidence": 1.5, "reason": "溢出"},
        ])
        result = CourseMatcherService._parse_candidates_json(content, limit=5)
        assert result[0].confidence == 1.0

    def test_respects_limit(self):
        items = [
            {"template_subject_id": str(i), "name": f"course_{i}", "code": f"c{i}", "confidence": 0.9, "reason": "ok"}
            for i in range(10)
        ]
        content = json.dumps(items)
        result = CourseMatcherService._parse_candidates_json(content, limit=3)
        assert len(result) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════


class TestSingleton:
    """Test module-level singleton."""

    def test_singleton_exists(self):
        assert course_matcher is not None
        assert isinstance(course_matcher, CourseMatcherService)
