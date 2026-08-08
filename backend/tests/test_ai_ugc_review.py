"""Tests for M5 AI ugc_review service (T31).

Covers:
  - Rule-based checks (content completeness, answer consistency, numeric validation)
  - AI deep review (mocked LLM)
  - Verdict pass/reject with confidence
  - Issue aggregation (rule + AI)
  - Edge cases: empty content, missing options, invalid answers
  - Error fallback

All external dependencies (LLM gateway) are mocked.
"""

import json
from unittest.mock import AsyncMock

import pytest

from app.services.ai.ugc_review import (
    UGCReviewResult,
    UGCReviewService,
    _check_content_completeness,
    _check_answer_consistency,
    _check_numeric_validation,
    ugc_reviewer,
)

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════════
# Rule-based: content completeness
# ═══════════════════════════════════════════════════════════════════════════


class TestContentCheck:
    """Test content completeness checks (no LLM)."""

    def test_valid_content_passes(self):
        issues = _check_content_completeness(
            "求函数 f(x) = x^2 + 2x + 1 在区间 [0, 1] 上的最大值"
        )
        assert issues == []

    def test_empty_content_fails(self):
        issues = _check_content_completeness("")
        assert len(issues) == 1
        assert issues[0].field == "content"
        assert "空" in issues[0].reason

    def test_too_short_content_fails(self):
        issues = _check_content_completeness("求导")
        assert len(issues) >= 1
        assert any("短" in i.reason for i in issues)

    def test_gibberish_content_fails(self):
        issues = _check_content_completeness("123 456 789")
        assert len(issues) >= 1
        assert any("有效字符" in i.reason for i in issues)


# ═══════════════════════════════════════════════════════════════════════════
# Rule-based: answer consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestAnswerConsistency:
    """Test answer-options consistency checks (no LLM)."""

    def test_single_choice_answer_in_options(self):
        options = [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}, {"key": "C", "text": "3"}, {"key": "D", "text": "4"}]
        issues = _check_answer_consistency("single", "C", options)
        assert issues == []

    def test_single_choice_answer_dict(self):
        options = [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}]
        issues = _check_answer_consistency("single", {"correct": "B"}, options)
        assert issues == []

    def test_single_choice_answer_not_in_options(self):
        options = [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}]
        issues = _check_answer_consistency("single", "Z", options)
        assert len(issues) == 1
        assert "不在选项" in issues[0].reason
        assert "'Z'" in issues[0].reason

    def test_multi_choice_answers_in_options(self):
        options = [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}, {"key": "C", "text": "3"}]
        issues = _check_answer_consistency("multi", ["A", "C"], options)
        assert issues == []

    def test_multi_choice_bad_answer(self):
        options = [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}]
        issues = _check_answer_consistency("multi", ["A", "D"], options)
        assert len(issues) == 1
        assert "'D'" in issues[0].reason or "D" in issues[0].reason

    def test_choice_without_options(self):
        issues = _check_answer_consistency("single", "A", None)
        assert len(issues) == 1
        assert "缺少选项" in issues[0].reason

    def test_empty_answer(self):
        issues = _check_answer_consistency("single", "", [{"key": "A", "text": "1"}])
        assert len(issues) == 1
        assert "为空" in issues[0].reason

    def test_blank_answer_non_empty(self):
        issues = _check_answer_consistency("blank", "x^3/3 + C", None)
        assert issues == []

    def test_blank_answer_empty(self):
        issues = _check_answer_consistency("blank", "", None)
        assert len(issues) >= 1
        assert any("答案为空" in i.reason for i in issues)


# ═══════════════════════════════════════════════════════════════════════════
# Rule-based: numeric validation
# ═══════════════════════════════════════════════════════════════════════════


class TestNumericValidation:
    """Test lightweight numeric backward validation."""

    def test_power_rule_correct(self):
        """f(x)=x^3 at x=1 → derivative=3 → matches."""
        issues = _check_numeric_validation(
            "求函数 f(x)=x^3 在 x=1 处的导数", "3"
        )
        assert issues == []

    def test_power_rule_incorrect(self):
        """f(x)=x^3 at x=1 → derivative=3 → given answer=2 → flagged."""
        issues = _check_numeric_validation(
            "求函数 f(x)=x^3 在 x=1 处的导数", "2"
        )
        assert len(issues) == 1
        assert "数值验算不匹配" in issues[0].reason

    def test_non_numeric_answer_skips(self):
        """Non-numeric answer like 'x^2' → no validation."""
        issues = _check_numeric_validation(
            "求函数 f(x)=x^3 在 x=1 处的导数", "3x^2"
        )
        assert issues == []

    def test_no_power_pattern_skips(self):
        """No f(x)=x^n pattern → no validation."""
        issues = _check_numeric_validation(
            "计算 1+1", "2"
        )
        assert issues == []

    def test_dict_answer(self):
        """Dict answer with correct key."""
        issues = _check_numeric_validation(
            "求函数 f(x)=x^3 在 x=1 处的导数", {"correct": "2"}
        )
        assert len(issues) == 1  # wrong value


# ═══════════════════════════════════════════════════════════════════════════
# AI review (mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════


class TestUGCReviewAI:
    """Test full review pipeline with mocked LLM."""

    async def test_pass_clean_question(self):
        """Clean question → pass with high confidence."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps({
                "verdict": "pass",
                "confidence": 0.9,
                "issues": [],
                "suggested_fix": "",
            }),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="求函数 f(x)=x^3 在 x=1 处的导数是多少？",
            qtype="single",
            answer="C",
            options=[
                {"key": "A", "text": "1"},
                {"key": "B", "text": "2"},
                {"key": "C", "text": "3"},
                {"key": "D", "text": "0"},
            ],
            analysis="f'(x)=3x^2, f'(1)=3",
            knowledge_point_name="导数计算",
        )

        assert result.verdict == "pass"
        assert result.confidence == 0.9
        assert result.issues == []

    async def test_reject_bad_answer(self):
        """Wrong answer + AI flags it → reject."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps({
                "verdict": "reject",
                "confidence": 0.95,
                "issues": [
                    {"field": "answer", "reason": "答案不正确，导数应为 3"}
                ],
                "suggested_fix": "请将答案修改为 C（3）",
            }),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 100, "completion_tokens": 60},
        }

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="求函数 f(x)=x^3 在 x=1 处的导数是多少？",
            qtype="single",
            answer="A",  # wrong
            options=[
                {"key": "A", "text": "1"},
                {"key": "B", "text": "2"},
                {"key": "C", "text": "3"},
                {"key": "D", "text": "0"},
            ],
        )

        assert result.verdict == "reject"
        assert len(result.issues) >= 1
        assert result.suggested_fix != ""

    async def test_empty_content_reject(self):
        """Empty content → hard reject without LLM call."""
        mock_gateway = AsyncMock()
        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(content="", qtype="single", answer="A")

        assert result.verdict == "reject"
        assert result.confidence == 1.0
        assert any("题干为空" in i.reason for i in result.issues)
        # Should not have called LLM at all (hard reject)
        mock_gateway.chat.assert_not_called()

    async def test_answer_not_in_options_reject(self):
        """Answer key not in options → reject via rule check."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps({
                "verdict": "pass",
                "confidence": 0.9,
                "issues": [],
                "suggested_fix": "",
            }),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 80, "completion_tokens": 40},
        }

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="求函数 f(x)=x^3 在 x=1 处的导数是多少？",
            qtype="single",
            answer="Z",  # not in options
            options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        )

        # Rule check catches bad answer → reject even though AI says pass
        assert result.verdict == "reject"

    async def test_numeric_mismatch_reject(self):
        """Numeric validation mismatch → reject."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps({
                "verdict": "pass",
                "confidence": 0.9,
                "issues": [],
                "suggested_fix": "",
            }),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 80, "completion_tokens": 40},
        }

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="求函数 f(x)=x^3 在 x=1 处的导数",
            qtype="blank",
            answer="2",  # wrong, should be 3
        )

        assert result.verdict == "reject"
        assert any("数值验算" in i.reason for i in result.issues)

    async def test_rule_issues_downgrade_confidence(self):
        """Rule issues downgrade AI confidence."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps({
                "verdict": "pass",
                "confidence": 0.95,
                "issues": [],
                "suggested_fix": "",
            }),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 80, "completion_tokens": 40},
        }

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="短",  # too short, rule issue
            qtype="single",
            answer="A",
            options=[{"key": "A", "text": "1"}],
        )

        assert result.verdict == "pass"
        assert result.confidence <= 0.85  # downgraded

    async def test_llm_error_fallback(self):
        """LLM error → graceful fallback with pass/low confidence."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.side_effect = Exception("API timeout")

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="求函数 f(x)=x^3 在 x=1 处的导数是多少？",
            qtype="single",
            answer="C",
            options=[{"key": "A", "text": "1"}, {"key": "C", "text": "3"}],
        )

        assert result.verdict == "pass"
        assert result.confidence == 0.5

    async def test_pro_tier_on_low_confidence(self):
        """use_pro=True → calls pro tier."""
        mock_gateway = AsyncMock()
        mock_gateway.chat.return_value = {
            "content": json.dumps({
                "verdict": "pass",
                "confidence": 0.92,
                "issues": [],
                "suggested_fix": "",
            }),
            "model": "deepseek-reasoner",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        svc = UGCReviewService(gateway=mock_gateway)
        result = await svc.review(
            content="证明：若函数 f(x) 在 [a,b] 上连续，在 (a,b) 内可导，且 f(a)=f(b)，则存在 ξ∈(a,b) 使得 f'(ξ)=0",
            qtype="essay",
            answer={"key_points": ["罗尔定理"]},
            use_pro=True,
        )

        assert result.verdict == "pass"
        # Verify pro tier was called
        call_args = mock_gateway.chat.call_args
        assert call_args is not None  # was actually called
        assert call_args[0][0] == "pro"


# ═══════════════════════════════════════════════════════════════════════════
# JSON parsing robustness
# ═══════════════════════════════════════════════════════════════════════════


class TestReviewJSONParsing:
    """Test robust JSON extraction from LLM review outputs."""

    def test_plain_json(self):
        content = json.dumps({
            "verdict": "pass",
            "confidence": 0.85,
            "issues": [{"field": "content", "reason": "略短"}],
            "suggested_fix": "",
        })
        result = UGCReviewService._parse_review_json(content)
        assert result["verdict"] == "pass"
        assert result["confidence"] == 0.85
        assert len(result["issues"]) == 1

    def test_markdown_fenced(self):
        content = '```json\n{"verdict": "reject", "confidence": 0.9, "issues": [], "suggested_fix": "修改答案"}\n```'
        result = UGCReviewService._parse_review_json(content)
        assert result["verdict"] == "reject"
        assert result["suggested_fix"] == "修改答案"

    def test_surrounding_text(self):
        content = '审查结果：{"verdict": "pass", "confidence": 0.8, "issues": [], "suggested_fix": ""}'
        result = UGCReviewService._parse_review_json(content)
        assert result["verdict"] == "pass"
        assert result["confidence"] == 0.8

    def test_invalid_verdict_falls_to_pass(self):
        content = json.dumps({"verdict": "flag", "confidence": 0.8, "issues": [], "suggested_fix": ""})
        result = UGCReviewService._parse_review_json(content)
        assert result["verdict"] == "pass"

    def test_confidence_clamped(self):
        content = json.dumps({"verdict": "pass", "confidence": 2.5, "issues": [], "suggested_fix": ""})
        result = UGCReviewService._parse_review_json(content)
        assert result["confidence"] == 1.0

    def test_garbage_input(self):
        result = UGCReviewService._parse_review_json("not json at all")
        assert result["verdict"] == "pass"
        assert result["confidence"] == 0.5

    def test_empty_input(self):
        result = UGCReviewService._parse_review_json("")
        assert result["verdict"] == "pass"
        assert result["confidence"] == 0.5

    def test_suggested_fix_truncated(self):
        long_fix = "x" * 1000
        content = json.dumps({"verdict": "reject", "confidence": 0.9, "issues": [], "suggested_fix": long_fix})
        result = UGCReviewService._parse_review_json(content)
        assert len(result["suggested_fix"]) <= 500


# ═══════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════


class TestSingleton:
    """Test module-level singleton."""

    def test_singleton_exists(self):
        assert ugc_reviewer is not None
        assert isinstance(ugc_reviewer, UGCReviewService)
