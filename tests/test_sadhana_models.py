from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction

from sadhana.models import AppSettings, EntryValue, SadhanaEntry, SadhanaField, UserFieldSetting
from sadhana.services.fields import effective_fields

IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 10, 5)


def test_seeded_fields_match_spec(db):
    rows = {
        f.key: (f.field_type, f.has_streak, f.is_rankable, f.is_core, f.is_active, f.enabled_by_default)
        for f in SadhanaField.objects.all()
    }
    assert rows == {
        "hearing": ("minutes", True, True, True, True, True),
        "reading": ("minutes", True, True, True, True, True),
        "seva": ("minutes", True, True, True, True, True),
        "rounds": ("count", False, True, True, True, True),
        "notes": ("text", False, False, True, True, True),
        "wake_up_time": ("time", False, False, False, True, False),
        "sleep_time": ("time", False, False, False, True, False),
        "mangala_arati": ("boolean", True, True, False, True, False),
        "day_rest": ("minutes", False, False, False, True, False),
    }
    assert [f.key for f in SadhanaField.objects.all()][:5] == ["hearing", "reading", "seva", "rounds", "notes"]
    hearing = SadhanaField.objects.get(key="hearing")
    assert (hearing.effective_min, hearing.effective_max, hearing.unit) == (0, 1440, "min")


def test_app_settings_singleton_defaults(db):
    settings = AppSettings.load()
    assert settings.pk == 1
    assert settings.edit_lock_enabled is False
    assert settings.backfill_limit_enabled is False
    assert (settings.edit_window_days, settings.backfill_limit_days, settings.day_rollover_hour) == (7, 7, 4)
    assert settings.site_title == "Sadhana Report"
    AppSettings(site_title="Another").save()
    assert AppSettings.objects.count() == 1


def test_second_entry_for_same_user_and_date_is_rejected(user):
    SadhanaEntry.objects.create(user=user, date=DAY)
    with pytest.raises(IntegrityError), transaction.atomic():
        SadhanaEntry.objects.create(user=user, date=DAY)
    assert SadhanaEntry.objects.count() == 1


def test_same_date_for_different_users_is_fine(user, superuser):
    SadhanaEntry.objects.create(user=user, date=DAY)
    SadhanaEntry.objects.create(user=superuser, date=DAY)


def test_one_value_per_field_per_entry(user, field):
    entry = SadhanaEntry.objects.create(user=user, date=DAY)
    EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=30)
    with pytest.raises(IntegrityError), transaction.atomic():
        EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=45)


def test_one_setting_per_user_per_field(user, field):
    UserFieldSetting.objects.create(user=user, field=field("day_rest"), enabled=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        UserFieldSetting.objects.create(user=user, field=field("day_rest"), enabled=False)


@pytest.mark.parametrize(
    "key, value",
    [("hearing", 45), ("rounds", 16), ("wake_up_time", time(4, 15)), ("mangala_arati", True), ("notes", "Nice kirtan")],
)
def test_entry_value_is_typed(user, field, key, value):
    entry = SadhanaEntry.objects.create(user=user, date=DAY)
    row = EntryValue(entry=entry, field=field(key))
    row.value = value
    row.save()
    assert EntryValue.objects.select_related("field").get(pk=row.pk).value == value


@pytest.mark.parametrize(
    "created, on_time",
    [
        (datetime(2026, 10, 5, 21, 0, tzinfo=IST), True),
        (datetime(2026, 10, 6, 23, 59, tzinfo=IST), True),
        (datetime(2026, 10, 7, 0, 1, tzinfo=IST), False),
        (datetime(2026, 10, 12, 9, 0, tzinfo=IST), False),
    ],
)
def test_is_on_time_means_same_or_next_day_in_ist(user, created, on_time):
    entry = SadhanaEntry.objects.create(user=user, date=DAY)
    SadhanaEntry.objects.filter(pk=entry.pk).update(created_at=created)
    entry.refresh_from_db()
    assert entry.is_on_time is on_time


def test_effective_fields_use_defaults(user):
    assert [f.key for f in effective_fields(user)] == ["hearing", "reading", "seva", "rounds", "notes"]


def test_effective_fields_respect_user_overrides(user, superuser, field):
    UserFieldSetting.objects.create(user=user, field=field("mangala_arati"), enabled=True)
    UserFieldSetting.objects.create(user=user, field=field("seva"), enabled=False)
    assert [f.key for f in effective_fields(user)] == ["hearing", "reading", "rounds", "notes", "mangala_arati"]
    # Another user is unaffected.
    assert "seva" in [f.key for f in effective_fields(superuser)]


def test_inactive_field_is_hidden_even_if_enabled_for_user(user, field):
    arati = field("mangala_arati")
    UserFieldSetting.objects.create(user=user, field=arati, enabled=True)
    arati.is_active = False
    arati.save()
    assert "mangala_arati" not in [f.key for f in effective_fields(user)]


def test_deleting_a_field_with_values_is_blocked(user, field):
    from django.db.models import ProtectedError

    entry = SadhanaEntry.objects.create(user=user, date=DAY)
    EntryValue.objects.create(entry=entry, field=field("day_rest"), value_int=20)
    with pytest.raises(ProtectedError):
        field("day_rest").delete()
    assert entry.date + timedelta(days=0) == DAY
