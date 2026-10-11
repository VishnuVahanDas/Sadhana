"""The "Send to coordinator on WhatsApp" button: phone numbers, the message, the wa.me link and where it shows."""

from datetime import date, time, timedelta
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import User
from accounts.phones import normalise_phone, whatsapp_number
from audit.models import AuditLog
from sadhana.models import EntryValue, SadhanaEntry, SadhanaField, UserFieldSetting
from sadhana.services.whatsapp import build_whatsapp_link, build_whatsapp_message

BUTTON = "Send to coordinator on WhatsApp"
DAY = date(2026, 10, 11)  # a Sunday


@pytest.fixture
def coordinator(make_user):
    return make_user(email="coord@example.com", name="Coordinator", is_coordinator=True, phone="919876543210")


@pytest.fixture
def devotee(make_user, coordinator):
    return make_user(email="bhakta@example.com", name="Gopal Sharma", spiritual_name="Gopāla Dāsa", coordinator=coordinator)


def fill(user, day=DAY, **values):
    """Save an entry for `user` with {field key: typed value}."""
    entry, _created = SadhanaEntry.objects.get_or_create(user=user, date=day)
    for key, value in values.items():
        row = EntryValue(entry=entry, field=SadhanaField.objects.get(key=key))
        row.value = value
        row.save()
    return entry


def enable(user, *keys):
    for key in keys:
        UserFieldSetting.objects.create(user=user, field=SadhanaField.objects.get(key=key), enabled=True)


@pytest.mark.django_db(transaction=True)
def test_migration_turns_the_button_on_for_existing_users_and_keeps_a_database_default():
    executor = MigrationExecutor(connection)
    try:
        executor.migrate([("accounts", "0003_user_ui_mode")])
        Old = executor.loader.project_state([("accounts", "0003_user_ui_mode")]).apps.get_model("accounts", "User")
        Old.objects.create(email="old@example.com", name="Old Devotee", password="!", phone="+91 98765 43210")

        executor = MigrationExecutor(connection)
        executor.migrate([("accounts", "0004_user_show_whatsapp_button")])
        old = User.objects.get(email="old@example.com")
        assert old.show_whatsapp_button is True
        assert old.phone == "+91 98765 43210"  # existing phone numbers are left exactly as they were
        # Rollback safety: the previous release does not know the column, and its inserts must still work.
        Old.objects.create(email="older-code@example.com", name="Added By Old Code", password="!")
        assert User.objects.get(email="older-code@example.com").show_whatsapp_button is True
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        call_command("flush", verbosity=0, interactive=False)


# --- Phone numbers ---------------------------------------------------------


@pytest.mark.parametrize("raw", ["9876543210", "09876543210", "+91 98765 43210", "919876543210", "(+91) 98765-43210"])
def test_phone_is_normalised_to_digits_with_country_code(raw):
    assert normalise_phone(raw) == "919876543210"


@pytest.mark.parametrize("raw", ["", "12345", "98765432101", "929876543210", "98765abcde", "9198765432100", "+1 415 555 2671"])
def test_invalid_phone_is_an_error(raw):
    with pytest.raises(ValidationError):
        normalise_phone(raw)
    assert whatsapp_number(raw) is None


def user_form_data(target, **changes):
    data = {
        "email": target.email, "name": target.name, "spiritual_name": target.spiritual_name, "phone": target.phone,
        "coordinator": target.coordinator_id or "", "is_participating": "on", "ui_mode": target.ui_mode,
    }
    data.update(changes)
    return data


def test_manage_users_normalises_the_phone_on_save(client, superuser, user):
    client.force_login(superuser)
    url = reverse("manage_user_edit", args=[user.pk])
    assert client.post(url, user_form_data(user, phone="+91 98765 43210")).status_code == 302
    user.refresh_from_db()
    assert user.phone == "919876543210"
    log = AuditLog.objects.get(field_key="phone")
    assert (log.old_value, log.new_value) == ("", "919876543210")

    # An empty phone is still allowed; a wrong one is a form error and nothing is saved.
    response = client.post(url, user_form_data(user, phone="12345"))
    assert response.status_code == 200 and response.context["form"].errors["phone"]
    user.refresh_from_db()
    assert user.phone == "919876543210"
    assert client.post(url, user_form_data(user, phone="")).status_code == 302
    user.refresh_from_db()
    assert user.phone == ""


def test_manage_users_shows_and_filters_coordinator_phone_missing(client, superuser, make_user, coordinator, devotee):
    silent = make_user(email="silent@example.com", name="Silent Coordinator", is_coordinator=True, phone="12345")
    stuck = make_user(email="stuck@example.com", name="Stuck Devotee", coordinator=silent)
    client.force_login(superuser)
    response = client.get(reverse("manage_users"))
    flags = {person.name: person.coordinator_phone_missing for person in response.context["users"]}
    # Nobody without a coordinator is flagged, only those whose coordinator cannot be reached.
    assert flags == {
        "Admin": False, "Coordinator": False, "Gopal Sharma": False, "Silent Coordinator": False, "Stuck Devotee": True,
    }
    assert response.content.decode().count('badge bg-saffron-light" title="This devotee cannot') == 1
    filtered = client.get(reverse("manage_users"), {"phone": "missing"})
    assert [person.pk for person in filtered.context["users"]] == [stuck.pk]


# --- The message -----------------------------------------------------------


def test_message_has_only_enabled_and_filled_fields_in_field_order(devotee):
    # Day rest is filled but not enabled for this devotee; seva is enabled but not filled.
    entry = fill(devotee, hearing=45, reading=30, rounds=16, day_rest=20, notes="Good japa today.")
    order = list(SadhanaField.objects.filter(key__in=["hearing", "reading", "rounds"]).values_list("label", flat=True))
    values = {"Hearing": "45 min", "Book Reading": "30 min", "Rounds": "16"}
    assert build_whatsapp_message(entry).split("\n") == [
        "🙏 Hare Krishna Prabhu",
        "Sadhana report — Sunday, 11 Oct 2026",
        "Gopāla Dāsa",
        *[f"- {label}: {values[label]}" for label in order],
        "Notes: Good japa today.",
        "sr.iskcongorakhpur.com",
    ]


def test_custom_fields_appear_when_switched_on_with_time_and_boolean_formatting(devotee):
    enable(devotee, "wake_up_time", "mangala_arati")
    entry = fill(devotee, rounds=16, wake_up_time=time(5, 30), mangala_arati=True)
    message = build_whatsapp_message(entry)
    assert "- Wake-up Time: 05:30" in message
    assert "- Mangala Arati: Yes" in message

    EntryValue.objects.filter(entry=entry, field__key="mangala_arati").update(value_bool=False)
    assert "- Mangala Arati: No" in build_whatsapp_message(entry)


def test_labels_and_units_come_from_the_field(devotee):
    SadhanaField.objects.filter(key="hearing").update(label="Śravaṇam", unit="minutes")
    assert "- Śravaṇam: 45 minutes" in build_whatsapp_message(fill(devotee, hearing=45))


def test_notes_are_cut_at_300_characters_and_left_out_when_empty(devotee):
    long_entry = fill(devotee, rounds=16, notes="a" * 301)
    assert f"Notes: {'a' * 300}…\n" in build_whatsapp_message(long_entry)
    exact = fill(devotee, day=DAY - timedelta(days=1), notes="b" * 300)
    assert f"Notes: {'b' * 300}\n" in build_whatsapp_message(exact)
    empty = fill(devotee, day=DAY - timedelta(days=2), rounds=16)
    assert "Notes" not in build_whatsapp_message(empty)


def test_message_never_mentions_streaks_or_levels(devotee):
    devotee.ui_mode = "advanced"
    devotee.save()
    for days_ago in range(5):
        entry = fill(devotee, day=DAY - timedelta(days=days_ago), hearing=60, reading=60, seva=60, rounds=16)
    message = build_whatsapp_message(entry).lower()
    for word in ("streak", "dhairya", "utsāha", "utsaha", "yātrī", "yatra", "niścaya", "level", "🔥"):
        assert word not in message


# --- The link --------------------------------------------------------------


def test_link_is_url_encoded_and_round_trips(devotee):
    entry = fill(devotee, rounds=16, notes="Śrī Kṛṣṇa & Rādhā #1?\nSecond line + more 🙏")
    link = build_whatsapp_link(entry)
    assert link.startswith("https://wa.me/919876543210?text=")
    encoded = link.split("?text=", 1)[1]
    # Nothing raw is left that could break the link: only unreserved characters and %XX escapes.
    assert set(encoded) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~%")
    assert "%F0%9F%99%8F" in encoded  # 🙏
    assert "%0A" in encoded  # line break
    assert "%C4%81" in encoded  # ā in Gopāla
    assert unquote(encoded) == build_whatsapp_message(entry)
    assert parse_qs(urlsplit(link).query)["text"] == [build_whatsapp_message(entry)]


def test_link_normalises_an_old_unformatted_coordinator_phone(devotee, coordinator):
    coordinator.phone = "+91 98765-43210"
    coordinator.save()
    devotee.refresh_from_db()
    assert build_whatsapp_link(fill(devotee, rounds=16)).startswith("https://wa.me/919876543210?")
    coordinator.refresh_from_db()
    assert coordinator.phone == "+91 98765-43210"  # the stored number is not rewritten


def hide_no_coordinator(devotee, coordinator):
    devotee.coordinator = None


def hide_no_phone(devotee, coordinator):
    coordinator.phone = ""


def hide_bad_phone(devotee, coordinator):
    coordinator.phone = "12345"


def hide_own_coordinator(devotee, coordinator):
    devotee.phone = "9876543210"
    devotee.coordinator = devotee


def hide_setting_off(devotee, coordinator):
    devotee.show_whatsapp_button = False


@pytest.mark.parametrize(
    "hide", [hide_no_coordinator, hide_no_phone, hide_bad_phone, hide_own_coordinator, hide_setting_off]
)
def test_button_is_hidden(client, devotee, coordinator, hide):
    today = timezone.localdate()
    entry = fill(devotee, day=today, rounds=16)
    client.force_login(devotee)
    assert BUTTON in client.get(reverse("home")).content.decode()

    hide(devotee, coordinator)
    coordinator.save()
    devotee.save()
    devotee.refresh_from_db()
    entry.refresh_from_db()
    assert build_whatsapp_link(entry) is None
    for url in (reverse("home"), reverse("dashboard", args=[devotee.pk])):
        response = client.get(url)
        assert response.status_code == 200
        assert "wa.me" not in response.content.decode()


# --- Where it shows --------------------------------------------------------


@pytest.mark.parametrize("mode", ["simple", "advanced"])
def test_button_follows_a_save_and_stays_on_the_day(client, devotee, mode):
    devotee.ui_mode = mode
    devotee.save()
    client.force_login(devotee)
    assert "wa.me" not in client.get(reverse("home")).content.decode()  # nothing saved yet

    response = client.post(reverse("home"), {"rounds": "16", "hearing": "45"}, follow=True)
    page = response.content.decode()
    assert response.context["just_saved"] and page.count("https://wa.me/919876543210?text=") == 1
    # Directly under the success message, above the rest of the page.
    assert page.index("Your sadhana has been saved") < page.index("wa.me") < page.index('class="hero')
    assert 'target="_blank" rel="noopener"' in page

    later = client.get(reverse("home"))
    assert not later.context["just_saved"] and later.content.decode().count("wa.me") == 1
    assert unquote(later.context["whatsapp_url"]).count("- Rounds: 16") == 1


def test_my_report_has_a_button_for_each_past_entry(client, devotee):
    today = timezone.localdate()
    for days_ago, rounds in ((0, 16), (1, 12), (2, 8)):
        fill(devotee, day=today - timedelta(days=days_ago), rounds=rounds)
    client.force_login(devotee)
    response = client.get(reverse("dashboard", args=[devotee.pk]))
    links = [row["whatsapp_url"] for row in response.context["rows"]]
    assert len(links) == 3 and response.content.decode().count("https://wa.me/919876543210?text=") == 3
    assert [("- Rounds: %d" % rounds) in unquote(link) for link, rounds in zip(links, (16, 12, 8))] == [True] * 3
    assert date_format(today - timedelta(days=1), "l, j M Y") in unquote(links[1])


def test_button_is_only_on_the_devotees_own_pages(client, devotee, coordinator, superuser):
    today = timezone.localdate()
    fill(devotee, day=today, rounds=16)
    # Someone else reading the report, and a superuser editing the entry, do not get the devotee's button.
    client.force_login(coordinator)
    assert "wa.me" not in client.get(reverse("dashboard", args=[devotee.pk])).content.decode()
    client.force_login(superuser)
    assert "wa.me" not in client.get(reverse("entry", args=[today]) + f"?user={devotee.pk}").content.decode()


def test_devotee_turns_the_button_off_and_on_and_it_is_audit_logged(client, devotee):
    fill(devotee, day=timezone.localdate(), rounds=16)
    client.force_login(devotee)
    assert devotee.show_whatsapp_button  # on by default
    assert 'action="%s"' % reverse("my_whatsapp") in client.get(reverse("home")).content.decode()

    response = client.post(reverse("my_whatsapp"), {"show": "off", "next": reverse("me")})
    assert response.status_code == 302 and response.url == reverse("me")
    devotee.refresh_from_db()
    assert not devotee.show_whatsapp_button
    log = AuditLog.objects.get(field_key="show_whatsapp_button")
    assert (log.action, log.actor, log.target_user, log.old_value, log.new_value) == (
        "user_update", devotee, devotee, "True", "False",
    )
    assert "wa.me" not in client.get(reverse("home")).content.decode()

    # Same value again, or nonsense: nothing changes and nothing is logged.
    client.post(reverse("my_whatsapp"), {"show": "off"})
    client.post(reverse("my_whatsapp"), {"show": "maybe"})
    assert AuditLog.objects.filter(field_key="show_whatsapp_button").count() == 1

    client.post(reverse("my_whatsapp"), {"show": "on", "next": "https://evil.example/"})
    devotee.refresh_from_db()
    assert devotee.show_whatsapp_button and AuditLog.objects.filter(field_key="show_whatsapp_button").count() == 2
    assert "wa.me" in client.get(reverse("home")).content.decode()
    assert client.get(reverse("my_whatsapp")).status_code == 405
