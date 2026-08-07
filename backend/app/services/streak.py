"""Streak (打卡连胜) computation (M3 §11.3).

Pure function — no DB dependency, takes a sorted list of dates and returns
(current_streak, longest_streak). Design per architecture.md §11.3:

- current_streak: from the most recent checked-in date backward by consecutive days
- If latest date < yesterday → current_streak = 0 (broken)
- longest_streak: max consecutive-day segment over entire history
- Timezone: dates are pre-normalized to Asia/Shanghai by caller; this fn just
  compares date objects by difference of 1 day

Conventions:
- "today" and "yesterday" are passed explicitly as date objects to keep this pure.
"""

from datetime import date, timedelta


def compute_streak(dates: list[date], today: date | None = None) -> tuple[int, int]:
    """Compute (current_streak, longest_streak) from a sorted ascending list of date objects.

    Args:
        dates: Sorted list of dates (ascending) when the user checked in.
        today: Current date for "today / yesterday" boundary; defaults to date.today().

    Returns:
        (current_streak, longest_streak) as non-negative integers.
    """
    if not dates:
        return 0, 0

    if today is None:
        today = date.today()

    yesterday = today - timedelta(days=1)

    # ── Current streak ──
    latest = dates[-1]
    current_streak = 0

    if latest in (today, yesterday):
        # Streak is alive — count backwards from latest
        current_streak = 1
        for d in reversed(dates[:-1]):
            if (latest - d).days == 1:
                current_streak += 1
                latest = d
            else:
                break
    # else: latest < yesterday → streak broken, remain 0

    # ── Longest streak ──
    longest = 0
    run = 0
    prev: date | None = None
    for d in dates:
        if prev is not None and (d - prev).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        prev = d

    return current_streak, longest


def compute_streak_from_sessions(
    session_dates: list[date],
    today: date | None = None,
) -> tuple[int, int]:
    """Compute streak from checked-in session dates (sorted ascending).

    Convenience wrapper over compute_streak. Sorts input defensively.
    """
    return compute_streak(sorted(session_dates), today=today)
