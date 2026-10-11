from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from sadhana.models import AppSettings, EntryValue, SadhanaEntry, UtsahaLevel, VehicleLevel
from sadhana.services import analytics, periods, yatra
from sadhana.services.analytics import Day

TODAY = date(2026, 10, 11)
ROUNDS, HEARING, READING, SEVA = 1, 2, 3, 4
MINUTES = [HEARING, READING, SEVA]

VEHICLES = [
    SimpleNamespace(min_rounds=rounds, name=name)
    for rounds, name in [
        (0, "Padayātrī"), (4, "Bail-gāḍī"), (8, "Naukā"), (12, "Pālkī"),
        (16, "Ratha"), (32, "Haṁsa"), (48, "Puṣpaka Vimāna"), (64, "Vaikuṇṭha Vimāna"),
    ]
]
UTSAHA = [
    SimpleNamespace(min_minutes=minutes, label=label, diya_count=diyas, is_full_flame=full)
    for minutes, label, diyas, full in [
        (0, "No lamp yet", 0, False), (1, "One diya", 1, False), (30, "Two diyas", 2, False),
        (60, "Three diyas", 3, False), (120, "Full flame", 4, True),
    ]
]


def days_of(*rows):
    """{date: Day} from (days ago, {field id: value}) pairs."""
    return {
        TODAY - timedelta(days=ago): Day(date=TODAY - timedelta(days=ago), on_time=True, values=values)
        for ago, values in rows
    }


# --- Niścaya: the vehicle ---------------------------------------------------


def test_vehicle_averages_the_filled_days_only():
    # Three filled days of 16; the four missed days do not pull the average down.
    days = days_of((0, {ROUNDS: 16}), (2, {ROUNDS: 16}), (5, {ROUNDS: 16}))
    vehicle = yatra.vehicle_for(yatra.recent_rounds(days, ROUNDS, TODAY), VEHICLES)
    assert (vehicle.level.name, vehicle.average, vehicle.filled_days) == ("Ratha", 16.0, 3)


def test_an_entry_without_rounds_is_not_a_filled_day():
    days = days_of((0, {ROUNDS: 16}), (1, {ROUNDS: 16}), (2, {HEARING: 30}), (3, {ROUNDS: None}))
    assert yatra.recent_rounds(days, ROUNDS, TODAY) == [16, 16]
    # An entered zero does count.
    assert yatra.recent_rounds(days_of((0, {ROUNDS: 0})), ROUNDS, TODAY) == [0]


def test_only_the_last_seven_days_count():
    days = days_of((6, {ROUNDS: 4}), (7, {ROUNDS: 64}), (30, {ROUNDS: 64}))
    assert yatra.recent_rounds(days, ROUNDS, TODAY) == [4]


def test_fewer_than_three_filled_days_is_starting_the_journey():
    vehicle = yatra.vehicle_for([64, 64], VEHICLES)
    assert not vehicle.started and vehicle.level is None and vehicle.filled_days == 2
    assert yatra.vehicle_for([64, 64, 64], VEHICLES).started


@pytest.mark.parametrize(
    "rounds, name",
    [
        ([0, 0, 0], "Padayātrī"), ([3, 3, 3], "Padayātrī"), ([4, 4, 4], "Bail-gāḍī"), ([4, 4, 3], "Padayātrī"),
        ([7, 7, 7], "Bail-gāḍī"), ([8, 8, 8], "Naukā"), ([11, 11, 11], "Naukā"), ([12, 12, 12], "Pālkī"),
        ([15, 15, 15], "Pālkī"), ([16, 16, 15], "Pālkī"), ([16, 16, 16], "Ratha"),
        ([31, 31, 31], "Ratha"), ([32, 32, 32], "Haṁsa"), ([47, 47, 47], "Haṁsa"), ([48, 48, 48], "Puṣpaka Vimāna"),
        ([63, 63, 63], "Puṣpaka Vimāna"), ([64, 64, 64], "Vaikuṇṭha Vimāna"), ([108, 108, 108], "Vaikuṇṭha Vimāna"),
    ],
)
def test_vehicle_thresholds(rounds, name):
    assert yatra.vehicle_for(rounds, VEHICLES).level.name == name


# --- Utsāha -----------------------------------------------------------------


@pytest.mark.parametrize(
    "minutes, label, lit",
    [
        (0, "No lamp yet", 0), (1, "One diya", 1), (29, "One diya", 1), (30, "Two diyas", 2), (59, "Two diyas", 2),
        (60, "Three diyas", 3), (119, "Three diyas", 3), (120, "Full flame", 4), (300, "Full flame", 4),
    ],
)
def test_utsaha_meter(minutes, label, lit):
    utsaha = yatra.utsaha_for(minutes, UTSAHA)
    assert utsaha.level.label == label
    assert utsaha.diyas == [True] * lit + [False] * (4 - lit)
    assert utsaha.is_full_flame == (minutes >= 120)


def test_minutes_offered_adds_hearing_reading_and_seva():
    day = Day(date=TODAY, on_time=True, values={HEARING: 30, READING: 20, SEVA: 40, ROUNDS: 16})
    assert yatra.minutes_offered(day, MINUTES) == 90
    assert yatra.minutes_offered(None, MINUTES) == 0
    assert yatra.minutes_offered(Day(date=TODAY, on_time=True, values={HEARING: None}), MINUTES) == 0


def test_together_streak_needs_all_three():
    full = {HEARING: 30, READING: 10, SEVA: 20}
    days = days_of((0, full), (1, full), (2, {HEARING: 30, READING: 10}), (3, full))
    assert yatra.together_streaks(days, MINUTES, TODAY).current == 2
    assert yatra.together_streaks(days, MINUTES, TODAY).longest == 2


def test_best_day():
    days = days_of((0, {HEARING: 30}), (3, {HEARING: 60, SEVA: 240}), (20, {SEVA: 600}))
    assert yatra.best_day(days, MINUTES, TODAY.replace(day=1), TODAY) == (TODAY - timedelta(days=3), 300)
    assert yatra.best_day({}, MINUTES, TODAY.replace(day=1), TODAY) is None


# --- With the database ------------------------------------------------------


@pytest.fixture
def today(db):
    return timezone.localdate()


@pytest.fixture
def log(field, today):
    def _log(person, days_ago, **values):
        entry = SadhanaEntry.objects.create(user=person, date=today - timedelta(days=days_ago))
        for key, value in values.items():
            EntryValue.objects.create(entry=entry, field=field(key), value_int=value)

    return _log


@pytest.fixture
def sanga(make_user, log):
    """Zara and Arjuna in a ratha, Bhima on foot, a newcomer, and an inactive devotee in the vimāna."""
    people = {
        "zara": make_user(email="z@example.com", name="Zara", ui_mode="advanced"),
        "arjuna": make_user(email="a@example.com", name="Arjuna"),
        "bhima": make_user(email="b@example.com", name="Bhima"),
        "new": make_user(email="n@example.com", name="Nava", ui_mode="advanced"),
        "gone": make_user(email="g@example.com", name="Gone", is_participating=False),
    }
    User.objects.update(date_joined=timezone.now() - timedelta(days=365))
    for days_ago in range(3):
        log(people["zara"], days_ago, rounds=16, hearing=30, reading=30, seva=30)
        log(people["arjuna"], days_ago, rounds=16, hearing=60)
        log(people["bhima"], days_ago, rounds=2, seva=10)
        log(people["gone"], days_ago, rounds=64, seva=600)
    log(people["new"], 0, rounds=16, hearing=15)
    return people


def test_levels_are_seeded(db):
    assert list(VehicleLevel.objects.values_list("min_rounds", flat=True)) == [0, 4, 8, 12, 16, 32, 48, 64]
    assert list(UtsahaLevel.objects.values_list("min_minutes", flat=True)) == [0, 1, 30, 60, 120]
    assert UtsahaLevel.objects.get(is_full_flame=True).min_minutes == 120
    assert AppSettings.load().rank_table_enabled is False


def test_my_vehicle_and_sanga_offering(sanga, today):
    assert yatra.my_vehicle(sanga["zara"], today).level.name == "Ratha"
    assert yatra.my_vehicle(sanga["bhima"], today).level.name == "Padayātrī"
    assert not yatra.my_vehicle(sanga["new"], today).started
    assert yatra.utsaha(90).level.label == "Three diyas"
    people = [person for person in sanga.values() if person.is_participating]
    days = analytics.load_days_for_users(people)
    one_day = periods.Period(periods.CUSTOM, today, today)
    # 90 + 60 + 10 + 15; the inactive devotee's 600 minutes are not part of it.
    assert yatra.sanga_offering(one_day, people, days) == 175


def test_sanga_yatra_page(client, sanga):
    client.force_login(sanga["zara"])
    response = client.get(reverse("yatra"))
    assert response.status_code == 200
    groups = [
        (group["level"].name if group["level"] else None, [item["user"].display_name for item in group["people"]])
        for group in response.context["groups"]
    ]
    # Grouped by vehicle, alphabetical inside each group, and no inactive devotee.
    assert groups == [(None, ["Nava"]), ("Padayātrī", ["Bhima"]), ("Ratha", ["Arjuna", "Zara"])]
    html = response.content.decode()
    assert "Gone" not in html
    for text in ["utsāhān niścayād dhairyāt", "Firm confidence, steady commitment", "My Journey",
                 "On the road together", "Sanga offering", "Three diyas", "90 min offered"]:
        assert text in html
    assert "km/h" not in html
    assert response.context["journey"].together.current == 3
    assert response.context["offerings"][0] == {"label": "Today", "hours": 2, "minutes": 55}
    assert response.context["best_day"][1] == 90


def test_inactive_devotee_still_sees_their_own_journey(client, sanga):
    client.force_login(sanga["gone"])
    response = client.get(reverse("yatra"))
    assert response.context["journey"].vehicle.level.name == "Vaikuṇṭha Vimāna"
    assert "Gone" not in [item["user"].display_name for group in response.context["groups"] for item in group["people"]]


def test_ranks_redirect_to_sanga_yatra_unless_switched_on(client, sanga, superuser):
    client.force_login(sanga["zara"])
    for name in ["ranks", "ranks_export"]:
        response = client.get(reverse(name))
        assert response.status_code == 302 and response["Location"] == reverse("yatra")
    home = client.get(reverse("home")).content.decode()
    assert "Sanga Yatra" in home and reverse("ranks") not in home

    client.force_login(superuser)
    current = AppSettings.load()
    data = {
        "site_title": current.site_title, "theme": current.theme, "day_rollover_hour": current.day_rollover_hour,
        "edit_window_days": 7, "backfill_limit_days": 7, "rank_table_enabled": "on",
    }
    assert client.post(reverse("manage_settings"), data).status_code == 302
    assert AuditLog.objects.filter(action="settings_update", field_key="rank_table_enabled").count() == 1
    assert client.get(reverse("ranks")).status_code == 200
    assert reverse("ranks") in client.get(reverse("yatra")).content.decode()


def test_cards_on_today_and_my_report(client, sanga, today):
    client.force_login(sanga["new"])
    # Nothing saved for yesterday: no card. Today is saved: vehicle and Utsāha are shown.
    assert 'aria-label="Bhakti Yatra"' not in client.get(reverse("entry", args=[today - timedelta(days=1)])).content.decode()
    saved = client.get(reverse("entry", args=[today])).content.decode()
    assert "Starting the journey" in saved and "15 min offered" in saved and "Dhairya" in saved
    report = client.get(reverse("dashboard", args=[sanga["zara"].pk]))
    assert report.context["journey"].vehicle.level.name == "Ratha"
    html = report.content.decode()
    assert "img/yatra/ratha" in html and "Current streak" not in html


def test_manage_yatra_levels(client, superuser, user):
    car = VehicleLevel.objects.get(min_rounds=16)
    url = reverse("manage_yatra_edit", args=["vehicle", car.pk])
    client.force_login(user)
    assert client.get(reverse("manage_yatra")).status_code == 403
    assert client.post(url, {}).status_code == 403

    client.force_login(superuser)
    assert client.get(reverse("manage_yatra")).status_code == 200
    assert client.get(reverse("manage_yatra_edit", args=["nonsense", car.pk])).status_code == 404
    data = {"name": "Chariot", "min_rounds": 20, "icon": "ratha", "description": "Steady"}
    assert client.post(url, {**data, "icon": "rocket"}).status_code == 200  # not one of the drawings
    assert client.post(url, {**data, "min_rounds": 32}).status_code == 200  # another level starts there
    assert client.post(url, data).status_code == 302
    car.refresh_from_db()
    assert (car.name, car.min_rounds) == ("Chariot", 20)
    logged = set(AuditLog.objects.filter(action="yatra_level_update").values_list("field_key", "old_value", "new_value"))
    assert (f"vehicle:{car.pk}", "min_rounds=16", "min_rounds=20") in logged and len(logged) == 3

    # The first level stays at 0, so every devotee always has a level.
    first = UtsahaLevel.objects.get(min_minutes=0)
    client.post(reverse("manage_yatra_edit", args=["utsaha", first.pk]), {"label": "Not yet", "min_minutes": 5, "diya_count": 0})
    first.refresh_from_db()
    assert (first.label, first.min_minutes) == ("Not yet", 0)


def test_vehicles_are_the_spiritual_ladder(db):
    from django.contrib.staticfiles import finders

    levels = list(VehicleLevel.objects.all())
    assert [(level.min_rounds, level.name, level.icon) for level in levels] == [
        (0, "Padayātrī", "padayatri"), (4, "Bail-gāḍī", "bail_gadi"), (8, "Naukā", "nauka"), (12, "Pālkī", "palki"),
        (16, "Ratha", "ratha"), (32, "Haṁsa", "hamsa"), (48, "Puṣpaka Vimāna", "pushpaka"),
        (64, "Vaikuṇṭha Vimāna", "vaikuntha"),
    ]
    # Every level has its short meaning and a drawing that exists; the first drawings stay for a rollback.
    assert all(level.description for level in levels)
    for key in [key for key, _label in VehicleLevel.ICONS] + sorted(VehicleLevel.LEGACY_ICONS):
        assert finders.find(f"img/yatra/{key}.svg"), key
    assert VehicleLevel(icon="car").icon_path == "img/yatra/car.svg"
    assert VehicleLevel(icon="rocket").icon_path == "img/yatra/padayatri.svg"


def test_sanga_yatra_shows_each_vehicles_meaning(client, sanga):
    client.force_login(sanga["zara"])
    html = client.get(reverse("yatra")).content.decode()
    assert "the 16-round standard" in html and "every step counts" in html
    assert "img/yatra/padayatri" in html  # "Starting the journey" uses the pilgrim


def test_ladder_migration_can_be_reversed(db):
    from importlib import import_module

    from django.apps import apps

    migration = import_module("sadhana.migrations.0010_vehicle_spiritual_ladder")
    thresholds = list(VehicleLevel.objects.values_list("min_rounds", flat=True))
    migration.backwards(apps, None)
    assert list(VehicleLevel.objects.values_list("name", "icon", "description"))[:2] == [
        ("Padayatra", "walking", "Walking — every step counts"), ("Cycle", "cycle", ""),
    ]
    migration.forwards(apps, None)
    assert VehicleLevel.objects.get(min_rounds=16).name == "Ratha"
    # Thresholds and the number of rows never change.
    assert list(VehicleLevel.objects.values_list("min_rounds", flat=True)) == thresholds
