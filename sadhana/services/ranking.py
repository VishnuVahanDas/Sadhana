"""Rank table logic (SPEC §8): what a metric can be ranked by, and competition ranking."""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

DEFAULT = "total"


@dataclass(frozen=True)
class RankBy:
    key: str
    label: str
    is_streak: bool  # streak options are live / all-time: the period does not apply

    @property
    def uses_period(self):
        return not self.is_streak


OPTIONS = [
    RankBy("current", _("Current streak"), True),
    RankBy("longest", _("Longest streak"), True),
    RankBy("on_time_current", _("On-time current streak"), True),
    RankBy("on_time_longest", _("On-time longest streak"), True),
    RankBy("total", _("Total"), False),
    RankBy("daily_average", _("Daily average"), False),
    RankBy("days_filled", _("Days filled"), False),
]


def options_for(field):
    """Streak options only exist for fields that have streaks (so not for Rounds)."""
    return [option for option in OPTIONS if field.has_streak or not option.is_streak]


def choose(field, key):
    """The requested option if this field supports it, else the default (Total)."""
    available = {option.key: option for option in options_for(field)}
    return available.get(key) or available[DEFAULT]


def value_of(row, option):
    """The number a UserRow is ranked by."""
    source = row.streaks if option.is_streak else row.stats
    return getattr(source, option.key)


def competition_ranks(values):
    """Ranks for values already sorted best-first; ties share a rank and the next one skips (1, 1, 3)."""
    ranks = []
    for position, value in enumerate(values, 1):
        if ranks and value == values[position - 2]:
            ranks.append(ranks[-1])
        else:
            ranks.append(position)
    return ranks


def rank_rows(rows, option):
    """Rows sorted best-first as [{"rank", "row", "value"}]; ties are ordered by name."""
    ordered = sorted(rows, key=lambda row: (-value_of(row, option), row.user.display_name.lower()))
    values = [value_of(row, option) for row in ordered]
    return [
        {"rank": rank, "row": row, "value": value}
        for rank, row, value in zip(competition_ranks(values), ordered, values)
    ]
