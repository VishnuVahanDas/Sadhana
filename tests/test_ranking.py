from types import SimpleNamespace

from sadhana.services import ranking
from sadhana.services.analytics import FieldStats, UserRow
from sadhana.services.streaks import Streaks


def row(name, total=0, average=0.0, filled=0, streaks=None):
    return UserRow(user=SimpleNamespace(display_name=name), stats=FieldStats(total, average, filled), streaks=streaks)


def option(key):
    return next(item for item in ranking.OPTIONS if item.key == key)


def test_competition_ranking_skips_after_ties():
    assert ranking.competition_ranks([90, 90, 60]) == [1, 1, 3]
    assert ranking.competition_ranks([90, 60, 60, 60, 10]) == [1, 2, 2, 2, 5]
    assert ranking.competition_ranks([5, 5, 5]) == [1, 1, 1]
    assert ranking.competition_ranks([3, 2, 1]) == [1, 2, 3]
    assert ranking.competition_ranks([]) == []


def test_rank_rows_orders_best_first_with_ties_by_name():
    rows = [row("Zeta", total=60), row("Madhava", total=90), row("Arjuna", total=90), row("Nobody", total=0)]
    ranked = ranking.rank_rows(rows, option("total"))
    assert [(item["rank"], item["row"].user.display_name, item["value"]) for item in ranked] == [
        (1, "Arjuna", 90), (1, "Madhava", 90), (3, "Zeta", 60), (4, "Nobody", 0),
    ]


def test_rank_by_each_option():
    a = row("A", total=10, average=1.4, filled=7, streaks=Streaks(3, 9, 1, 4))
    b = row("B", total=50, average=7.1, filled=2, streaks=Streaks(5, 6, 2, 2))
    winners = {key: ranking.rank_rows([a, b], option(key))[0]["row"].user.display_name for key in
               ["current", "longest", "on_time_current", "on_time_longest", "total", "daily_average", "days_filled"]}
    assert winners == {
        "current": "B", "longest": "A", "on_time_current": "B", "on_time_longest": "A",
        "total": "B", "daily_average": "B", "days_filled": "A",
    }


def test_streak_options_are_hidden_for_fields_without_streaks(field):
    assert [item.key for item in ranking.options_for(field("rounds"))] == ["total", "daily_average", "days_filled"]
    assert len(ranking.options_for(field("hearing"))) == 7
    assert len(ranking.options_for(field("mangala_arati"))) == 7


def test_choose_falls_back_to_total(field):
    assert ranking.choose(field("rounds"), "current").key == "total"
    assert ranking.choose(field("hearing"), "current").key == "current"
    assert ranking.choose(field("hearing"), "nonsense").key == "total"


def test_period_only_applies_to_non_streak_options():
    assert [item.key for item in ranking.OPTIONS if item.uses_period] == ["total", "daily_average", "days_filled"]
