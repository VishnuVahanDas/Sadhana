"""Totals, averages, series and heatmaps built from a user's entries."""

from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from django.utils import timezone

from ..models import SadhanaEntry, SadhanaField
from . import streaks
from .dates import is_on_time

HEATMAP_DAYS = 365
HEATMAP_LEVELS = 4


@dataclass(frozen=True)
class Day:
    """One entry: its date, whether it was entered on time, and field_id -> value."""

    date: object
    on_time: bool
    values: dict


@dataclass(frozen=True)
class FieldStats:
    total: int
    daily_average: float
    days_filled: int


def number(value):
    """A value as a number for totals: not entered = 0, yes = 1."""
    if value is None or value is False:
        return 0
    if value is True:
        return 1
    return value


def load_days(user, start=None, end=None):
    """All of a user's entries (optionally within a date range) as {date: Day}."""
    entries = SadhanaEntry.objects.filter(user=user).prefetch_related("values__field")
    if start:
        entries = entries.filter(date__gte=start)
    if end:
        entries = entries.filter(date__lte=end)
    return {
        entry.date: Day(
            date=entry.date,
            on_time=is_on_time(entry.created_at, entry.date),
            values={row.field_id: row.value for row in entry.values.all()},
        )
        for entry in entries
    }


def average_days(period, date_joined, today):
    """Calendar days the daily average is divided by.

    The period start is bounded by the day the user joined, so new users are
    not penalised; days after today do not count either.
    """
    start = max(period.start, timezone.localdate(date_joined))
    end = min(period.end, today)
    return max((end - start).days + 1, 0)


def field_stats(days, field, period, date_joined, today):
    in_period = [day for day in days.values() if period.start <= day.date <= period.end]
    total = sum(number(day.values.get(field.id)) for day in in_period)
    divisor = average_days(period, date_joined, today)
    return FieldStats(
        total=total,
        daily_average=round(total / divisor, 1) if divisor else 0.0,
        days_filled=len(in_period),
    )


def field_streaks(days, field, today):
    records = ((day.date, day.values.get(field.id), day.on_time) for day in days.values())
    return streaks.compute_streaks(records, today)


def series(days, field, period):
    """One number per calendar day of the period (0 when nothing was entered)."""
    return [number(days[date].values.get(field.id)) if date in days else 0 for date in period.dates()]


def heatmap(days, field, today):
    """Last 365 days as week columns (Monday first), each cell with a 0–4 intensity level."""
    start = today - timedelta(days=HEATMAP_DAYS - 1)
    values = {
        date: number(day.values.get(field.id)) for date, day in days.items() if start <= date <= today
    }
    highest = max(values.values(), default=0)
    first_monday = start - timedelta(days=start.weekday())
    weeks, date = [], first_monday
    while date <= today:
        week = []
        for _ in range(7):
            if start <= date <= today:
                value = values.get(date, 0)
                level = ceil(value / highest * HEATMAP_LEVELS) if value and highest else 0
                week.append({"date": date, "value": value, "level": level, "filled": date in values})
            else:
                week.append(None)
            date += timedelta(days=1)
        weeks.append(week)
    # Label a column with its month when the month changes.
    previous = None
    columns = []
    for week in weeks:
        first = next(cell["date"] for cell in week if cell)
        columns.append({"cells": week, "month": first if first.month != previous else None})
        previous = first.month
    return columns


def is_measurable(field):
    return field.is_numeric or field.field_type == SadhanaField.FieldType.BOOLEAN
