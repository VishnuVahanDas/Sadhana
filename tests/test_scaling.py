from reports.services import scaling


def test_percentile_interpolates():
    assert scaling.percentile([10, 20, 30, 40, 50], 50) == 30
    assert scaling.percentile([10, 20, 30, 40, 50], 90) == 46
    assert scaling.percentile([7], 90) == 7
    assert scaling.percentile([], 90) == 0
    assert scaling.percentile([50, 10, 30], 0) == 10 and scaling.percentile([50, 10, 30], 100) == 50


def test_cap_lands_exactly_on_a_clean_step():
    # 90th percentile 50 × 1.2 = 60 exactly: stays 60, not pushed to 90 by float noise.
    values = [50] * 20 + [400]
    assert scaling.usual_cap(values) == 60


def test_round_up_to_clean_numbers():
    steps = scaling.MINUTE_STEPS
    assert [scaling.round_up(value, steps) for value in (1, 60, 61, 100, 121, 181, 250)] == [60, 60, 90, 120, 150, 240, 300]
    assert scaling.round_up(19.2, scaling.COUNT_STEPS) == 20
    assert scaling.round_up(16, scaling.COUNT_STEPS) == 16
    # Beyond the list: 1 / 2 / 5 × 10ⁿ.
    assert scaling.round_up(130, scaling.COUNT_STEPS) == 200
    assert scaling.round_up(2100, steps) == 5000


def test_cap_is_90th_percentile_plus_headroom_rounded_up():
    # Nine normal days and one festival day.
    values = [60, 70, 80, 90, 100, 100, 110, 110, 120, 300]
    # 90th percentile = 138; × 1.2 = 165.6; next clean number = 180.
    assert scaling.percentile(values, 90) == 138
    assert scaling.usual_cap(values) == 180
    assert scaling.clipped(values, 180) == [(9, 300)]


def test_cap_ignores_zero_and_empty_days():
    values = [0, None, 30, 30, 30, 0, 30, 30, 30, 30, 240, 0]
    # Only the 8 non-zero days count: their 90th percentile is 93; × 1.2 = 111.6; next clean number = 120.
    assert scaling.usual_cap(values, floor=60) == 120


def test_cap_never_goes_below_the_floor():
    # Tiny values: 90th percentile × 1.2 is about 17 minutes, but the axis never goes below 60.
    small = [5, 5, 5, 5, 5, 5, 5, 5, 5, 100]
    assert scaling.usual_cap(small, floor=60) == 60
    # Rounds: a floor of 16 keeps the axis from zooming in on a devotee who usually chants 4.
    rounds = [4, 4, 4, 4, 4, 4, 4, 4, 4, 64]
    assert scaling.usual_cap(rounds, scaling.COUNT_STEPS, floor=16) == 16
    assert scaling.usual_cap(rounds, scaling.COUNT_STEPS) == 12


def test_fewer_than_seven_non_zero_days_uses_the_full_range():
    assert scaling.usual_cap([30, 30, 30, 30, 30, 300]) is None
    assert scaling.usual_cap([0] * 20 + [30, 30, 30, 30, 30, 300]) is None
    assert scaling.usual_cap([30, 30, 30, 30, 30, 30, 300]) is not None
    assert scaling.usual_cap([]) is None


def test_no_cap_when_nothing_would_be_clipped():
    assert scaling.usual_cap([60, 70, 80, 90, 100, 110, 120]) is None
    assert scaling.clipped([60, 300], None) == []


def test_clipped_days_carry_their_real_values():
    values = [30, 0, 200, None, 180, 181, 500]
    assert scaling.clipped(values, 180) == [(2, 200), (5, 181), (6, 500)]


def test_rolling_average():
    assert scaling.rolling_average([7, 7, 7], lead_in=[7] * 6) == [7.0, 7.0, 7.0]
    assert scaling.rolling_average([70], lead_in=[0] * 6) == [10.0]
    # Without earlier days the window grows from one day.
    assert scaling.rolling_average([10, 20, 30]) == [10.0, 15.0, 20.0]
    # A single 300-minute day lifts the 7-day line only a little.
    line = scaling.rolling_average([60, 60, 300, 60], lead_in=[60] * 6)
    assert line == [60.0, 60.0, round(660 / 7, 1), round(660 / 7, 1)]
    assert scaling.rolling_average([None, 14], lead_in=[0] * 6) == [0.0, 2.0]


def test_median_is_not_moved_by_one_long_day():
    assert scaling.median([60, 60, 60, 60, 300]) == 60
    assert scaling.median([10, 20, 30, 40]) == 25
    assert scaling.median([]) == 0
