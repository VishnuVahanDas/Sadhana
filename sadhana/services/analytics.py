"""Totals, averages, series and heatmaps built from a user's entries."""

from dataclasses import dataclass
from datetime import timedelta
from statistics import median

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
    typical_day: float = 0  # median of the daily values, counting days with nothing entered as 0


@dataclass(frozen=True)
class UserRow:
    """One person's numbers for one field, as used by the group table and the rank table."""

    user: object
    stats: FieldStats
    streaks: object  # Streaks, or None when the field has no streak


@dataclass(frozen=True)
class GroupSummary:
    people: int
    total: int
    average_per_person: float
    average_per_person_per_day: float


def number(value):
    """A value as a number for totals: not entered = 0, yes = 1."""
    if value is None or value is False:
        return 0
    if value is True:
        return 1
    return value


def load_days_for_users(users, start=None, end=None):
    """Entries of several users (optionally within a date range) as {user_id: {date: Day}}."""
    entries = SadhanaEntry.objects.filter(user__in=users).prefetch_related("values__field")
    if start:
        entries = entries.filter(date__gte=start)
    if end:
        entries = entries.filter(date__lte=end)
    result = {user.pk: {} for user in users}
    for entry in entries:
        result[entry.user_id][entry.date] = Day(
            date=entry.date,
            on_time=is_on_time(entry.created_at, entry.date),
            values={row.field_id: row.value for row in entry.values.all()},
        )
    return result


def load_days(user, start=None, end=None):
    """All of one user's entries (optionally within a date range) as {date: Day}."""
    return load_days_for_users([user], start, end)[user.pk]


def counted_dates(period, date_joined, today, first_entry=None, day_filter=None):
    """The calendar days that the daily average and the typical day are worked out over.

    The period start is bounded by the day the user started — the day they
    joined, or their first entry if they backfilled earlier days — so new users
    are not penalised. Days after today do not count. `day_filter` (date -> bool)
    narrows it further, e.g. to regular days only.
    """
    started = timezone.localdate(date_joined)
    if first_entry and first_entry < started:
        started = first_entry
    day, end = max(period.start, started), min(period.end, today)
    dates = []
    while day <= end:
        if day_filter is None or day_filter(day):
            dates.append(day)
        day += timedelta(days=1)
    return dates


def average_days(period, date_joined, today, first_entry=None, day_filter=None):
    """How many calendar days the daily average is divided by."""
    return len(counted_dates(period, date_joined, today, first_entry, day_filter))


def field_stats(days, field, period, date_joined, today, day_filter=None):
    in_period = [
        day for day in days.values()
        if period.start <= day.date <= period.end and (day_filter is None or day_filter(day.date))
    ]
    total = sum(number(day.values.get(field.id)) for day in in_period)
    dates = counted_dates(period, date_joined, today, min(days, default=None), day_filter)
    daily = [number(days[date].values.get(field.id)) if date in days else 0 for date in dates]
    typical = median(daily) if daily else 0
    return FieldStats(
        total=total,
        daily_average=round(total / len(dates), 1) if dates else 0.0,
        days_filled=len(in_period),
        typical_day=round(typical, 1) if typical % 1 else int(typical),
    )


def field_streaks(days, field, today):
    records = ((day.date, day.values.get(field.id), day.on_time) for day in days.values())
    return streaks.compute_streaks(records, today)


def series(days, field, period):
    """One number per calendar day of the period (0 when nothing was entered)."""
    return [number(days[date].values.get(field.id)) if date in days else 0 for date in period.dates()]


def heatmap_values(days, field, today):
    """The last 365 days of one field as {date: number}, for days that have an entry."""
    start = today - timedelta(days=HEATMAP_DAYS - 1)
    return {date: number(day.values.get(field.id)) for date, day in days.items() if start <= date <= today}


def heatmap(days, field, today, top=None):
    """Last 365 days as week columns (Monday first), each cell with a 0–4 intensity level.

    `top` is the value that gets the darkest colour (the "usual range" cap);
    without it the scale runs to the largest value of the year.
    """
    start = today - timedelta(days=HEATMAP_DAYS - 1)
    values = heatmap_values(days, field, today)
    highest = top or max(values.values(), default=0)
    first_monday = start - timedelta(days=start.weekday())
    weeks, date = [], first_monday
    while date <= today:
        week = []
        for _ in range(7):
            if start <= date <= today:
                value = values.get(date, 0)
                level = min(HEATMAP_LEVELS, -(-value * HEATMAP_LEVELS // highest)) if value and highest else 0
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


def user_rows(users, days_by_user, field, period, today, day_filter=None, show_streaks=True):
    """A UserRow per user for one field. `day_filter` narrows the stats; streaks always use all days.

    `show_streaks=False` (a Simple-mode reader) leaves the streaks out, uncomputed.
    """
    return [
        UserRow(
            user=user,
            stats=field_stats(days_by_user[user.pk], field, period, user.date_joined, today, day_filter),
            streaks=field_streaks(days_by_user[user.pk], field, today) if show_streaks and field.has_streak else None,
        )
        for user in users
    ]


def group_summary(rows, period, today, day_filter=None):
    """Total over the people in scope, and the average per person (overall and per day)."""
    people = len(rows)
    total = sum(row.stats.total for row in rows)
    per_person = total / people if people else 0
    days = sum(1 for day in period.dates() if day <= today and (day_filter is None or day_filter(day)))
    return GroupSummary(
        people=people,
        total=total,
        average_per_person=round(per_person, 1),
        average_per_person_per_day=round(per_person / days, 1) if days else 0.0,
    )


def community_series(users, days_by_user, field, period):
    """Per calendar day of the period: the group's total, and the average per person."""
    totals = [0] * period.days
    for user in users:
        for index, value in enumerate(series(days_by_user[user.pk], field, period)):
            totals[index] += value
    people = len(users)
    averages = [round(total / people, 1) if people else 0 for total in totals]
    return totals, averages
