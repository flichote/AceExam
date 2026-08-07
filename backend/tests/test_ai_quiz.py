"""Tests for quiz_generator — JSON parsing, tier routing, output structures."""

import pytest

from app.services.quiz_generator import (
    QuizGenerator,
    GeneratedQuiz,
    quiz_generator,
)


# ═══════════════════════════════════════════════════════════════════════════
# JSON parsing
# ═══════════════════════════════════════════════════════════════════════════


class TestParseQuestions:
    """Test LLM output JSON parsing."""

    def test_parse_valid_json_array(self):
        json_str = '''[
            {"type": "single", "content": "1+1=?", "options": {"A": "1", "B": "2"}, "answer": {"correct": "B"}, "analysis": "基础", "difficulty": 1, "knowledge_point": "加法"}
        ]'''
        result = QuizGenerator._parse_questions(json_str)
        assert len(result) == 1
        assert result[0]["type"] == "single"
        assert result[0]["content"] == "1+1=?"

    def test_parse_json_with_code_fence(self):
        json_str = '```json\n[{"type": "blank", "content": "填空", "analysis": "解", "difficulty": 2, "knowledge_point": "测试"}]\n```'
        result = QuizGenerator._parse_questions(json_str)
        assert len(result) == 1
        assert result[0]["type"] == "blank"

    def test_parse_json_with_text_preamble(self):
        """LLM often adds explanatory text before JSON."""
        text = '好的，以下是题目：\n```json\n[{"type": "single", "content": "问题", "analysis": "解析", "difficulty": 3, "knowledge_point": "KP"}]\n```'
        result = QuizGenerator._parse_questions(text)
        assert len(result) >= 1

    def test_parse_invalid_json_returns_empty(self):
        result = QuizGenerator._parse_questions("这不是 JSON")
        assert result == []

    def test_parse_empty_string(self):
        result = QuizGenerator._parse_questions("")
        assert result == []

    def test_parse_single_object(self):
        """Single object (not array) should be wrapped."""
        json_str = '{"type": "single", "content": "问题", "analysis": "解", "difficulty": 2}'
        result = QuizGenerator._parse_questions(json_str)
        assert len(result) == 1
        assert result[0]["type"] == "single"

    def test_parse_nested_json_in_text(self):
        """JSON embedded deep within markdown text."""
        text = """
分析完毕。现在给出习题：

[
  {"type": "single", "content": "极限的定义", "options": {"A":"对","B":"错"}, "answer": {"correct":"A"}, "analysis": "这是基本定义", "difficulty": 2, "knowledge_point": "极限"},
  {"type": "blank", "content": "导数公式: (sin x)' = ___", "options": null, "answer": {"correct": "cos x"}, "analysis": "基本求导公式", "difficulty": 1, "knowledge_point": "导数"}
]

以上就是本次练习题。
"""
        result = QuizGenerator._parse_questions(text)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════
# GeneratedQuiz dataclass
# ═══════════════════════════════════════════════════════════════════════════


class TestGeneratedQuiz:
    """Test output structure."""

    def test_to_dict(self):
        gq = GeneratedQuiz(
            subject="数学",
            knowledge_points=["极限", "导数"],
            questions=[
                {
                    "type": "single",
                    "content": "1+1=?",
                    "options": {"A": "1", "B": "2"},
                    "answer": {"correct": "B"},
                    "analysis": "基础加法",
                    "difficulty": 1,
                    "knowledge_point": "加法",
                }
            ],
            token_usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
        d = gq.to_dict()
        assert d["subject"] == "数学"
        assert len(d["questions"]) == 1
        assert d["questions"][0]["difficulty"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# QuizGenerator integration
# ═══════════════════════════════════════════════════════════════════════════


class TestQuizGenerator:
    """Test generator configuration and entry point."""

    def test_generator_exists(self):
        assert quiz_generator is not None
        assert isinstance(quiz_generator, QuizGenerator)

    def test_custom_gateway(self):
        from app.services.llm_gateway import LLMGateway
        g = LLMGateway()
        gen = QuizGenerator(gateway=g)
        assert gen._gateway is g
