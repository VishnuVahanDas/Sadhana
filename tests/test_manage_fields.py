from datetime import date

from django.urls import reverse

from audit.models import AuditLog
from sadhana.models import AppSettings, EntryValue, SadhanaEntry, SadhanaField, UserFieldSetting
from sadhana.services.fields import effective_fields

NEW_FIELD = {
    "label": "Japa Quality", "key": "japa_quality", "field_type": "count", "unit": "/10",
    "min_value": "0", "max_value": "10", "is_rankable": "on", "is_active": "on", "help_text": "",
}


def keys(user):
    return [field.key for field in effective_fields(user)]


def test_per_user_toggles(client, superuser, user, field):
    client.force_login(superuser)
    page = reverse("manage_user_fields", args=[user.pk])
    rows = client.get(page).context["rows"]
    assert [row["field"].key for row in rows if row["enabled"]] == ["hearing", "reading", "seva", "rounds", "notes"]

    wanted = ["hearing", "reading", "rounds", "notes", "mangala_arati"]  # seva off, mangala arati on
    client.post(page, {"field": [field(key).id for key in wanted]})
    assert keys(user) == wanted
    assert keys(superuser) == ["hearing", "reading", "seva", "rounds", "notes"]
    # Only the two that changed get a setting and an audit row.
    assert UserFieldSetting.objects.filter(user=user).count() == 2
    logs = AuditLog.objects.filter(action="field_toggle_user", target_user=user)
    assert {(log.field_key, log.old_value, log.new_value) for log in logs} == {
        ("seva", "True", "False"),
        ("mangala_arati", "False", "True"),
    }
    # Switching back updates the same setting row.
    client.post(page, {"field": [field(key).id for key in wanted + ["seva"]]})
    assert UserFieldSetting.objects.filter(user=user).count() == 2
    assert "seva" in keys(user)


def test_add_field(client, superuser, user):
    client.force_login(superuser)
    assert client.post(reverse("manage_field_add"), NEW_FIELD).status_code == 302
    created = SadhanaField.objects.get(key="japa_quality")
    assert created.order > SadhanaField.objects.get(key="day_rest").order
    assert created.is_core is False and created.enabled_by_default is False
    assert AuditLog.objects.get().action == "field_create"
    assert "japa_quality" not in keys(user)


def test_text_field_cannot_be_ranked_or_streaked(client, superuser):
    client.force_login(superuser)
    response = client.post(reverse("manage_field_add"), {**NEW_FIELD, "field_type": "text", "has_streak": "on"})
    assert response.status_code == 200
    assert set(response.context["form"].errors) == {"has_streak", "is_rankable"}
    response = client.post(reverse("manage_field_add"), {**NEW_FIELD, "min_value": "20"})
    assert "max_value" in response.context["form"].errors
    assert not SadhanaField.objects.filter(key="japa_quality").exists()


def test_edit_field_keeps_key_and_type(client, superuser, field):
    hearing = field("hearing")
    client.force_login(superuser)
    response = client.post(
        reverse("manage_field_edit", args=[hearing.pk]),
        {
            "label": "Hearing (lectures)", "key": "changed", "field_type": "text", "unit": "min",
            "min_value": "0", "max_value": "600", "has_streak": "on", "is_rankable": "on",
            "is_active": "on", "enabled_by_default": "on", "help_text": "",
        },
    )
    assert response.status_code == 302
    hearing.refresh_from_db()
    assert (hearing.key, hearing.field_type, hearing.label, hearing.max_value) == ("hearing", "minutes", "Hearing (lectures)", 600)
    logs = AuditLog.objects.filter(action="field_update", field_key="hearing")
    assert {(log.old_value, log.new_value) for log in logs} == {
        ("label=Hearing", "label=Hearing (lectures)"),
        ("max_value=1440", "max_value=600"),
    }


def test_deactivated_field_disappears_from_forms(client, superuser, user, field):
    seva = field("seva")
    client.force_login(superuser)
    data = {
        "label": seva.label, "unit": seva.unit, "min_value": "0", "max_value": "1440",
        "has_streak": "on", "is_rankable": "on", "enabled_by_default": "on", "help_text": "",
    }
    client.post(reverse("manage_field_edit", args=[seva.pk]), data)
    assert "seva" not in keys(user)
    assert SadhanaField.objects.filter(key="seva", is_active=False).exists()


def test_reorder_fields(client, superuser):
    client.force_login(superuser)
    reading = SadhanaField.objects.get(key="reading")
    client.post(reverse("manage_field_move", args=[reading.pk]), {"direction": "up"})
    assert [f.key for f in SadhanaField.objects.all()][:3] == ["reading", "hearing", "seva"]
    client.post(reverse("manage_field_move", args=[reading.pk]), {"direction": "up"})  # already first
    client.post(reverse("manage_field_move", args=[reading.pk]), {"direction": "down"})
    assert [f.key for f in SadhanaField.objects.all()][:3] == ["hearing", "reading", "seva"]


def test_apply_to_all_users_replaces_overrides(client, superuser, user, field):
    arati = field("mangala_arati")
    UserFieldSetting.objects.create(user=user, field=arati, enabled=False)
    client.force_login(superuser)
    client.post(reverse("manage_field_apply", args=[arati.pk]), {"enabled": "1"})
    assert "mangala_arati" in keys(user) and "mangala_arati" in keys(superuser)
    assert not UserFieldSetting.objects.filter(field=arati).exists()
    assert AuditLog.objects.filter(action="field_update", field_key="mangala_arati").count() == 1
    client.post(reverse("manage_field_apply", args=[arati.pk]), {"enabled": "0"})
    assert "mangala_arati" not in keys(user)


def test_delete_rules(client, superuser, user, field):
    client.force_login(superuser)
    # Core: never.
    client.post(reverse("manage_field_delete", args=[field("hearing").pk]))
    # Has stored values: deactivate only.
    entry = SadhanaEntry.objects.create(user=user, date=date(2026, 10, 1))
    EntryValue.objects.create(entry=entry, field=field("day_rest"), value_int=20)
    client.post(reverse("manage_field_delete", args=[field("day_rest").pk]))
    # Unused and not core: deleted.
    client.post(reverse("manage_field_delete", args=[field("sleep_time").pk]))
    remaining = set(SadhanaField.objects.values_list("key", flat=True))
    assert {"hearing", "day_rest"} <= remaining and "sleep_time" not in remaining


def test_settings_form(client, superuser, user):
    client.force_login(superuser)
    data = {
        "site_title": "Sadhana Report", "day_rollover_hour": "3", "edit_lock_enabled": "on",
        "edit_window_days": "5", "backfill_limit_days": "7",
    }
    assert client.post(reverse("manage_settings"), data).status_code == 302
    settings = AppSettings.load()
    assert (settings.edit_lock_enabled, settings.edit_window_days, settings.day_rollover_hour) == (True, 5, 3)
    assert settings.backfill_limit_enabled is False
    logs = AuditLog.objects.filter(action="settings_update")
    assert {(log.field_key, log.old_value, log.new_value) for log in logs} == {
        ("day_rollover_hour", "4", "3"),
        ("edit_lock_enabled", "False", "True"),
        ("edit_window_days", "7", "5"),
    }
    response = client.post(reverse("manage_settings"), {**data, "day_rollover_hour": "24"})
    assert response.context["form"].errors["day_rollover_hour"]


def test_site_title_setting_shows_in_header(client, superuser):
    AppSettings.objects.update(site_title="Gorakhpur Sadhana")
    client.force_login(superuser)
    assert "Gorakhpur Sadhana" in client.get(reverse("home")).content.decode()


def test_audit_viewer_filters(client, superuser, user, today=None):
    from audit import services

    services.log("entry_create", user, target_user=user, field_key="hearing", new_value=30)
    services.log("entry_update", superuser, target_user=user, field_key="hearing", old_value=30, new_value=45)
    services.log("settings_update", superuser, field_key="edit_window_days", old_value=7, new_value=5)
    client.force_login(superuser)
    page = reverse("manage_audit")

    assert client.get(page).context["page"].paginator.count == 3
    assert client.get(page, {"action": "settings_update"}).context["page"].paginator.count == 1
    assert client.get(page, {"user": user.pk}).context["page"].paginator.count == 2
    assert client.get(page, {"user": superuser.pk}).context["page"].paginator.count == 2
    assert client.get(page, {"date_from": "2099-01-01"}).context["page"].paginator.count == 0
    assert client.get(page, {"date_to": "2099-01-01"}).context["page"].paginator.count == 3
    html = client.get(page, {"user": user.pk}).content.decode()
    assert "hearing" in html and "edit_window_days" not in html


def test_audit_viewer_paginates(client, superuser):
    from audit import services

    for number in range(55):
        services.log("settings_update", superuser, field_key="site_title", new_value=number)
    client.force_login(superuser)
    first = client.get(reverse("manage_audit"), {"action": "settings_update"})
    assert len(first.context["page"]) == 50
    assert "action=settings_update&amp;page=2" in first.content.decode()
    assert len(client.get(reverse("manage_audit"), {"page": 2}).context["page"]) == 5
