"""M3 打卡连胜纯函数测试 — app.services.streak.compute_streak。

验收点（docs/design/flows.md / architecture.md §11.3）：
- 连续判定：最近打卡日为今天或昨天 → current 从最近日向前数连续天数
- 中断判定：最近打卡日早于昨天 → current=0（已断）；longest 保留历史最长连续段
- 空输入 → (0,0)；输入乱序 → 防御性排序

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_streak.py -v --tb=short -p no:warnings
"""
from datetime import date, timedelta

import pytest

from app.services.streak import compute_streak, compute_streak_from_sessions

pytestmark = pytest.mark.anyio

TODAY = date(2026, 8, 8)


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


# ═══════════════════════════════════════════════════════════════════════
# 连续判定
# ═══════════════════════════════════════════════════════════════════════

class TestStreakAlive:
    def test_empty_returns_zero(self):
        assert compute_streak([], today=TODAY) == (0, 0)

    def test_today_only(self):
        assert compute_streak([TODAY], today=TODAY) == (1, 1)

    def test_yesterday_only_still_alive(self):
        """昨天打卡 → 连胜仍存活（current=1）。"""
        assert compute_streak([_ago(1)], today=TODAY) == (1, 1)

    def test_three_consecutive_ending_today(self):
        dates = [_ago(2), _ago(1), TODAY]
        assert compute_streak(dates, today=TODAY) == (3, 3)

    def test_consecutive_ending_yesterday(self):
        """连续 4 天截至昨天 → current=4。"""
        dates = [_ago(4), _ago(3), _ago(2), _ago(1)]
        assert compute_streak(dates, today=TODAY) == (4, 4)


# ═══════════════════════════════════════════════════════════════════════
# 中断判定
# ═══════════════════════════════════════════════════════════════════════

class TestStreakBroken:
    def test_broken_current_zero(self):
        """最近打卡是 2 天前（<昨天）→ 连胜中断 current=0，longest 保留 2。"""
        dates = [_ago(3), _ago(2)]
        assert compute_streak(dates, today=TODAY) == (0, 2)

    def test_gap_in_middle_current_short(self):
        """中间断档：今天打卡但昨天没打 → current=1，longest=2（前面连续段）。"""
        dates = [_ago(5), _ago(4), TODAY]
        assert compute_streak(dates, today=TODAY) == (1, 2)

    def test_two_runs_longest_kept(self):
        """两段连续（2 天 + 3 天）→ current=3、longest=3。"""
        dates = [_ago(6), _ago(5), _ago(2), _ago(1), TODAY]
        assert compute_streak(dates, today=TODAY) == (3, 3)

    def test_unsorted_input_defensive(self):
        """乱序输入仍正确（compute_streak_from_sessions 防御性排序）。"""
        dates = [TODAY, _ago(2), _ago(1)]
        assert compute_streak_from_sessions(dates, today=TODAY) == (3, 3)

    def test_single_old_date_broken(self):
        """仅一条很久以前的打卡 → current=0、longest=1。"""
        assert compute_streak([_ago(10)], today=TODAY) == (0, 1)
