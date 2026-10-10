from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from sadhana.services.dates import default_entry_date
from sadhana.services.entries import restriction

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
TODAY = date(2026, 10, 10)


@pytest.mark.parametrize(
    "now, expected",
    [
        (datetime(2026, 10, 10, 3, 59, tzinfo=IST), date(2026, 10, 9)),
        (datetime(2026, 10, 10, 4, 0, tzinfo=IST), date(2026, 10, 10)),
        (datetime(2026, 10, 10, 0, 0, tzinfo=IST), date(2026, 10, 9)),
        (datetime(2026, 10, 10, 23, 59, tzinfo=IST), date(2026, 10, 10)),
        # 22:29 UTC on the 9th is 03:59 IST on the 10th; 22:30 UTC is 04:00 IST.
        (datetime(2026, 10, 9, 22, 29, tzinfo=UTC), date(2026, 10, 9)),
        (datetime(2026, 10, 9, 22, 30, tzinfo=UTC), date(2026, 10, 10)),
    ],
)
def test_default_entry_date_rolls_over_at_4am_ist(now, expected):
    assert default_entry_date(4, now=now) == expected


def test_rollover_hour_is_configurable():
    now = datetime(2026, 10, 10, 2, 30, tzinfo=IST)
    assert default_entry_date(2, now=now) == date(2026, 10, 10)
    assert default_entry_date(0, now=now) == date(2026, 10, 10)


def check(actor, days_ago, exists, settings):
    return restriction(actor, TODAY - timedelta(days=days_ago), exists=exists, app_settings=settings, today=TODAY)


def test_default_settings_are_fully_open(user, app_settings):
    assert check(user, 0, False, app_settings) is None
    assert check(user, 400, False, app_settings) is None
    assert check(user, 400, True, app_settings) is None


def test_future_dates_are_rejected_for_everyone(user, superuser, app_settings):
    assert check(user, -1, False, app_settings)
    assert check(superuser, -1, False, app_settings)


def test_edit_lock(user, app_settings):
    app_settings.edit_lock_enabled = True
    assert check(user, 7, True, app_settings) is None
    assert check(user, 8, True, app_settings)
    # The lock is about editing: creating an old entry is the backfill limit's job.
    assert check(user, 8, False, app_settings) is None


def test_backfill_limit(user, app_settings):
    app_settings.backfill_limit_enabled = True
    app_settings.backfill_limit_days = 3
    assert check(user, 3, False, app_settings) is None
    assert check(user, 4, False, app_settings)
    assert check(user, 4, True, app_settings) is None


def test_superusers_are_never_restricted(superuser, app_settings):
    app_settings.edit_lock_enabled = True
    app_settings.backfill_limit_enabled = True
    assert check(superuser, 100, True, app_settings) is None
    assert check(superuser, 100, False, app_settings) is None
