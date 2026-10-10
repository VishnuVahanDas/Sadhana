"""Festival days: which dates fall in a festival, and the day filter used by analysis and ranks."""

from datetime import timedelta

from django.utils.translation import gettext_lazy as _

from ..models import Festival

ALL, REGULAR, FESTIVAL = "all", "regular", "festival"
DAY_FILTERS = [
    (ALL, _("All days")),
    (REGULAR, _("Regular days only")),
    (FESTIVAL, _("Festival days only")),
]


def festival_dates(start, end, festivals=None):
    """{date: [festival names]} for every date between start and end that falls in any festival.

    Overlapping festivals are fine: the date simply lists each of them.
    """
    if festivals is None:
        festivals = Festival.objects.filter(start_date__lte=end, end_date__gte=start)
    result = {}
    for festival in sorted(festivals, key=lambda item: (item.start_date, item.name)):
        day = max(festival.start_date, start)
        while day <= min(festival.end_date, end):
            result.setdefault(day, []).append(festival.name)
            day += timedelta(days=1)
    return result


def choose(key):
    """A valid day-filter key; anything unknown means all days."""
    return key if key in (REGULAR, FESTIVAL) else ALL


def day_filter(key, dates):
    """A date -> bool function for the chosen filter, or None for all days."""
    if key == REGULAR:
        return lambda day: day not in dates
    if key == FESTIVAL:
        return lambda day: day in dates
    return None
