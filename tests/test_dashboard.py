import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from sadhana.models import EntryValue, SadhanaEntry, UserFieldSetting


@pytest.fixture
def today(db):
    return timezone.localdate()


@pytest.fixture
def filled(user, field, today):
    """Three days of entries for `user`: today, yesterday and 3 days ago."""
    for days_ago, hearing, rounds, notes in [(0, 30, 16, "Nice class"), (1, 60, 16, ""), (3, 45, 8, "")]:
        entry = SadhanaEntry.objects.create(user=user, date=today - timedelta(days=days_ago))
        EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=hearing)
        EntryValue.objects.create(entry=entry, field=field("rounds"), value_int=rounds)
        if notes:
            EntryValue.objects.create(entry=entry, field=field("notes"), value_text=notes)
    return user


def page(client, person, **params):
    return client.get(reverse("dashboard", args=[person.pk]), params)


def test_me_redirects_to_own_dashboard(client, user):
    client.force_login(user)
    assert client.get(reverse("me")).url == reverse("dashboard", args=[user.pk])


def test_dashboard_requires_login(client, user):
    assert page(client, user).status_code == 302


def test_everyone_can_view_everyone_including_notes(client, filled, make_user):
    client.force_login(make_user(email="other@example.com", name="Other"))
    response = page(client, filled)
    assert response.status_code == 200
    html = response.content.decode()
    assert "Nice class" in html
    assert filled.email not in html
    # But only the owner or a superuser gets Edit links.
    assert response.context["can_edit"] is False
    assert "/entry/" not in html


def test_summary_cards(client, filled, today):
    client.force_login(filled)
    response = page(client, filled)
    cards = {card["field"].key: card for card in response.context["cards"]}
    assert list(cards) == ["hearing", "reading", "seva", "rounds"]  # rankable fields only: no notes
    assert (cards["hearing"]["stats"].total, cards["hearing"]["stats"].days_filled) == (135, 3)
    assert cards["hearing"]["streaks"].current == 2 and cards["hearing"]["streaks"].longest == 2
    assert cards["hearing"]["streaks"].on_time_current == 2
    assert cards["rounds"]["stats"].total == 40
    assert cards["rounds"]["streaks"] is None  # no streak for Rounds
    html = response.content.decode()
    for text in ["Current streak", "Longest", "On-time current", "On-time longest", "Daily average", "Days filled"]:
        assert text in html


def test_period_selection(client, filled):
    client.force_login(filled)
    assert page(client, filled).context["period"].key == "last_7"
    response = page(client, filled, period="last_month")
    assert response.context["period"].key == "last_month"
    assert response.context["rows"] == [] or all(
        row["date"] <= response.context["period"].end for row in response.context["rows"]
    )
    custom = page(client, filled, period="custom", start="2026-01-01", end="2026-01-31")
    assert custom.context["period"].days == 31
    assert "No entries in this period." in custom.content.decode()


def test_charts_never_mix_units(client, filled):
    client.force_login(filled)
    response = page(client, filled)
    charts = response.context["charts"]
    assert [[series["label"] for series in chart["datasets"]] for chart in charts] == [
        ["Hearing", "Book Reading", "Seva"],
        ["Rounds"],
    ]
    assert [chart["unit"] for chart in charts] == ["min", "rounds"]
    assert charts[0]["datasets"][0]["data"][-4:] == [45, 0, 60, 30]
    assert len(charts[0]["labels"]) == 7
    # The data reaches the page as JSON for Chart.js.
    html = response.content.decode()
    embedded = html.split('<script id="chart-data" type="application/json">')[1].split("</script>")[0]
    assert json.loads(embedded)[1]["datasets"][0]["data"][-1] == 16
    assert "chart.umd.min.js" in html


def test_heatmap_field_selector(client, filled, field):
    client.force_login(filled)
    response = page(client, filled)
    assert response.context["heat_field"].key == "hearing"
    assert response.content.decode().count("data-heat") == 365
    assert 'class="heat heat-4"' in response.content.decode()
    assert page(client, filled, heat="rounds").context["heat_field"].key == "rounds"
    assert page(client, filled, heat="notes").context["heat_field"].key == "hearing"


def test_entries_table_and_edit_links(client, filled, superuser, today):
    client.force_login(filled)
    response = page(client, filled)
    rows = response.context["rows"]
    assert [row["date"] for row in rows] == [today, today - timedelta(days=1), today - timedelta(days=3)]
    assert rows[0]["cells"] == ["30", None, None, "16", "Nice class"]
    # The entry for three days ago was created just now, so it counts as late.
    assert [row["on_time"] for row in rows] == [True, True, False]
    assert reverse("entry", args=[today]) in response.content.decode()

    client.force_login(superuser)
    html = page(client, filled).content.decode()
    assert f"{reverse('entry', args=[today])}?user={filled.pk}" in html


def test_dashboard_uses_that_users_fields(client, filled, field):
    UserFieldSetting.objects.create(user=filled, field=field("mangala_arati"), enabled=True)
    UserFieldSetting.objects.create(user=filled, field=field("wake_up_time"), enabled=True)
    entry = SadhanaEntry.objects.get(user=filled, date=timezone.localdate())
    EntryValue.objects.create(entry=entry, field=field("mangala_arati"), value_bool=True)
    EntryValue.objects.create(entry=entry, field=field("wake_up_time"), value_time="04:15")
    client.force_login(filled)
    response = page(client, filled)
    cards = {card["field"].key: card for card in response.context["cards"]}
    assert cards["mangala_arati"]["stats"].total == 1 and cards["mangala_arati"]["streaks"].current == 1
    assert "wake_up_time" not in cards
    assert response.context["rows"][0]["cells"][-2:] == ["04:15", "Yes"]


def test_inactive_users_dashboard_is_still_viewable(client, user, make_user):
    inactive = make_user(email="gone@example.com", name="Gone", is_participating=False)
    client.force_login(user)
    response = page(client, inactive)
    assert response.status_code == 200 and "Inactive" in response.content.decode()


def test_unknown_user_is_404(client, user):
    client.force_login(user)
    assert client.get(reverse("dashboard", args=[99999])).status_code == 404


def test_home_shows_streak_badges_after_saving(client, user, today):
    client.force_login(user)
    badges = client.get(reverse("home")).context["streak_badges"]
    assert [badge["field"].key for badge in badges] == ["hearing", "reading", "seva"]
    assert all(badge["streaks"].current == 0 for badge in badges)
    response = client.post(reverse("entry", args=[today]), {"hearing": "30"}, follow=True)
    current = {badge["field"].key: badge["streaks"].current for badge in response.context["streak_badges"]}
    assert current == {"hearing": 1, "reading": 0, "seva": 0}


def test_devotees_directory(client, user, make_user):
    coordinator = make_user(email="coord@example.com", name="Coord", spiritual_name="Madhava Das", is_coordinator=True)
    member = make_user(email="member@example.com", name="Member One", coordinator=coordinator)
    inactive = make_user(email="gone@example.com", name="Gone Away", is_participating=False)
    client.force_login(user)
    url = reverse("devotees")

    response = client.get(url)
    assert set(response.context["people"]) == {user, coordinator, member, inactive}
    html = response.content.decode()
    assert "Madhava Das" in html and "member@example.com" not in html
    assert reverse("dashboard", args=[member.pk]) in html

    assert list(client.get(url, {"q": "madhava"}).context["people"]) == [coordinator]
    assert set(client.get(url, {"coordinator": coordinator.pk}).context["people"]) == {coordinator, member}
    assert list(client.get(url, {"status": "inactive"}).context["people"]) == [inactive]
    assert inactive not in client.get(url, {"status": "active"}).context["people"]
