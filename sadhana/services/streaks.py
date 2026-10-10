"""Pure streak logic (SPEC §6). No database access here.

A day qualifies for a field when an entry exists for that date and its value
passes `qualifies` (by default: greater than zero, or True for yes/no fields).
"""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Streaks:
    current: int = 0
    longest: int = 0
    on_time_current: int = 0
    on_time_longest: int = 0


def qualifies(value):
    """Default rule: True, or a number above zero. Missing, empty and 0 do not count."""
    if value is True:
        return True
    if isinstance(value, bool) or value is None:
        return False
    return isinstance(value, (int, float)) and value > 0


def current_streak(dates, today):
    """Consecutive days in `dates` ending today, or ending yesterday if today is not in yet."""
    day = today if today in dates else today - timedelta(days=1)
    count = 0
    while day in dates:
        count += 1
        day -= timedelta(days=1)
    return count


def longest_streak(dates):
    """Longest run of consecutive days in `dates`."""
    longest = run = 0
    previous = None
    for day in sorted(dates):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    return longest


def compute_streaks(records, today, qualifies=qualifies):
    """Streaks for one user and one field.

    `records` is an iterable of (date, value, on_time) — one per entry.
    Pass another `qualifies` for fields with a threshold (e.g. 16 rounds).
    """
    normal, on_time = set(), set()
    for day, value, entered_on_time in records:
        if day <= today and qualifies(value):
            normal.add(day)
            if entered_on_time:
                on_time.add(day)
    return Streaks(
        current=current_streak(normal, today),
        longest=longest_streak(normal),
        on_time_current=current_streak(on_time, today),
        on_time_longest=longest_streak(on_time),
    )
