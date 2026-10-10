from datetime import date, timedelta

from sadhana.services.streaks import Streaks, compute_streaks, current_streak, longest_streak, qualifies

TODAY = date(2026, 10, 10)


def ago(days):
    return TODAY - timedelta(days=days)


def run(*days_ago, value=30, on_time=True):
    return [(ago(n), value, on_time) for n in days_ago]


def test_qualifies():
    assert qualifies(1) and qualifies(45) and qualifies(True)
    assert not qualifies(0) and not qualifies(None) and not qualifies(False) and not qualifies("")


def test_no_entries():
    assert compute_streaks([], TODAY) == Streaks(0, 0, 0, 0)


def test_streak_ending_today():
    assert compute_streaks(run(0, 1, 2), TODAY).current == 3


def test_grace_rule_counts_up_to_yesterday_when_today_is_missing():
    assert compute_streaks(run(1, 2, 3), TODAY).current == 3


def test_grace_rule_also_applies_when_today_is_zero():
    records = run(1, 2) + [(TODAY, 0, True)]
    assert compute_streaks(records, TODAY).current == 2


def test_streak_is_broken_after_two_missed_days():
    result = compute_streaks(run(2, 3, 4), TODAY)
    assert result.current == 0 and result.longest == 3


def test_gap_resets_the_current_streak():
    result = compute_streaks(run(0, 1, 3, 4, 5, 6), TODAY)
    assert result.current == 2 and result.longest == 4


def test_zero_and_empty_values_break_the_streak():
    records = run(0, 1) + [(ago(2), 0, True)] + run(3, 4, 5)
    assert compute_streaks(records, TODAY).current == 2
    records = run(0, 1) + [(ago(2), None, True)] + run(3, 4, 5)
    result = compute_streaks(records, TODAY)
    assert result.current == 2 and result.longest == 3


def test_longest_streak_can_be_in_the_past():
    result = compute_streaks(run(0, 20, 21, 22, 23, 24), TODAY)
    assert result.current == 1 and result.longest == 5


def test_boolean_field():
    records = [(ago(0), True, True), (ago(1), True, True), (ago(2), None, True), (ago(3), True, True)]
    result = compute_streaks(records, TODAY)
    assert result.current == 2 and result.longest == 2


def test_backfilled_days_count_for_normal_but_not_on_time_streaks():
    # Days 0-1 entered on time, days 2-4 filled in late, days 5-6 on time.
    records = run(0, 1) + run(2, 3, 4, on_time=False) + run(5, 6)
    result = compute_streaks(records, TODAY)
    assert result == Streaks(current=7, longest=7, on_time_current=2, on_time_longest=2)


def test_on_time_streak_uses_the_grace_rule_too():
    records = run(1, 2, 3)
    assert compute_streaks(records, TODAY).on_time_current == 3
    late_today = records + [(TODAY, 30, False)]
    result = compute_streaks(late_today, TODAY)
    assert result.current == 4 and result.on_time_current == 3


def test_future_days_are_ignored():
    records = run(0, 1) + [(TODAY + timedelta(days=1), 30, True)]
    result = compute_streaks(records, TODAY)
    assert result.current == 2 and result.longest == 2


def test_custom_threshold_for_fields_like_rounds():
    records = [(ago(0), 16, True), (ago(1), 12, True), (ago(2), 16, True)]
    assert compute_streaks(records, TODAY, qualifies=lambda rounds: (rounds or 0) >= 16).current == 1
    assert compute_streaks(records, TODAY).current == 3


def test_helpers():
    days = {ago(0), ago(1), ago(5)}
    assert current_streak(days, TODAY) == 2
    assert current_streak({ago(2)}, TODAY) == 0
    assert longest_streak(days) == 2
    assert longest_streak(set()) == 0
