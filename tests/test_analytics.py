from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from accounts.models import User
from sadhana.models import EntryValue, SadhanaEntry
from sadhana.services import analytics, periods

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def today(db):
    return timezone.localdate()


@pytest.fixture
def log(field):
    """log(user, days_ago, hearing=30, late=True) creates an entry with values."""

    def _log(user, days_ago, late=False, **values):
        date = timezone.localdate() - timedelta(days=days_ago)
        entry = SadhanaEntry.objects.create(user=user, date=date)
        entered = date + timedelta(days=5 if late else 0)
        SadhanaEntry.objects.filter(pk=entry.pk).update(
            created_at=datetime(entered.year, entered.month, entered.day, 21, 0, tzinfo=IST)
        )
        for key, value in values.items():
            row = EntryValue(entry=entry, field=field(key))
            row.value = value
            row.save()
        return entry

    return _log


def joined(user, days_ago):
    User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=days_ago))
    user.refresh_from_db()


def test_totals_average_and_days_filled(user, field, log, today):
    joined(user, 365)
    log(user, 0, hearing=30, rounds=16)
    log(user, 1, hearing=60)
    log(user, 3, rounds=16)  # entry without hearing: still a filled day, counts 0
    log(user, 20, hearing=500)  # outside the period
    days = analytics.load_days(user)
    period = periods.resolve("last_7", today)

    hearing = analytics.field_stats(days, field("hearing"), period, user.date_joined, today)
    assert (hearing.total, hearing.days_filled) == (90, 3)
    assert hearing.daily_average == round(90 / 7, 1)
    rounds = analytics.field_stats(days, field("rounds"), period, user.date_joined, today)
    assert (rounds.total, rounds.daily_average) == (32, round(32 / 7, 1))


def test_daily_average_is_bounded_by_date_joined(user, field, log, today):
    joined(user, 2)  # joined the day before yesterday: 3 calendar days so far
    log(user, 0, hearing=30)
    log(user, 1, hearing=60)
    days = analytics.load_days(user)
    period = periods.resolve("last_30", today)
    stats = analytics.field_stats(days, field("hearing"), period, user.date_joined, today)
    assert stats.total == 90
    assert stats.daily_average == 30.0  # 90 / 3, not 90 / 30
    assert analytics.average_days(period, user.date_joined, today) == 3


def test_backfilling_before_joining_moves_the_start_back(user, field, log, today):
    joined(user, 0)  # account created today...
    for days_ago in range(7):  # ...then a week of entries filled in
        log(user, days_ago, hearing=30)
    days = analytics.load_days(user)
    period = periods.resolve("last_7", today)
    stats = analytics.field_stats(days, field("hearing"), period, user.date_joined, today)
    assert (stats.total, stats.daily_average) == (210, 30.0)  # 210 / 7, not 210 / 1
    # Still bounded: over 30 days it divides by the 7 days since the first entry.
    month = analytics.field_stats(days, field("hearing"), periods.resolve("last_30", today), user.date_joined, today)
    assert month.daily_average == 30.0


def test_average_days_edge_cases(user, today):
    joined(user, 365)
    last_week = periods.resolve("last_week", today)
    assert analytics.average_days(last_week, user.date_joined, today) == 7
    future = periods.resolve("custom", today, today - timedelta(days=1), today + timedelta(days=10))
    assert analytics.average_days(future, user.date_joined, today) == 2
    joined(user, 0)
    assert analytics.average_days(last_week, user.date_joined, today) == 0
    days = analytics.load_days(user)
    assert analytics.field_stats(days, None, last_week, user.date_joined, today).daily_average == 0.0


def test_boolean_fields_count_days(user, field, log, today):
    joined(user, 365)
    log(user, 0, mangala_arati=True)
    log(user, 1, mangala_arati=True)
    log(user, 2, hearing=10)
    stats = analytics.field_stats(
        analytics.load_days(user), field("mangala_arati"), periods.resolve("last_7", today), user.date_joined, today
    )
    assert stats.total == 2


def test_streaks_from_entries_distinguish_on_time(user, field, log, today):
    log(user, 0, hearing=30)
    log(user, 1, hearing=30)
    log(user, 2, hearing=30, late=True)
    log(user, 3, hearing=30)
    log(user, 4, hearing=0)
    log(user, 5, hearing=30)
    result = analytics.field_streaks(analytics.load_days(user), field("hearing"), today)
    assert (result.current, result.longest) == (4, 4)
    assert (result.on_time_current, result.on_time_longest) == (2, 2)
    # Reading was never entered.
    assert analytics.field_streaks(analytics.load_days(user), field("reading"), today).longest == 0


def test_series_has_one_number_per_day(user, field, log, today):
    log(user, 0, hearing=30)
    log(user, 2, hearing=45)
    period = periods.resolve("last_7", today)
    assert analytics.series(analytics.load_days(user), field("hearing"), period) == [0, 0, 0, 0, 45, 0, 30]


def test_heatmap_grid(user, field, log, today):
    log(user, 0, hearing=120)
    log(user, 1, hearing=30)
    log(user, 2, hearing=0)
    log(user, 400, hearing=999)  # older than a year: ignored, also for the scale
    columns = analytics.heatmap(analytics.load_days(user), field("hearing"), today)
    cells = [cell for column in columns for cell in column["cells"] if cell]
    assert len(cells) == 365
    assert all(len(column["cells"]) == 7 for column in columns)
    assert cells[0]["date"] == today - timedelta(days=364) and cells[-1]["date"] == today
    # Rows are weekdays, Monday first.
    assert all(cell["date"].weekday() == row for column in columns for row, cell in enumerate(column["cells"]) if cell)
    by_date = {cell["date"]: cell for cell in cells}
    assert by_date[today]["level"] == 4
    assert by_date[today - timedelta(days=1)]["level"] == 1
    assert by_date[today - timedelta(days=2)]["level"] == 0
    assert by_date[today - timedelta(days=3)] == {"date": today - timedelta(days=3), "value": 0, "level": 0, "filled": False}
    assert sum(1 for column in columns if column["month"]) in (12, 13)
