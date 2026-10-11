"""Chart scaling for "usual range" views. Pure functions: display only, never changes data.

Normal sadhana is roughly 0–120 minutes per field per day, but festival days can
reach several hours. Scaling an axis to the largest value squashes every normal
day, so charts and the heatmap are scaled to the usual range instead and the
exceptional days are drawn clipped, with their real value shown.
"""

from math import ceil, floor, log10

PERCENTILE = 90
HEADROOM = 1.2
MIN_DAYS = 7  # with fewer non-zero days there is no "usual" to speak of
ROLLING_WINDOW = 7

MINUTE_STEPS = [60, 90, 120, 150, 180, 240, 300, 360, 480, 600, 720, 960, 1200, 1440]
COUNT_STEPS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64, 80, 100]
MINUTE_FLOOR = 60
COUNT_FLOOR = 16


def percentile(values, percent):
    """Percentile with linear interpolation between the two nearest values."""
    ordered = sorted(values)
    if not ordered:
        return 0
    position = (len(ordered) - 1) * percent / 100
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    # Rounded so float noise (137.99999999999994) cannot push a cap over a clean step.
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 6)


def round_up(value, steps):
    """The first clean number in `steps` that is not below `value`; beyond the list, 1/2/5 × 10ⁿ."""
    for step in steps:
        if step >= value:
            return step
    magnitude = 10 ** floor(log10(value))
    for factor in (1, 2, 5, 10):
        if factor * magnitude >= value:
            return factor * magnitude


def usual_cap(values, steps=MINUTE_STEPS, floor=None):
    """Axis maximum for the "usual range" view, or None when the full range should be used.

    90th percentile of the non-zero values × 1.2, never below `floor`, rounded up
    to a clean number. None when there are fewer than 7 non-zero days, or when no
    value is above the cap (so there is nothing to clip).
    """
    nonzero = [value for value in values if value and value > 0]
    if len(nonzero) < MIN_DAYS:
        return None
    cap = round_up(max(round(percentile(nonzero, PERCENTILE) * HEADROOM, 6), floor or 0), steps)
    return cap if max(nonzero) > cap else None


def clipped(values, cap):
    """(index, real value) for every value drawn clipped at the cap."""
    if cap is None:
        return []
    return [(index, value) for index, value in enumerate(values) if value and value > cap]


def rolling_average(values, lead_in=(), window=ROLLING_WINDOW):
    """Average of each day and the days before it, `window` days in all.

    `lead_in` holds the days just before `values`, so the line starts with a full window.
    """
    history = list(lead_in)[-(window - 1):] if window > 1 else []
    result = []
    for value in values:
        history.append(value or 0)
        history = history[-window:]
        result.append(round(sum(history) / len(history), 1))
    return result


def median(values):
    """Middle value; the mean of the two middle values for an even count. 0 for no values."""
    ordered = sorted(values)
    if not ordered:
        return 0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2, 1)


SHADE_LEVELS = 4


def daily_top(values, steps=MINUTE_STEPS, floor=None):
    """The value that gets the darkest shade in a column of daily values.

    The "usual range" cap when there is one, so a festival day is darkest without
    washing out every normal day; otherwise simply the largest value.
    """
    cap = usual_cap(values, steps, floor)
    if cap is not None:
        return cap
    return max((value for value in values if value), default=0)


def relative_top(values):
    """The darkest-shade value for a column that compares people (totals, averages).

    With seven or more non-zero values it is the 90th percentile × 1.2 (never
    above the largest value), so one exceptional devotee does not turn everyone
    else pale; with fewer it is the largest value.
    """
    nonzero = [value for value in values if value and value > 0]
    if not nonzero:
        return 0
    if len(nonzero) < MIN_DAYS:
        return max(nonzero)
    return min(max(nonzero), round(percentile(nonzero, PERCENTILE) * HEADROOM, 6))


def shade_level(value, top, levels=SHADE_LEVELS):
    """Shade for a table cell: None = nothing entered (no shade), 0 = an entered zero, then 1..levels.

    Yes/no values: yes is the darkest shade.
    """
    if value is None:
        return None
    if value is True:
        return levels
    if not value or value <= 0:
        return 0
    if not top:
        return levels
    return min(levels, ceil(value / top * levels))


def shade_column(values, top):
    return [shade_level(value, top) for value in values]
