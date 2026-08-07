"""Tests for adaptive question selection — scoring, selection logic, data structures.

Tests the MVP rule-based scorer from architecture.md §10.1:
  score(kp) = 50·status_factor + 35·error_factor + 10·recency_factor + 5·difficulty_factor
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.services.selection import (
    compute_score,
    status_factor,
    error_factor,
    recency_factor,
    difficulty_factor,
)
from app.db.models import UserKnowledgeState


# ═══════════════════════════════════════════════════════════════════════════
# Status factor
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusFactor:
    """Test status_factor mapping per architecture.md §10.1."""

    def test_weak(self):
        assert status_factor("weak") == 1.0

    def test_consolidating(self):
        assert status_factor("consolidating") == 0.6

    def test_untouched(self):
        assert status_factor("untouched") == 0.35

    def test_mastered(self):
        assert status_factor("mastered") == 0.05

    def test_unknown_status(self):
        # Unknown status defaults to untouched weight
        assert status_factor("unknown") == 0.35


# ═══════════════════════════════════════════════════════════════════════════
# Error factor (Laplace smoothing)
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorFactor:
    """Test error_factor with Laplace smoothing: (wrong+1)/(total+2)."""

    def test_no_data(self):
        # 0 correct, 0 wrong → (0+1)/(0+2) = 0.5
        assert error_factor(0, 0) == 0.5

    def test_all_correct(self):
        # 10 correct, 0 wrong → (0+1)/(10+2) ≈ 0.083
        f = error_factor(10, 0)
        assert pytest.approx(f, 0.01) == 1 / 12

    def test_all_wrong(self):
        # 0 correct, 10 wrong → (10+1)/(10+2) ≈ 0.917
        f = error_factor(0, 10)
        assert pytest.approx(f, 0.01) == 11 / 12

    def test_half_wrong(self):
        # 5 correct, 5 wrong → (5+1)/(10+2) = 0.5
        f = error_factor(5, 5)
        assert f == 0.5

    def test_high_error(self):
        # Weak scenario: 2 correct, 8 wrong
        f = error_factor(2, 8)
        assert f > 0.7


# ═══════════════════════════════════════════════════════════════════════════
# Recency factor
# ═══════════════════════════════════════════════════════════════════════════


class TestRecencyFactor:
    """Test recency_factor: min(days, 7)/7."""

    def test_never_practiced(self):
        kp = UserKnowledgeState(
            user_id=uuid.uuid4(),
            knowledge_point_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            status="untouched",
            last_practiced_at=None,
        )
        assert recency_factor(kp) == 1.0

    def test_practiced_today(self):
        kp = UserKnowledgeState(
            user_id=uuid.uuid4(),
            knowledge_point_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            status="consolidating",
            last_practiced_at=datetime.now(timezone.utc),
        )
        assert recency_factor(kp) == 0.0

    def test_practiced_3_days_ago(self):
        from datetime import timedelta
        kp = UserKnowledgeState(
            user_id=uuid.uuid4(),
            knowledge_point_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            status="weak",
            last_practiced_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        val = recency_factor(kp)
        # 3 days out of max 7
        assert pytest.approx(val, 0.1) == 3 / 7

    def test_practiced_long_ago(self):
        """More than 7 days ago should cap at 1.0."""
        from datetime import timedelta
        kp = UserKnowledgeState(
            user_id=uuid.uuid4(),
            knowledge_point_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            status="untouched",
            last_practiced_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        assert recency_factor(kp) == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Difficulty factor
# ═══════════════════════════════════════════════════════════════════════════


class TestDifficultyFactor:
    """Test difficulty_factor: max(0, 1 - |q_diff - target|/4)."""

    def test_exact_match(self):
        assert difficulty_factor(3, 3) == 1.0

    def test_one_off(self):
        # |4-3|/4 = 0.25 → 0.75
        assert difficulty_factor(4, 3) == 0.75
        assert difficulty_factor(2, 3) == 0.75

    def test_max_distance(self):
        # |5-1|/4 = 1.0 → 0
        assert difficulty_factor(5, 1) == 0.0
        assert difficulty_factor(1, 5) == 0.0

    def test_two_off(self):
        # |5-3|/4 = 0.5 → 0.5
        assert difficulty_factor(5, 3) == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Composite score (architecture.md §10.1 formula)
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeScore:
    """Test the composite scoring formula with default weights (50, 35, 10, 5)."""

    def _make_kp(self, status="untouched", correct=0, wrong=0, days_ago=None):
        from datetime import timedelta
        last = None
        if days_ago is not None:
            last = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return UserKnowledgeState(
            user_id=uuid.uuid4(),
            knowledge_point_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            status=status,
            correct_count=correct,
            wrong_count=wrong,
            last_practiced_at=last,
        )

    def test_weak_priority(self):
        """Weak status + high error → highest score."""
        kp = self._make_kp(status="weak", correct=2, wrong=8)
        score = compute_score(kp)
        # Should be significant (weak=1.0, error≈0.75, recency=1.0)
        assert score > 70

    def test_mastered_low_priority(self):
        """Mastered status → very low score."""
        kp = self._make_kp(status="mastered", correct=20, wrong=1, days_ago=0)
        score = compute_score(kp)
        assert score < 20

    def test_untouched_mid_priority(self):
        """Untouched → medium priority."""
        kp = self._make_kp(status="untouched")
        score = compute_score(kp)
        # untouched=0.35*50 + 0.5*35 + 1.0*10 + 1.0*5 ≈ 17.5+17.5+10+5=50
        assert 40 < score < 60

    def test_custom_weights(self):
        """Custom weights should change the score."""
        kp = self._make_kp(status="weak", correct=0, wrong=5)
        default_score = compute_score(kp)
        custom_score = compute_score(kp, weights={"status": 100, "error": 0, "recency": 0, "difficulty": 0})
        # With only status weight, weak=1.0*100=100
        assert custom_score == 100.0
        assert custom_score != default_score

    def test_score_range(self):
        """Score should always be in reasonable range (0-100)."""
        for status in ["untouched", "consolidating", "mastered", "weak"]:
            kp = self._make_kp(status=status, correct=5, wrong=5, days_ago=3)
            score = compute_score(kp)
            assert 0 <= score <= 100, f"score {score} out of range for {status}"


# ═══════════════════════════════════════════════════════════════════════════
# Module exports
# ═══════════════════════════════════════════════════════════════════════════


class TestSelectionModuleExports:
    """Verify selection module exports the expected functions."""

    def test_functions_exist(self):
        from app.services import selection
        assert callable(selection.compute_score)
        assert callable(selection.status_factor)
        assert callable(selection.error_factor)
        assert callable(selection.recency_factor)
        assert callable(selection.difficulty_factor)
        assert callable(selection.select_practice_questions)
        assert callable(selection.select_self_test_questions)
