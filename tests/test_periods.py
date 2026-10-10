from datetime import date

import pytest
from django.http import QueryDict

from sadhana.services import periods

SATURDAY = date(2026, 10, 10)


@pytest.mark.parametrize(
    "key, start, end",
    [
        ("last_7", date(2026, 10, 4), SATURDAY),
        ("last_10", date(2026, 10, 1), SATURDAY),
        ("last_15", date(2026, 9, 26), SATURDAY),
        ("last_30", date(2026, 9, 11), SATURDAY),
        ("this_week", date(2026, 10, 5), SATURDAY),  # Monday to today
        ("last_week", date(2026, 9, 28), date(2026, 10, 4)),  # Monday to Sunday
        ("this_month", date(2026, 10, 1), SATURDAY),
        ("last_month", date(2026, 9, 1), date(2026, 9, 30)),
    ],
)
def test_presets(key, start, end):
    period = periods.resolve(key, SATURDAY)
    assert (period.start, period.end) == (start, end)
    assert period.end <= SATURDAY


def test_day_counts_include_today():
    assert periods.resolve("last_7", SATURDAY).days == 7
    assert periods.resolve("last_30", SATURDAY).days == 30
    assert len(periods.resolve("last_10", SATURDAY).dates()) == 10


def test_week_starts_on_monday():
    monday, sunday = date(2026, 10, 5), date(2026, 10, 11)
    assert periods.resolve("this_week", monday).start == monday
    assert periods.resolve("this_week", monday).days == 1
    assert periods.resolve("this_week", sunday).start == monday
    last = periods.resolve("last_week", sunday)
    assert (last.start, last.end) == (date(2026, 9, 28), date(2026, 10, 4))
    assert last.start.weekday() == 0 and last.end.weekday() == 6


def test_month_boundaries():
    january = periods.resolve("last_month", date(2027, 1, 15))
    assert (january.start, january.end) == (date(2026, 12, 1), date(2026, 12, 31))
    leap = periods.resolve("last_month", date(2028, 3, 31))
    assert (leap.start, leap.end) == (date(2028, 2, 1), date(2028, 2, 29))
    first = periods.resolve("this_month", date(2026, 10, 1))
    assert (first.start, first.end, first.days) == (date(2026, 10, 1), date(2026, 10, 1), 1)


def test_custom_range():
    period = periods.resolve("custom", SATURDAY, date(2026, 8, 1), date(2026, 8, 31))
    assert (period.key, period.days) == ("custom", 31)
    swapped = periods.resolve("custom", SATURDAY, date(2026, 8, 31), date(2026, 8, 1))
    assert (swapped.start, swapped.end) == (date(2026, 8, 1), date(2026, 8, 31))
    assert period.query() == {"period": "custom", "start": "2026-08-01", "end": "2026-08-31"}


def test_from_request_falls_back_to_default():
    default = periods.resolve(periods.DEFAULT, SATURDAY)
    assert periods.from_request(QueryDict(""), SATURDAY) == default
    assert periods.from_request(QueryDict("period=nonsense"), SATURDAY) == default
    assert periods.from_request(QueryDict("period=custom&start=bad&end=2026-08-01"), SATURDAY) == default
    assert periods.from_request(QueryDict("period=last_month"), SATURDAY).key == "last_month"
    custom = periods.from_request(QueryDict("period=custom&start=2026-08-01&end=2026-08-05"), SATURDAY)
    assert custom.days == 5
