from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditLog
from sadhana.models import AppSettings, EntryValue, SadhanaEntry, UserFieldSetting
from sadhana.services import entries


@pytest.fixture
def today(db):
    return timezone.localdate()


def url(day, name="entry"):
    return reverse(name, args=[day])


def values_of(entry):
    return {row.field.key: row.value for row in entry.values.select_related("field")}


def test_home_shows_the_entry_form_with_default_fields(client, user):
    client.force_login(user)
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert list(response.context["form"].fields) == ["hearing", "reading", "seva", "rounds", "notes"]
    html = response.content.decode()
    assert 'inputmode="numeric"' in html
    assert 'data-add="15"' in html


def test_only_effective_fields_are_shown(client, user, field, today):
    UserFieldSetting.objects.create(user=user, field=field("mangala_arati"), enabled=True)
    UserFieldSetting.objects.create(user=user, field=field("seva"), enabled=False)
    client.force_login(user)
    form = client.get(url(today)).context["form"]
    assert "mangala_arati" in form.fields
    assert "seva" not in form.fields


def test_create_entry_and_audit_one_row_per_value(client, user, today):
    client.force_login(user)
    response = client.post(
        url(today), {"hearing": "30", "reading": "", "seva": "0", "rounds": "16", "notes": " Nice class "},
        REMOTE_ADDR="10.0.0.9", follow=True,
    )
    assert "has been saved" in response.content.decode()
    entry = SadhanaEntry.objects.get(user=user, date=today)
    assert entry.created_by == user and entry.updated_by == user
    # Empty numeric = not entered (no value); an explicit 0 is stored.
    assert values_of(entry) == {"hearing": 30, "seva": 0, "rounds": 16, "notes": "Nice class"}

    logs = AuditLog.objects.filter(target_user=user, entry_date=today)
    assert {(log.action, log.field_key, log.old_value, log.new_value) for log in logs} == {
        ("entry_create", "hearing", "", "30"),
        ("entry_create", "seva", "", "0"),
        ("entry_create", "rounds", "", "16"),
        ("entry_create", "notes", "", "Nice class"),
    }
    assert all(log.actor == user and log.ip_address == "10.0.0.9" for log in logs)


def test_saving_again_updates_instead_of_duplicating(client, user, today):
    client.force_login(user)
    client.post(url(today), {"hearing": "30", "rounds": "16"})
    # The form opens pre-filled.
    assert client.get(url(today)).context["form"]["hearing"].initial == 30
    response = client.post(url(today), {"hearing": "45", "rounds": "16", "reading": "20"})
    assert response.status_code == 302
    assert SadhanaEntry.objects.filter(user=user, date=today).count() == 1
    entry = SadhanaEntry.objects.get(user=user, date=today)
    assert values_of(entry) == {"hearing": 45, "rounds": 16, "reading": 20}

    updates = AuditLog.objects.filter(action="entry_update")
    assert {(log.field_key, log.old_value, log.new_value) for log in updates} == {
        ("hearing", "30", "45"),
        ("reading", "", "20"),
    }


def test_saving_without_changes_writes_no_audit_rows(client, user, today):
    client.force_login(user)
    client.post(url(today), {"hearing": "30"})
    before = AuditLog.objects.count()
    client.post(url(today), {"hearing": "30"})
    assert AuditLog.objects.count() == before


def test_clearing_a_value_removes_it_and_is_audited(client, user, today):
    client.force_login(user)
    client.post(url(today), {"hearing": "30", "notes": "x"})
    client.post(url(today), {"hearing": "", "notes": ""})
    entry = SadhanaEntry.objects.get(user=user, date=today)
    assert values_of(entry) == {}
    cleared = AuditLog.objects.filter(action="entry_update")
    assert {(log.field_key, log.old_value, log.new_value) for log in cleared} == {
        ("hearing", "30", ""),
        ("notes", "x", ""),
    }


def test_empty_entry_is_still_recorded(client, user, today):
    client.force_login(user)
    client.post(url(today), {})
    assert SadhanaEntry.objects.filter(user=user, date=today).exists()
    log = AuditLog.objects.get()
    assert (log.action, log.field_key) == ("entry_create", "")


def test_race_on_create_falls_back_to_update(user, field, today, monkeypatch):
    existing = SadhanaEntry.objects.create(user=user, date=today)

    def lose_the_race(**kwargs):
        raise IntegrityError("duplicate key")

    monkeypatch.setattr(SadhanaEntry.objects, "get_or_create", lose_the_race)
    entry, created = entries.save_entry(user, today, {field("hearing"): 25}, actor=user)
    assert (entry.pk, created) == (existing.pk, False)
    assert values_of(entry) == {"hearing": 25}


@pytest.mark.parametrize("data", [{"hearing": "1441"}, {"hearing": "-5"}, {"rounds": "abc"}])
def test_out_of_range_values_are_rejected(client, user, today, data):
    client.force_login(user)
    response = client.post(url(today), data)
    assert response.status_code == 200
    assert response.context["form"].errors
    assert not SadhanaEntry.objects.exists()


def test_time_and_boolean_fields(client, user, field, today):
    for key in ("wake_up_time", "mangala_arati"):
        UserFieldSetting.objects.create(user=user, field=field(key), enabled=True)
    client.force_login(user)
    client.post(url(today), {"wake_up_time": "04:15", "mangala_arati": "on"})
    entry = SadhanaEntry.objects.get(user=user, date=today)
    assert values_of(entry)["mangala_arati"] is True
    assert values_of(entry)["wake_up_time"].strftime("%H:%M") == "04:15"
    assert AuditLog.objects.get(field_key="wake_up_time").new_value == "04:15"
    # Unticking clears it.
    client.post(url(today), {"wake_up_time": "04:15"})
    assert "mangala_arati" not in values_of(entry)


def test_values_of_disabled_fields_are_kept(client, user, field, today):
    client.force_login(user)
    client.post(url(today), {"hearing": "30", "seva": "60"})
    UserFieldSetting.objects.create(user=user, field=field("seva"), enabled=False)
    client.post(url(today), {"hearing": "40"})
    entry = SadhanaEntry.objects.get(user=user, date=today)
    assert values_of(entry) == {"hearing": 40, "seva": 60}


def test_future_date_is_rejected(client, user, today):
    client.force_login(user)
    tomorrow = today + timedelta(days=1)
    response = client.get(url(tomorrow))
    assert "future dates" in response.content.decode()
    assert "<form method=\"post\" action=\"/entry/" not in response.content.decode()
    client.post(url(tomorrow), {"hearing": "30"})
    assert not SadhanaEntry.objects.exists()


def test_invalid_date_is_404(client, user):
    client.force_login(user)
    assert client.get("/entry/2026-02-30/").status_code == 404
    assert client.get("/entry/yesterday/").status_code == 404


def test_past_dates_are_open_by_default(client, user, today):
    client.force_login(user)
    old = today - timedelta(days=200)
    client.post(url(old), {"hearing": "30"})
    client.post(url(old), {"hearing": "35"})
    assert values_of(SadhanaEntry.objects.get(user=user, date=old)) == {"hearing": 35}


def test_edit_lock_makes_old_entries_read_only(client, user, superuser, field, today):
    old = today - timedelta(days=8)
    entry = SadhanaEntry.objects.create(user=user, date=old)
    EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=30)
    AppSettings.objects.update(edit_lock_enabled=True)

    client.force_login(user)
    html = client.get(url(old)).content.decode()
    assert "can no longer be changed" in html
    assert 'name="hearing"' not in html
    client.post(url(old), {"hearing": "99"})
    client.post(url(old, "entry_delete"))
    assert values_of(SadhanaEntry.objects.get(pk=entry.pk)) == {"hearing": 30}
    # Within the window it still works.
    recent = today - timedelta(days=7)
    client.post(url(recent), {"hearing": "10"})
    client.post(url(recent), {"hearing": "20"})
    assert values_of(SadhanaEntry.objects.get(user=user, date=recent)) == {"hearing": 20}

    # Superusers are never locked.
    client.force_login(superuser)
    client.post(f"{url(old)}?user={user.pk}", {"hearing": "99"})
    assert values_of(SadhanaEntry.objects.get(pk=entry.pk)) == {"hearing": 99}


def test_backfill_limit_blocks_new_old_entries(client, user, superuser, today):
    AppSettings.objects.update(backfill_limit_enabled=True, backfill_limit_days=3)
    client.force_login(user)
    client.post(url(today - timedelta(days=4)), {"hearing": "30"})
    assert not SadhanaEntry.objects.exists()
    client.post(url(today - timedelta(days=3)), {"hearing": "30"})
    assert SadhanaEntry.objects.count() == 1

    client.force_login(superuser)
    client.post(url(today - timedelta(days=40)), {"hearing": "30"})
    assert SadhanaEntry.objects.filter(user=superuser).count() == 1


def test_superuser_edits_another_users_entry(client, user, superuser, today):
    client.force_login(user)
    client.post(url(today), {"hearing": "30"})

    client.force_login(superuser)
    page = f"{url(today)}?user={user.pk}"
    assert user.display_name in client.get(page).content.decode()
    response = client.post(page, {"hearing": "50"})
    assert response.url == page

    entry = SadhanaEntry.objects.get(user=user, date=today)
    assert entry.created_by == user and entry.updated_by == superuser
    assert not SadhanaEntry.objects.filter(user=superuser).exists()
    log = AuditLog.objects.get(action="entry_update")
    assert (log.actor, log.target_user, log.old_value, log.new_value) == (superuser, user, "30", "50")


def test_normal_user_cannot_edit_someone_else(client, user, superuser, today):
    client.force_login(user)
    page = f"{url(today)}?user={superuser.pk}"
    assert client.get(page).status_code == 403
    assert client.post(page, {"hearing": "50"}).status_code == 403
    assert client.post(f"{url(today, 'entry_delete')}?user={superuser.pk}").status_code == 403
    assert not SadhanaEntry.objects.exists()


def test_delete_own_entry_is_audited(client, user, today):
    client.force_login(user)
    client.post(url(today), {"hearing": "30", "rounds": "16"})
    assert client.get(url(today, "entry_delete")).status_code == 405
    response = client.post(url(today, "entry_delete"), follow=True)
    assert "has been deleted" in response.content.decode()
    assert not SadhanaEntry.objects.exists()
    deleted = AuditLog.objects.filter(action="entry_delete")
    assert {(log.field_key, log.old_value) for log in deleted} == {("hearing", "30"), ("rounds", "16")}


def test_recent_days_strip_marks_filled_days(client, user, today):
    SadhanaEntry.objects.create(user=user, date=today - timedelta(days=2))
    client.force_login(user)
    recent = client.get(reverse("home")).context["recent"]
    assert len(recent) == 7
    assert [day["filled"] for day in recent] == [False, False, False, False, True, False, False]
