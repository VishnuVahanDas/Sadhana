"""Bhakti Yatra: the vehicle (Niścaya), the Utsāha meter and Dhairya.

- Niścaya — the vehicle comes from the average rounds over the last 7 days,
  counting only the days rounds were entered. It rewards steadiness, not one
  big day, and a missed report does not pull it down.
- Utsāha — the minutes of hearing, reading and seva offered in a day.
- Dhairya — the existing streaks, unchanged (see streaks.py).

The functions in the first half are pure; the loaders at the end read the database.
"""

from dataclasses import dataclass
from datetime import timedelta

from ..models import AppSettings, SadhanaField, UtsahaLevel, VehicleLevel
from . import analytics, dates, periods, streaks

VEHICLE_DAYS = 7
MIN_FILLED_DAYS = 3  # fewer filled days than this: "Starting the journey"
ROUNDS_KEY = "rounds"
UTSAHA_KEYS = ("hearing", "reading", "seva")


@dataclass(frozen=True)
class Vehicle:
    level: object  # VehicleLevel, or None while the devotee is starting the journey
    average: object  # average rounds over the filled days, or None
    filled_days: int

    @property
    def started(self):
        return self.level is not None


@dataclass(frozen=True)
class Utsaha:
    minutes: int
    level: object  # UtsahaLevel, or None when no levels are set up
    slots: int  # lamps on the meter

    @property
    def diyas(self):
        """One True per lit lamp, then False for the rest of the meter."""
        lit = min(self.level.diya_count, self.slots) if self.level else 0
        return [True] * lit + [False] * (self.slots - lit)

    @property
    def is_full_flame(self):
        return bool(self.level and self.level.is_full_flame)


@dataclass(frozen=True)
class Journey:
    """What a Bhakti Yatra card shows for one devotee."""

    vehicle: Vehicle
    utsaha: Utsaha  # the day's
    utsaha_day: object
    utsaha_is_today: bool
    week_utsaha: Utsaha  # average minutes per day over the last 7 days
    dhairya: list  # [{"field", "streaks"}] for the devotee's streak fields
    together: object  # Streaks of the days with hearing, reading and seva all done; None when streaks are hidden


# --- Pure logic -----------------------------------------------------------


def level_for(value, levels, attribute):
    """The highest level whose threshold is not above `value`; None when there is none."""
    best = None
    for level in levels:
        threshold = getattr(level, attribute)
        if threshold <= value and (best is None or threshold > getattr(best, attribute)):
            best = level
    return best


def recent_rounds(days, rounds_id, today):
    """The rounds of each filled day among the last seven. A day counts only when rounds were entered."""
    values = []
    for offset in range(VEHICLE_DAYS):
        day = days.get(today - timedelta(days=offset))
        value = day.values.get(rounds_id) if day else None
        if value is not None:
            values.append(value)
    return values


def vehicle_for(rounds, levels):
    """The vehicle for the rounds of the filled days; "Starting the journey" below three filled days."""
    if len(rounds) < MIN_FILLED_DAYS:
        return Vehicle(None, None, len(rounds))
    average = sum(rounds) / len(rounds)
    return Vehicle(level_for(average, levels, "min_rounds"), round(average, 1), len(rounds))


def utsaha_for(minutes, levels):
    slots = max((level.diya_count for level in levels), default=0)
    return Utsaha(minutes, level_for(minutes, levels, "min_minutes"), slots)


def minutes_offered(day, field_ids):
    """Hearing + reading + seva minutes of one Day (0 when there is no entry)."""
    if day is None:
        return 0
    return sum(analytics.number(day.values.get(field_id)) for field_id in field_ids)


def together_streaks(days, field_ids, today):
    """Streaks of the days on which every one of the fields was done."""
    if not field_ids:
        return streaks.Streaks()
    records = (
        (day.date, all(streaks.qualifies(day.values.get(field_id)) for field_id in field_ids), day.on_time)
        for day in days.values()
    )
    return streaks.compute_streaks(records, today)


def best_day(days, field_ids, start, end):
    """(date, minutes) of the day with the most minutes offered between start and end; None if there is none."""
    offered = [
        (minutes_offered(day, field_ids), date) for date, day in days.items() if start <= date <= end
    ]
    minutes, date = max(offered, default=(0, None))
    return (date, minutes) if minutes else None


# --- Loaders --------------------------------------------------------------


@dataclass(frozen=True)
class Setup:
    """The levels and field ids every Bhakti Yatra calculation needs; load once per request."""

    vehicles: list
    utsaha_levels: list
    rounds_id: object
    minute_ids: list
    today: object  # the real date (IST), which streaks run to
    day: object  # the sadhana day: yesterday until the rollover hour

    @classmethod
    def load(cls):
        ids = dict(SadhanaField.objects.filter(key__in=(ROUNDS_KEY, *UTSAHA_KEYS)).values_list("key", "id"))
        return cls(
            vehicles=list(VehicleLevel.objects.all()),
            utsaha_levels=list(UtsahaLevel.objects.all()),
            rounds_id=ids.get(ROUNDS_KEY),
            minute_ids=[ids[key] for key in UTSAHA_KEYS if key in ids],
            today=dates.today(),
            day=dates.default_entry_date(AppSettings.load().day_rollover_hour),
        )


def my_vehicle(user, today=None, days=None, setup=None):
    setup = setup or Setup.load()
    days = analytics.load_days(user) if days is None else days
    return vehicle_for(recent_rounds(days, setup.rounds_id, today or setup.day), setup.vehicles)


def utsaha(minutes, setup=None):
    setup = setup or Setup.load()
    return utsaha_for(minutes, setup.utsaha_levels)


def week_utsaha(user, days, setup):
    """Average minutes per day over the last 7 days (not before the devotee started), with its meter."""
    week = periods.Period(periods.CUSTOM, setup.day - timedelta(days=VEHICLE_DAYS - 1), setup.day)
    counted = analytics.counted_dates(week, user.date_joined, setup.day, min(days, default=None))
    total = sum(minutes_offered(days.get(date), setup.minute_ids) for date in counted)
    return utsaha_for(round(total / len(counted)) if counted else 0, setup.utsaha_levels)


def journey(user, days, setup, utsaha_day=None, streak_fields=(), show_streaks=True):
    """`show_streaks=False` (a Simple-mode reader) leaves every streak out, uncomputed."""
    utsaha_day = utsaha_day or setup.day
    if not show_streaks:
        streak_fields = ()
    return Journey(
        vehicle=my_vehicle(user, days=days, setup=setup),
        utsaha=utsaha_for(minutes_offered(days.get(utsaha_day), setup.minute_ids), setup.utsaha_levels),
        utsaha_day=utsaha_day,
        utsaha_is_today=utsaha_day == setup.day,
        week_utsaha=week_utsaha(user, days, setup),
        dhairya=[
            {"field": field, "streaks": analytics.field_streaks(days, field, setup.today)} for field in streak_fields
        ],
        together=together_streaks(days, setup.minute_ids, setup.today) if show_streaks else None,
    )


def sanga_offering(period, people, days_by_user, setup=None):
    """Minutes of hearing, reading and seva the devotees offered together in the period."""
    setup = setup or Setup.load()
    return sum(
        minutes_offered(day, setup.minute_ids)
        for user in people
        for date, day in days_by_user[user.pk].items()
        if period.start <= date <= period.end
    )


def road_together(people, days_by_user, setup, show_streaks=True):
    """Devotees grouped by vehicle, names alphabetical within each group; never ordered by score.

    Groups run along the road from "Starting the journey" (level None) upwards, and empty ones are left out.
    `show_streaks=False` (a Simple-mode reader) leaves the flame out, uncomputed.
    """
    groups = {}
    for user in people:
        days = days_by_user[user.pk]
        level = my_vehicle(user, days=days, setup=setup).level
        groups.setdefault(level.pk if level else None, {"level": level, "people": []})["people"].append(
            {
                "user": user,
                "flame": together_streaks(days, setup.minute_ids, setup.today).current if show_streaks else None,
            }
        )
    ordered = sorted(groups.values(), key=lambda group: group["level"].min_rounds if group["level"] else -1)
    for group in ordered:
        group["people"].sort(key=lambda item: item["user"].display_name.lower())
    return ordered
