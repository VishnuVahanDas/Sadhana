from datetime import timedelta
from io import BytesIO

import pytest
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from accounts.models import User
from reports.services import scaling
from sadhana.models import EntryValue, SadhanaEntry, UserFieldSetting


def test_shade_level():
    assert scaling.shade_level(None, 120) is None  # nothing entered: no shade
    assert scaling.shade_level(0, 120) == 0  # an entered zero: palest
    assert [scaling.shade_level(value, 120) for value in (1, 30, 31, 60, 61, 90, 91, 120)] == [1, 1, 2, 2, 3, 3, 4, 4]
    assert scaling.shade_level(300, 120) == 4  # above the top: darkest, not off the scale
    assert scaling.shade_level(True, 0) == 4 and scaling.shade_level(False, 0) == 0
    assert scaling.shade_level(5, 0) == 4
    assert scaling.shade_column([None, 0, 60, 120], 120) == [None, 0, 2, 4]


def test_daily_top_uses_the_usual_range_when_there_is_one():
    normal = [60, 70, 80, 90, 100, 100, 110, 110, 120]
    assert scaling.daily_top(normal + [300]) == 180  # the festival day does not set the scale
    assert scaling.daily_top(normal) == 120  # nothing unusual: the largest value
    assert scaling.daily_top([30, 45]) == 45
    assert scaling.daily_top([0, None]) == 0


def test_relative_top_is_not_set_by_one_exceptional_devotee():
    # Twenty devotees between 200 and 770 minutes, and one with 3000.
    totals = list(range(200, 800, 30)) + [3000]
    top = scaling.relative_top(totals)
    assert 770 < top < 3000
    levels = scaling.shade_column(totals, top)
    assert levels[-1] == 4 and len(set(levels[:-1])) >= 3  # the others still spread over several shades
    # Scaled to the largest value instead, all twenty would share the palest shade.
    assert set(scaling.shade_column(totals[:-1], 3000)) <= {1, 2}
    assert scaling.relative_top([400, 3000]) == 3000  # too few to judge: the largest
    assert scaling.relative_top([0, 0]) == 0
    # Never above the largest value, so someone always gets the darkest shade.
    assert scaling.relative_top([100] * 9) == 100


@pytest.fixture
def today(db):
    return timezone.localdate()


@pytest.fixture
def people(make_user, field, today):
    """Arjuna: 60 min hearing for 9 days plus a 300-minute day and one zero. Bhima: 30 minutes once."""
    arjuna = make_user(email="a@example.com", name="Arjuna")
    bhima = make_user(email="b@example.com", name="Bhima")
    User.objects.update(date_joined=timezone.now() - timedelta(days=365))
    for days_ago in range(11):
        entry = SadhanaEntry.objects.create(user=arjuna, date=today - timedelta(days=days_ago))
        minutes = {3: 300, 5: 0}.get(days_ago, 60)
        EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=minutes)
        if days_ago == 0:
            EntryValue.objects.create(entry=entry, field=field("notes"), value_text="Nice class")
    entry = SadhanaEntry.objects.create(user=bhima, date=today)
    EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=30)
    return arjuna, bhima


def test_entries_table_is_shaded_per_column(client, people, today):
    arjuna, _ = people
    client.force_login(arjuna)
    response = client.get(reverse("dashboard", args=[arjuna.pk]), {"period": "last_15"})
    rows = {row["date"]: row for row in response.context["rows"]}
    # Columns: hearing, reading, seva, rounds, notes.
    assert rows[today]["shaded"][0] == ("60", 2)  # the usual range tops out at 120 here, so 60 is mid-scale
    assert rows[today - timedelta(days=3)]["shaded"][0] == ("300", 4)  # festival-sized day: darkest
    assert rows[today - timedelta(days=5)]["shaded"][0] == ("0", 0)  # an entered zero
    assert rows[today]["shaded"][1] == (None, None)  # reading not entered: no shade
    assert rows[today]["shaded"][4] == ("Nice class", None)  # text is never shaded
    html = response.content.decode()
    # The numbers are still there; colour only sits behind them.
    assert "shade-4" in html and "300" in html
    assert "shade-None" not in html


def test_yes_no_column_is_shaded(client, people, field, today):
    arjuna, _ = people
    UserFieldSetting.objects.create(user=arjuna, field=field("mangala_arati"), enabled=True)
    entry = SadhanaEntry.objects.get(user=arjuna, date=today)
    EntryValue.objects.create(entry=entry, field=field("mangala_arati"), value_bool=True)
    client.force_login(arjuna)
    row = client.get(reverse("dashboard", args=[arjuna.pk])).context["rows"][0]
    assert row["shaded"][-1] == ("Yes", 4)


def test_analysis_table_is_shaded_against_the_group(client, people):
    arjuna, _ = people
    client.force_login(arjuna)
    response = client.get(reverse("analysis"), {"period": "last_15"})
    table = {row.user.display_name: (total_level, average_level) for row, _change, total_level, average_level in response.context["table"]}
    assert table == {"Arjuna": (4, 4), "Bhima": (1, 1)}
    html = response.content.decode()
    assert "shade-4" in html and "shade-1" in html
    # Shading replaces the small bars in the table.
    assert 'class="meter' not in html.split("By devotee")[1].split("</table>")[0]


def test_sheet_totals_and_daily_are_shaded(client, people, today):
    arjuna, _ = people
    client.force_login(arjuna)
    totals = client.get(reverse("sheet"), {"period": "last_15"})
    rows = {row["user"].display_name: row for row in totals.context["rows"]}
    assert rows["Arjuna"]["shaded"][0] == (840, 4) and rows["Bhima"]["shaded"][0] == (30, 1)
    assert rows["Bhima"]["shaded"][1] == (0, 0)
    assert "shade-4" in totals.content.decode()

    daily = client.get(reverse("sheet"), {"period": "last_15", "show": "daily"})
    rows = {row["user"].display_name: row for row in daily.context["rows"]}
    # Newest day first; hearing is the first field.
    assert rows["Arjuna"]["shaded_days"][0][0] == (60, 3)
    assert rows["Arjuna"]["shaded_days"][3][0] == (300, 4)
    assert rows["Arjuna"]["shaded_days"][5][0] == (0, 0)
    assert rows["Bhima"]["shaded_days"][0][0] == (30, 2)  # same scale as Arjuna's column
    assert rows["Bhima"]["shaded_days"][1][0] == (None, None)
    html = daily.content.decode()
    assert "shade-3" in html and "shade-None" not in html


def test_excel_files_carry_a_colour_scale_and_real_values(client, people, today):
    arjuna, _ = people
    client.force_login(arjuna)

    def book(name, *args, **params):
        return load_workbook(BytesIO(client.get(reverse(name, args=args), params).content))

    def shaded_ranges(sheet):
        return sorted(str(item.sqref) for item in sheet.conditional_formatting)

    entries = book("dashboard_export", arjuna.pk, period="last_15").active
    # Hearing, Book Reading, Seva and Rounds columns (B–E); not the date, notes or on-time columns.
    ranges = shaded_ranges(entries)
    assert len(ranges) == 4 and all(item[0] in "BCDE" for item in ranges)
    assert 300 in [cell.value for row in entries.iter_rows() for cell in row]

    analysis = book("analysis_export", period="last_15").active
    assert [item[0] for item in shaded_ranges(analysis)] == ["C", "D"]

    totals = book("sheet_export", period="last_15").active
    ranges = shaded_ranges(totals)
    assert ranges and all(item[0] >= "C" for item in ranges)
    # The group total row is not part of the scale.
    last_row = totals.max_row
    assert all(not item.endswith(str(last_row)) for item in ranges)

    daily = book("sheet_export", period="last_7", show="daily").active
    # One scale per field, covering that field's column on every day.
    assert all(len(str(item.sqref).split()) == 7 for item in daily.conditional_formatting)
