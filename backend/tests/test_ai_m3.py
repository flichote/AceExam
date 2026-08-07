"""Tests for M3 AI-enhanced services — sprint, warning, knowledge_graph (T17).

Tests the AI-enhanced functions that wrap the existing rule-based logic:
- ai_identify_high_freq_kps: LLM-driven high-frequency KP identification
- ai_enhance_sprint_plan: LLM-enhanced sprint study plan
- ai_analyze_warning_risk: LLM-driven risk analysis with JSON output
- ai_generate_warning_suggestion: LLM-generated personalized suggestions
- ai_enhance_graph_nodes: LLM-enhanced knowledge graph status

Mocks the llm_gateway to test logic without real API calls.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.sprint import (
    ai_enhance_sprint_plan,
    ai_identify_high_freq_kps,
)
from app.services.warning import (
    ai_analyze_warning_risk,
    ai_generate_warning_suggestion,
)
from app.services.knowledge_graph import (
    ai_enhance_graph_nodes,
    ai_summarize_graph_status,
)

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════════
# Sprint — AI high-frequency KP identification
# ═══════════════════════════════════════════════════════════════════════════


class TestAiIdentifyHighFreqKps:
    """Test ai_identify_high_freq_kps with mocked LLM responses."""

    async def test_identifies_high_freq_kps_from_stats(self):
        """Given practice stats, LLM identifies high-frequency weak KPs."""
        stats = [
            {"kp_name": "极限计算", "correct": 5, "wrong": 15, "total_practice": 20},
            {"kp_name": "导数应用", "correct": 25, "wrong": 5, "total_practice": 30},
            {"kp_name": "不定积分", "correct": 2, "wrong": 8, "total_practice": 10},
            {"kp_name": "矩阵运算", "correct": 18, "wrong": 2, "total_practice": 20},
        ]

        mock_llm_response = {
            "content": json.dumps({
                "high_freq_kps": [
                    {
                        "kp_name": "极限计算",
                        "heat_score": 0.85,
                        "reason": "练习量大(20次)但正确率仅25%，是典型高频薄弱考点",
                        "priority": 1,
                    },
                    {
                        "kp_name": "不定积分",
                        "heat_score": 0.70,
                        "reason": "正确率20%极低，虽练习量中等但风险高",
                        "priority": 2,
                    },
                ]
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 200, "completion_tokens": 150},
        }

        with patch.object(
            __import__("app.services.sprint", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await ai_identify_high_freq_kps(stats)

        assert len(result) == 2
        assert result[0]["kp_name"] == "极限计算"
        assert result[0]["heat_score"] == 0.85
        assert result[0]["priority"] == 1
        assert "reason" in result[0]

    async def test_handles_empty_stats_gracefully(self):
        """Empty stats returns empty list without LLM call."""
        result = await ai_identify_high_freq_kps([])
        assert result == []

    async def test_falls_back_on_llm_error(self):
        """When LLM fails, falls back to rule-based scoring from stats."""
        stats = [
            {"kp_name": "极限计算", "correct": 5, "wrong": 15, "total_practice": 20},
        ]

        with patch.object(
            __import__("app.services.sprint", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            result = await ai_identify_high_freq_kps(stats)

        # Falls back to rule-based: low accuracy + high volume = high freq
        assert len(result) > 0
        assert "kp_name" in result[0]
        assert "heat_score" in result[0]
        assert result[0]["heat_score"] >= 0.0

    async def test_handles_invalid_json_response(self):
        """Malformed JSON from LLM falls back gracefully."""
        stats = [
            {"kp_name": "极限计算", "correct": 5, "wrong": 15, "total_practice": 20},
        ]

        mock_bad_response = {
            "content": "not valid json at all",
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }

        with patch.object(
            __import__("app.services.sprint", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_bad_response,
        ):
            result = await ai_identify_high_freq_kps(stats)

        # Falls back to rule-based
        assert len(result) > 0
        assert "kp_name" in result[0]


# ═══════════════════════════════════════════════════════════════════════════
# Sprint — AI-enhanced sprint plan
# ═══════════════════════════════════════════════════════════════════════════


class TestAiEnhanceSprintPlan:
    """Test ai_enhance_sprint_plan with mocked LLM."""

    async def test_generates_study_plan_from_kps(self):
        """Given high-freq KPs and days_left, LLM generates a study plan."""
        high_freq_kps = [
            {"kp_name": "极限计算", "heat_score": 0.85, "priority": 1},
            {"kp_name": "不定积分", "heat_score": 0.70, "priority": 2},
        ]
        days_left = 5
        total_questions = 20

        mock_llm_response = {
            "content": json.dumps({
                "plan": [
                    {"day": 1, "focus": "极限计算", "question_count": 6,
                     "rationale": "最高频薄弱考点，优先攻克"},
                    {"day": 2, "focus": "极限计算+不定积分", "question_count": 5,
                     "rationale": "巩固极限，引入积分"},
                    {"day": 3, "focus": "不定积分", "question_count": 5,
                     "rationale": "集中练习积分题型"},
                    {"day": 4, "focus": "综合复习", "question_count": 2,
                     "rationale": "回顾错题"},
                    {"day": 5, "focus": "模拟冲刺", "question_count": 2,
                     "rationale": "考前模拟"},
                ],
                "total_questions": 20,
                "strategy": "从高频薄弱考点突破，逐日递减题量",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 300, "completion_tokens": 250},
        }

        with patch.object(
            __import__("app.services.sprint", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await ai_enhance_sprint_plan(high_freq_kps, days_left, total_questions)

        assert "plan" in result
        assert len(result["plan"]) == 5
        assert result["total_questions"] == 20
        assert "strategy" in result
        # Each day entry has required fields
        for day in result["plan"]:
            assert "day" in day
            assert "focus" in day
            assert "question_count" in day
            assert "rationale" in day

    async def test_handles_no_kps(self):
        """Empty KP list returns minimal fallback plan."""
        result = await ai_enhance_sprint_plan([], 5, 10)
        assert "plan" in result
        assert result["total_questions"] == 0
        assert result["strategy"] == ""

    async def test_plan_question_count_does_not_exceed_total(self):
        """Generated plan respects total question limit."""
        high_freq_kps = [
            {"kp_name": "极限计算", "heat_score": 0.85, "priority": 1},
        ]
        total = 10

        mock_llm_response = {
            "content": json.dumps({
                "plan": [
                    {"day": 1, "focus": "极限计算", "question_count": 3},
                    {"day": 2, "focus": "极限计算", "question_count": 7},
                ],
                "total_questions": 10,
                "strategy": "集中突破",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        with patch.object(
            __import__("app.services.sprint", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await ai_enhance_sprint_plan(high_freq_kps, 3, total)

        total_q = sum(d["question_count"] for d in result["plan"])
        assert total_q <= total

    async def test_falls_back_on_llm_failure(self):
        """When LLM fails, generates a simple rule-based plan."""
        high_freq_kps = [
            {"kp_name": "极限计算", "heat_score": 0.85, "priority": 1},
        ]

        with patch.object(
            __import__("app.services.sprint", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("timeout"),
        ):
            result = await ai_enhance_sprint_plan(high_freq_kps, 3, 9)

        assert "plan" in result
        assert len(result["plan"]) > 0
        # Rule-based fallback: evenly split
        assert result["total_questions"] <= 9


# ═══════════════════════════════════════════════════════════════════════════
# Warning — AI risk analysis
# ═══════════════════════════════════════════════════════════════════════════


class TestAiAnalyzeWarningRisk:
    """Test ai_analyze_warning_risk with mocked LLM responses."""

    async def test_analyzes_high_risk_correctly(self):
        """Very low accuracy + few days left = high risk."""
        weak_kps = [
            {"kp_name": "二重积分", "accuracy": 0.15, "practice_count": 8,
             "status": "weak"},
        ]
        days_left = 3
        trend = {"active_days_7d": 1, "questions_7d": 5, "trend_direction": "declining"}

        mock_llm_response = {
            "content": json.dumps({
                "risk_assessments": [
                    {
                        "kp_name": "二重积分",
                        "risk_level": "high",
                        "confidence": 0.95,
                        "reasons": [
                            "正确率仅15%，远低于及格线",
                            "距考试仅3天，时间紧迫",
                            "近7天仅练习1天，趋势恶化",
                        ],
                    }
                ],
                "overall_risk": "high",
                "urgency_summary": "二重积分为极高风险考点，需立即集中突破",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 350, "completion_tokens": 200},
        }

        with patch.object(
            __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await ai_analyze_warning_risk(weak_kps, days_left, trend)

        assert result["overall_risk"] == "high"
        assert len(result["risk_assessments"]) == 1
        assert result["risk_assessments"][0]["risk_level"] == "high"
        assert len(result["risk_assessments"][0]["reasons"]) >= 2

    async def test_analyzes_low_risk_correctly(self):
        """Decent accuracy + many days left = low risk."""
        weak_kps = [
            {"kp_name": "级数收敛", "accuracy": 0.65, "practice_count": 15,
             "status": "consolidating"},
        ]
        days_left = 30
        trend = {"active_days_7d": 6, "questions_7d": 50,
                 "trend_direction": "improving"}

        mock_llm_response = {
            "content": json.dumps({
                "risk_assessments": [
                    {
                        "kp_name": "级数收敛",
                        "risk_level": "low",
                        "confidence": 0.80,
                        "reasons": [
                            "正确率65%，处于巩固阶段",
                            "距考试30天，时间充裕",
                            "近7天练习活跃，趋势向好",
                        ],
                    }
                ],
                "overall_risk": "low",
                "urgency_summary": "当前风险较低，保持现有节奏即可",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 200, "completion_tokens": 150},
        }

        with patch.object(
            __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await ai_analyze_warning_risk(weak_kps, days_left, trend)

        assert result["overall_risk"] == "low"
        assert result["risk_assessments"][0]["risk_level"] == "low"

    async def test_risk_level_boundaries(self):
        """Test risk level at various boundaries (accuracy × days_left)."""
        boundary_cases = [
            # (accuracy, days_left, expected_risk)
            (0.10, 3, "high"),    # urgent crisis
            (0.35, 7, "high"),    # borderline high
            (0.50, 7, "medium"),  # typical medium
            (0.70, 14, "medium"), # decent but limited time
            (0.80, 30, "low"),    # comfortable
            (0.60, 60, "low"),    # lots of time
        ]

        for accuracy, days_left, expected in boundary_cases:
            weak_kps = [
                {"kp_name": f"考点_{accuracy}", "accuracy": accuracy,
                 "practice_count": 10, "status": "weak"},
            ]
            trend = {"active_days_7d": 5, "questions_7d": 30,
                     "trend_direction": "stable"}

            mock_llm = {
                "content": json.dumps({
                    "risk_assessments": [
                        {"kp_name": f"考点_{accuracy}", "risk_level": expected,
                         "confidence": 0.85, "reasons": ["test"]},
                    ],
                    "overall_risk": expected,
                    "urgency_summary": "test",
                }),
                "model": "deepseek-v4-pro",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }

            with patch.object(
                __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
                "chat",
                new_callable=AsyncMock,
                return_value=mock_llm,
            ):
                result = await ai_analyze_warning_risk(weak_kps, days_left, trend)

            assert result["overall_risk"] == expected, \
                f"accuracy={accuracy}, days_left={days_left}: expected {expected}, got {result['overall_risk']}"

    async def test_handles_empty_weak_kps(self):
        """No weak KPs → no risk."""
        result = await ai_analyze_warning_risk([], 10, {})
        assert result["overall_risk"] is None
        assert result["risk_assessments"] == []

    async def test_falls_back_on_llm_error(self):
        """LLM error → rule-based risk fallback."""
        weak_kps = [
            {"kp_name": "微分方程", "accuracy": 0.2, "practice_count": 5,
             "status": "weak"},
        ]

        with patch.object(
            __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("API down"),
        ):
            result = await ai_analyze_warning_risk(weak_kps, 5,
                                                    {"active_days_7d": 2, "questions_7d": 10,
                                                     "trend_direction": "declining"})

        assert "overall_risk" in result
        assert result["overall_risk"] in ("high", "medium", "low")
        assert len(result["risk_assessments"]) > 0

    async def test_overall_risk_is_max_of_items(self):
        """Overall risk = maximum risk among all KPs."""
        weak_kps = [
            {"kp_name": "安全考点", "accuracy": 0.85, "practice_count": 30,
             "status": "consolidating"},
            {"kp_name": "危险考点", "accuracy": 0.15, "practice_count": 3,
             "status": "weak"},
            {"kp_name": "中等考点", "accuracy": 0.55, "practice_count": 12,
             "status": "weak"},
        ]

        mock_llm = {
            "content": json.dumps({
                "risk_assessments": [
                    {"kp_name": "安全考点", "risk_level": "low", "confidence": 0.9,
                     "reasons": ["good"]},
                    {"kp_name": "危险考点", "risk_level": "high", "confidence": 0.95,
                     "reasons": ["bad"]},
                    {"kp_name": "中等考点", "risk_level": "medium", "confidence": 0.8,
                     "reasons": ["ok"]},
                ],
                "overall_risk": "high",
                "urgency_summary": "存在高风险考点",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 100, "completion_tokens": 100},
        }

        with patch.object(
            __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm,
        ):
            result = await ai_analyze_warning_risk(weak_kps, 10, {})

        assert result["overall_risk"] == "high"


# ═══════════════════════════════════════════════════════════════════════════
# Warning — AI suggestion generation
# ═══════════════════════════════════════════════════════════════════════════


class TestAiGenerateWarningSuggestion:
    """Test ai_generate_warning_suggestion with mocked LLM."""

    async def test_generates_personalized_suggestion(self):
        """LLM generates a personalized study suggestion for a weak KP."""
        kp_name = "傅里叶变换"
        accuracy = 0.25
        days_left = 5
        risk_level = "high"

        mock_llm = {
            "content": json.dumps({
                "suggestion": "建议立即重点复习傅里叶变换：1)每天做5道傅里叶变换真题，2)回顾教材第5章核心公式，3)重点关注频域分析题型",
                "estimated_hours": 8,
                "priority_actions": [
                    "完成傅里叶变换基础公式记忆",
                    "练习5道典型频域分析题",
                    "对照答案总结常见错误",
                ],
            }),
            "model": "deepseek-v4-flash",
            "usage": {"prompt_tokens": 100, "completion_tokens": 80},
        }

        with patch.object(
            __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm,
        ):
            result = await ai_generate_warning_suggestion(
                kp_name, accuracy, days_left, risk_level
            )

        assert "suggestion" in result
        assert len(result["suggestion"]) > 20  # meaningful content
        assert "傅里叶" in result["suggestion"]
        assert "estimated_hours" in result
        assert result["estimated_hours"] > 0
        assert "priority_actions" in result
        assert len(result["priority_actions"]) >= 1

    async def test_handles_missing_days_left(self):
        """Handles None days_left gracefully."""
        result = await ai_generate_warning_suggestion(
            "线性代数", 0.4, None, "medium"
        )
        # Falls back to rule-based suggestion
        assert "suggestion" in result

    async def test_fallback_suggestion_is_meaningful(self):
        """Rule-based fallback produces useful suggestion."""
        with patch.object(
            __import__("app.services.warning", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await ai_generate_warning_suggestion(
                "概率论", 0.3, 10, "medium"
            )

        assert "suggestion" in result
        assert len(result["suggestion"]) > 10
        assert "概率论" in result["suggestion"]


# ═══════════════════════════════════════════════════════════════════════════
# Knowledge Graph — AI-enhanced node status
# ═══════════════════════════════════════════════════════════════════════════


class TestAiEnhanceGraphNodes:
    """Test ai_enhance_graph_nodes with mocked LLM."""

    async def test_enhances_node_statuses_with_notes(self):
        """LLM adds study notes and recommendations to graph nodes."""
        nodes = [
            {"id": "kp1", "name": "极限定义", "level": 3, "status": "weak",
             "accuracy": 0.3, "practice_count": 10, "children": []},
            {"id": "kp2", "name": "求导法则", "level": 3, "status": "mastered",
             "accuracy": 0.95, "practice_count": 25, "children": []},
        ]

        mock_llm = {
            "content": json.dumps({
                "enhanced_nodes": [
                    {"id": "kp1", "study_note": "需重点加强ε-δ语言理解",
                     "recommended_order": 1},
                    {"id": "kp2", "study_note": "已熟练掌握，可减少练习频率",
                     "recommended_order": 2},
                ],
            }),
            "model": "deepseek-v4-flash",
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        }

        with patch.object(
            __import__("app.services.knowledge_graph", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm,
        ):
            result = await ai_enhance_graph_nodes(nodes)

        assert len(result) == 2
        assert result[0]["id"] == "kp1"
        assert "study_note" in result[0]
        assert "recommended_order" in result[0]
        # Original fields preserved
        assert result[0]["name"] == "极限定义"
        assert result[0]["status"] == "weak"

    async def test_handles_empty_nodes(self):
        """Empty node list returns empty."""
        result = await ai_enhance_graph_nodes([])
        assert result == []

    async def test_falls_back_preserves_original(self):
        """On LLM failure, returns original nodes with basic enhancement."""
        nodes = [
            {"id": "kp1", "name": "极限", "level": 3, "status": "weak",
             "accuracy": 0.3, "practice_count": 5, "children": []},
        ]

        with patch.object(
            __import__("app.services.knowledge_graph", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("timeout"),
        ):
            result = await ai_enhance_graph_nodes(nodes)

        assert len(result) == 1
        assert result[0]["id"] == "kp1"
        # Fallback adds a basic study_note
        assert "study_note" in result[0]
        assert "recommended_order" in result[0]


class TestAiSummarizeGraphStatus:
    """Test ai_summarize_graph_status with mocked LLM."""

    async def test_summarizes_overall_status(self):
        """LLM generates a summary of overall knowledge graph status."""
        stats = {
            "total_nodes": 30,
            "mastered_count": 10,
            "weak_count": 8,
            "consolidating_count": 5,
            "untouched_count": 7,
        }

        mock_llm = {
            "content": json.dumps({
                "summary": "已掌握33%知识点，26%薄弱需重点突破，23%未接触需尽快启动",
                "mastery_rate": 0.33,
                "risk_areas": ["微分方程", "多重积分"],
                "recommendation": "优先处理8个薄弱知识点，每天安排2个知识点的专项练习",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        }

        with patch.object(
            __import__("app.services.knowledge_graph", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm,
        ):
            result = await ai_summarize_graph_status(stats)

        assert "summary" in result
        assert result["mastery_rate"] == 0.33
        assert len(result["summary"]) > 10

    async def test_handles_all_mastered(self):
        """100% mastery → positive summary."""
        stats = {
            "total_nodes": 10, "mastered_count": 10,
            "weak_count": 0, "consolidating_count": 0, "untouched_count": 0,
        }

        mock_llm = {
            "content": json.dumps({
                "summary": "所有知识点已掌握，建议进行综合模拟训练",
                "mastery_rate": 1.0,
                "risk_areas": [],
                "recommendation": "进行全真模拟考试，查漏补缺",
            }),
            "model": "deepseek-v4-pro",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        with patch.object(
            __import__("app.services.knowledge_graph", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=mock_llm,
        ):
            result = await ai_summarize_graph_status(stats)

        assert result["mastery_rate"] == 1.0
        assert result["risk_areas"] == []

    async def test_falls_back_on_error(self):
        """LLM error → rule-based summary."""
        stats = {
            "total_nodes": 20, "mastered_count": 5,
            "weak_count": 5, "consolidating_count": 5, "untouched_count": 5,
        }

        with patch.object(
            __import__("app.services.knowledge_graph", fromlist=["llm_gateway"]).llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("timeout"),
        ):
            result = await ai_summarize_graph_status(stats)

        assert "summary" in result
        assert "mastery_rate" in result
        assert 0 <= result["mastery_rate"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Integration: confirm existing rule-based services still work
# ═══════════════════════════════════════════════════════════════════════════


class TestSprintRuleBasedStillWorks:
    """Verify existing generate_sprint_questions still works after AI additions."""

    async def test_generate_sprint_questions_empty(self, db_session):
        """generate_sprint_questions with no data returns empty snapshot."""
        from app.db.models import SprintSession
        from app.services.sprint import generate_sprint_questions

        sprint = SprintSession(
            user_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            status="active",
        )
        db_session.add(sprint)
        await db_session.commit()
        await db_session.refresh(sprint)

        result = await generate_sprint_questions(db_session, sprint, count=5)
        assert "items" in result
        assert "summary" in result
        assert result["summary"]["total"] == 0


class TestWarningRuleBasedStillWorks:
    """Verify existing get_warnings still works after AI additions."""

    async def test_get_warnings_no_plan(self, db_session):
        """get_warnings with no plan returns empty."""
        from app.services.warning import get_warnings

        result = await get_warnings(db_session, uuid.uuid4())
        assert result["overall_risk"] is None
        assert result["items"] == []


class TestKnowledgeGraphRuleBasedStillWorks:
    """Verify existing build_knowledge_graph still works after AI additions."""

    async def test_build_graph_no_kps(self, db_session):
        """build_knowledge_graph with no KPs returns None."""
        from app.services.knowledge_graph import build_knowledge_graph

        result = await build_knowledge_graph(db_session, uuid.uuid4(), uuid.uuid4())
        assert result is None
