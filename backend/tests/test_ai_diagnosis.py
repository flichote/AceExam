"""Tests for diagnosis engine — parsing, summary building, data structures."""

import pytest

from app.services.diagnosis import (
    DiagnosisEngine,
    WeaknessMap,
    WeaknessItem,
    diagnosis_engine,
)


# ═══════════════════════════════════════════════════════════════════════════
# WeaknessMap dataclass
# ═══════════════════════════════════════════════════════════════════════════


class TestWeaknessMap:
    """Test WeaknessMap structure and serialization."""

    def test_empty_map(self):
        wm = WeaknessMap(
            user_id="u1",
            subject_id="s1",
            subject_name="数学",
        )
        assert wm.user_id == "u1"
        assert wm.overall_mastery == 0.0
        assert wm.weak_points == []

    def test_to_dict(self):
        wm = WeaknessMap(
            user_id="u1",
            subject_id="s1",
            subject_name="高等数学",
            overall_mastery=0.65,
            weak_points=[
                WeaknessItem(
                    knowledge_point_id="kp1",
                    knowledge_point_name="极限",
                    mastery_level=0.3,
                    error_rate=0.7,
                    common_mistake_pattern="混淆ε-δ定义",
                    suggested_focus="重新学习极限的严格定义",
                )
            ],
            strengths=["导数计算", "积分"],
            recommendations=["重点复习极限定义"],
        )
        d = wm.to_dict()
        assert d["subject_name"] == "高等数学"
        assert d["overall_mastery"] == 0.65
        assert len(d["weak_points"]) == 1
        assert d["weak_points"][0]["mastery_level"] == 0.3
        assert d["strengths"] == ["导数计算", "积分"]

    def test_to_dict_empty_lists(self):
        wm = WeaknessMap(user_id="u1", subject_id="s1", subject_name="")
        d = wm.to_dict()
        assert d["weak_points"] == []
        assert d["strengths"] == []
        assert d["recommendations"] == []


class TestWeaknessItem:
    """Test WeaknessItem dataclass."""

    def test_defaults(self):
        wi = WeaknessItem()
        assert wi.knowledge_point_name == ""
        assert wi.mastery_level == 0.0
        assert wi.error_rate == 0.0

    def test_full_item(self):
        wi = WeaknessItem(
            knowledge_point_id="kp123",
            knowledge_point_name="拉格朗日中值定理",
            mastery_level=0.25,
            error_rate=0.8,
            common_mistake_pattern="忽略中值定理的适用条件",
            suggested_focus="练习判断何时使用拉格朗日中值定理",
        )
        assert wi.mastery_level == 0.25
        assert "适用条件" in wi.common_mistake_pattern


# ═══════════════════════════════════════════════════════════════════════════
# Summary building (no LLM call)
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildSummary:
    """Test data summary generation for LLM prompt."""

    def test_build_summary_with_states(self):
        states = [
            {
                "knowledge_point_name": "极限",
                "status": "weak",
                "correct_count": 2,
                "wrong_count": 8,
            },
            {
                "knowledge_point_name": "导数",
                "status": "mastered",
                "correct_count": 15,
                "wrong_count": 1,
            },
        ]
        summary = DiagnosisEngine._build_summary(states, None)
        assert "极限" in summary
        assert "导数" in summary
        assert "8/10" in summary or "8" in summary
        assert "weak" in summary

    def test_build_summary_with_errors(self):
        errors = [
            {
                "question_content": "计算 lim(x→0) sin(x)/x",
                "wrong_answer": "0",
                "wrong_reason": "未掌握重要极限",
            }
        ]
        summary = DiagnosisEngine._build_summary(None, errors)
        assert "lim" in summary
        assert "sin" in summary

    def test_build_summary_empty(self):
        summary = DiagnosisEngine._build_summary(None, None)
        assert summary == ""

    def test_build_summary_truncates_errors(self):
        """More than 10 errors should be capped."""
        errors = [
            {"question_content": f"问题{i}", "wrong_answer": f"答案{i}"}
            for i in range(20)
        ]
        summary = DiagnosisEngine._build_summary(None, errors)
        # Should include first 10 items (问题0 through 问题9)
        assert "问题9" in summary
        # Should NOT include item 10 (问题10) — 0-indexed, [0:10] stops at index 9
        assert "问题10" not in summary


# ═══════════════════════════════════════════════════════════════════════════
# Diagnosis JSON parsing
# ═══════════════════════════════════════════════════════════════════════════


class TestParseDiagnosis:
    """Test LLM output parsing for diagnosis JSON."""

    def test_parse_valid_json(self):
        json_str = '''{
            "overall_mastery": 0.55,
            "weak_points": [
                {
                    "knowledge_point_name": "极限",
                    "mastery_level": 0.3,
                    "error_rate": 0.7,
                    "common_mistake_pattern": "定义不清",
                    "suggested_focus": "重新学习"
                }
            ],
            "strengths": ["导数"],
            "recommendations": ["先复习极限"]
        }'''
        parsed = DiagnosisEngine._parse_diagnosis(json_str)
        assert parsed is not None
        assert parsed["overall_mastery"] == 0.55
        assert len(parsed["weak_points"]) == 1

    def test_parse_json_with_code_fence(self):
        json_str = '```json\n{"overall_mastery": 0.8, "weak_points": [], "strengths": ["全部"], "recommendations": []}\n```'
        parsed = DiagnosisEngine._parse_diagnosis(json_str)
        assert parsed is not None
        assert parsed["overall_mastery"] == 0.8

    def test_parse_json_in_text(self):
        text = '诊断结果如下：\n\n```\n{"overall_mastery": 0.6, "weak_points": [], "strengths": [], "recommendations": []}\n```\n\n以上为分析结果。'
        parsed = DiagnosisEngine._parse_diagnosis(text)
        assert parsed is not None
        assert parsed["overall_mastery"] == 0.6

    def test_parse_invalid_json(self):
        assert DiagnosisEngine._parse_diagnosis("不是 JSON") is None
        assert DiagnosisEngine._parse_diagnosis("") is None


# ═══════════════════════════════════════════════════════════════════════════
# Build map from parsed data
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildMap:
    """Test converting parsed JSON into WeaknessMap."""

    def test_build_map_sorts_by_mastery(self):
        parsed = {
            "overall_mastery": 0.5,
            "weak_points": [
                {"knowledge_point_name": "A", "mastery_level": 0.8, "error_rate": 0.2,
                 "common_mistake_pattern": "", "suggested_focus": ""},
                {"knowledge_point_name": "B", "mastery_level": 0.2, "error_rate": 0.9,
                 "common_mistake_pattern": "", "suggested_focus": ""},
                {"knowledge_point_name": "C", "mastery_level": 0.5, "error_rate": 0.5,
                 "common_mistake_pattern": "", "suggested_focus": ""},
            ],
            "strengths": [],
            "recommendations": [],
        }
        wm = DiagnosisEngine._build_map(
            user_id="u1",
            subject_id="s1",
            subject_name="test",
            parsed=parsed,
            raw="",
            token_usage={},
        )
        # Weakest first
        assert wm.weak_points[0].knowledge_point_name == "B"
        assert wm.weak_points[0].mastery_level == 0.2
        assert wm.weak_points[-1].knowledge_point_name == "A"


# ═══════════════════════════════════════════════════════════════════════════
# Engine initialization
# ═══════════════════════════════════════════════════════════════════════════


class TestDiagnosisEngineInit:
    """Test engine singleton and factory."""

    def test_engine_exists(self):
        assert diagnosis_engine is not None
        assert isinstance(diagnosis_engine, DiagnosisEngine)

    def test_custom_gateway(self):
        from app.services.llm_gateway import LLMGateway
        g = LLMGateway()
        eng = DiagnosisEngine(gateway=g)
        assert eng._gateway is g
