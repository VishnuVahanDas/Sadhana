"""Period presets -> (start, end) dates in IST. Weeks start on Monday; periods include today."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils.translation import gettext_lazy as _

DEFAULT = "last_7"
CUSTOM = "custom"

PRESETS = [
    ("last_7", _("Last 7 days")),
    ("last_10", _("Last 10 days")),
    ("last_15", _("Last 15 days")),
    ("last_30", _("Last 30 days")),
    ("this_week", _("This week")),
    ("last_week", _("Last week")),
    ("this_month", _("This month")),
    ("last_month", _("Last month")),
    (CUSTOM, _("Custom range")),
]
LABELS = dict(PRESETS)


@dataclass(frozen=True)
class Period:
    key: str
    start: date
    end: date

    @property
    def label(self):
        return LABELS[self.key]

    @property
    def days(self):
        return (self.end - self.start).days + 1

    def dates(self):
        return [self.start + timedelta(days=offset) for offset in range(self.days)]

    def query(self):
        """Query-string parameters that reproduce this period."""
        if self.key == CUSTOM:
            return {"period": CUSTOM, "start": self.start.isoformat(), "end": self.end.isoformat()}
        return {"period": self.key}


def resolve(key, today, start=None, end=None):
    """The Period for a preset key. Unknown keys and incomplete custom ranges fall back to the default."""
    if key == CUSTOM and start and end:
        if start > end:
            start, end = end, start
        return Period(CUSTOM, start, end)
    if key.startswith("last_") and key[5:].isdigit() and key in LABELS:
        return Period(key, today - timedelta(days=int(key[5:]) - 1), today)
    monday = today - timedelta(days=today.weekday())
    if key == "this_week":
        return Period(key, monday, today)
    if key == "last_week":
        return Period(key, monday - timedelta(days=7), monday - timedelta(days=1))
    first = today.replace(day=1)
    if key == "this_month":
        return Period(key, first, today)
    if key == "last_month":
        last_of_previous = first - timedelta(days=1)
        return Period(key, last_of_previous.replace(day=1), last_of_previous)
    return resolve(DEFAULT, today)


def from_request(params, today):
    """Read ?period=&start=&end= from a QueryDict."""

    def parse(name):
        try:
            return date.fromisoformat(params.get(name, ""))
        except ValueError:
            return None

    return resolve(params.get("period", DEFAULT), today, parse("start"), parse("end"))


def previous(period):
    """The period just before this one, to compare it with.

    Rolling periods and custom ranges go back by their own length. "This week"
    and "This month" compare like with like: the same days of last week or last
    month (1–10 October against 1–10 September), not the whole of it.
    """
    if period.key in ("this_week", "last_week"):
        return Period(CUSTOM, period.start - timedelta(days=7), period.end - timedelta(days=7))
    if period.key in ("this_month", "last_month"):
        last_of_previous = period.start.replace(day=1) - timedelta(days=1)
        start = last_of_previous.replace(day=1)
        if period.key == "last_month":
            return Period(CUSTOM, start, last_of_previous)
        # Month to date; a 31st is held back to the last day of a shorter month.
        return Period(CUSTOM, start, start.replace(day=min(period.end.day, last_of_previous.day)))
    return Period(CUSTOM, period.start - timedelta(days=period.days), period.start - timedelta(days=1))
