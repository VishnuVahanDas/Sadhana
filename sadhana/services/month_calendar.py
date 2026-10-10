"""Month calendar on the entry page: which days are filled, missed, festival days or not open."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Cell:
    date: date
    filled: bool
    open: bool  # can be opened: not in the future, and either filled or still allowed to be added
    festivals: tuple  # festival names on this day
    is_today: bool
    selected: bool


def parse(text, fallback, today):
    """First day of the month named by "YYYY-MM"; the fallback date's month when missing or invalid.

    Never later than the current month.
    """
    try:
        year, month = (text or "").split("-")
        first = date(int(year), int(month), 1)
    except ValueError:
        first = fallback.replace(day=1)
    return min(first, today.replace(day=1))


def last_day(first):
    return first.replace(day=calendar.monthrange(first.year, first.month)[1])


def neighbours(first, today):
    """(first day of the previous month, first day of the next month or None when that is in the future)."""
    previous = (first - timedelta(days=1)).replace(day=1)
    following = last_day(first) + timedelta(days=1)
    return previous, following if following <= today else None


def weeks(first, *, filled, festivals, today, selected, is_closed):
    """The month as Monday-first weeks of Cells, with None for the days of neighbouring months.

    `filled` is a set of dates, `festivals` is {date: [names]} and `is_closed(date)` says whether an
    unfilled past day can no longer be added.
    """
    rows = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month):
        row = []
        for day in week:
            if day.month != first.month:
                row.append(None)
                continue
            is_filled = day in filled
            row.append(Cell(
                date=day,
                filled=is_filled,
                open=day <= today and (is_filled or not is_closed(day)),
                festivals=tuple(festivals.get(day, ())),
                is_today=day == today,
                selected=day == selected,
            ))
        rows.append(row)
    return rows


def filled_summary(first, filled, today):
    """(days filled, days so far) for the month, counting only up to today."""
    end = min(last_day(first), today)
    return sum(1 for day in filled if first <= day <= end), max(0, (end - first).days + 1)
