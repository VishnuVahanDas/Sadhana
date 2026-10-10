"""Comparing a period with the one before it. Pure functions."""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

# Daily average leads: months differ in length, so totals alone mislead.
METRICS = [
    ("daily_average", _("Daily average")),
    ("typical_day", _("Typical day")),
    ("total", _("Total")),
    ("days_filled", _("Days filled")),
]


@dataclass(frozen=True)
class Change:
    """A number now and in the previous period. `previous` is None when there is nothing to compare with."""

    current: float
    previous: float | None

    @property
    def difference(self):
        return None if self.previous is None else round(self.current - self.previous, 1)

    @property
    def amount(self):
        """The size of the change, without its sign."""
        return None if self.previous is None else abs(self.difference)

    @property
    def direction(self):
        if self.previous is None:
            return None
        if self.difference > 0:
            return "up"
        return "down" if self.difference < 0 else "same"

    @property
    def percent(self):
        """Change as a whole percentage of the previous value; None when that was zero or missing."""
        if not self.previous:
            return None
        return round(100 * (self.current - self.previous) / self.previous)


def compare_stats(current, previous):
    """One Change per metric for two FieldStats. `previous` may be None (e.g. the devotee had not joined)."""
    return [
        {"key": key, "label": label, "change": Change(getattr(current, key), getattr(previous, key) if previous else None)}
        for key, label in METRICS
    ]


def align(previous_values, length):
    """Previous-period values lined up day by day with the current period: cut or padded with None."""
    values = list(previous_values)[:length]
    return values + [None] * (length - len(values))
