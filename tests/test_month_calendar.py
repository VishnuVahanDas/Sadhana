from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from sadhana.models import AppSettings, Festival, SadhanaEntry
from sadhana.services import month_calendar

TODAY = date(2026, 10, 10)


def test_parse_month():
    assert month_calendar.parse("2026-08", TODAY, TODAY) == date(2026, 8, 1)
    assert month_calendar.parse(None, date(2026, 9, 20), TODAY) == date(2026, 9, 1)
    assert month_calendar.parse("nonsense", date(2026, 9, 20), TODAY) == date(2026, 9, 1)
    assert month_calendar.parse("2026-13", TODAY, TODAY) == date(2026, 10, 1)
    assert month_calendar.parse("2027-01", TODAY, TODAY) == date(2026, 10, 1)  # never a future month


def test_neighbours():
    assert month_calendar.neighbours(date(2026, 10, 1), TODAY) == (date(2026, 9, 1), None)
    assert month_calendar.neighbours(date(2026, 1, 1), TODAY) == (date(2025, 12, 1), date(2026, 2, 1))


def test_weeks_mark_filled_festival_future_and_closed_days():
    weeks = month_calendar.weeks(
        date(2026, 10, 1),
        filled={date(2026, 10, 2), date(2026, 10, 9)},
        festivals={date(2026, 10, 9): ["Kartik"]},
        today=TODAY,
        selected=date(2026, 10, 9),
        is_closed=lambda day: day < date(2026, 10, 5),
    )
    assert all(len(week) == 7 for week in weeks)
    assert weeks[0][:3] == [None, None, None]  # 1 October 2026 is a Thursday; weeks start on Monday
    cells = {cell.date.day: cell for week in weeks for cell in week if cell}
    assert len(cells) == 31
    assert cells[2].filled and cells[2].open  # filled days stay open even when backfill is closed
    assert not cells[3].filled and not cells[3].open  # too old to add
    assert not cells[6].filled and cells[6].open
    assert cells[9].festivals == ("Kartik",) and cells[9].selected and not cells[9].is_today
    assert cells[10].is_today and cells[10].open
    assert not cells[11].open  # future


def test_filled_summary_counts_only_up_to_today():
    filled = {date(2026, 10, 2), date(2026, 10, 9), date(2026, 9, 30)}
    assert month_calendar.filled_summary(date(2026, 10, 1), filled, TODAY) == (2, 10)
    assert month_calendar.filled_summary(date(2026, 9, 1), filled, TODAY) == (1, 30)


def test_entry_page_shows_the_month_calendar(client, user):
    today = timezone.localdate()
    first = today.replace(day=1)
    SadhanaEntry.objects.create(user=user, date=first)
    Festival.objects.create(name="Test Utsava", start_date=first, end_date=first)
    client.force_login(user)

    response = client.get(reverse("entry", args=[today]))
    html = response.content.decode()
    calendar = response.context["calendar"]
    assert calendar["month"] == first and calendar["next_url"] is None
    assert calendar["days_filled"] == 1 and calendar["days_so_far"] == today.day
    assert "Test Utsava" in html and "cal-filled" in html and 'id="entry-date"' in html

    previous = (first - timedelta(days=1)).replace(day=1)
    response = client.get(reverse("entry", args=[today]), {"month": f"{previous:%Y-%m}"})
    assert response.context["calendar"]["month"] == previous
    assert response.context["calendar"]["next_url"].endswith(f"month={first:%Y-%m}#calendar")


def test_calendar_closes_days_past_the_backfill_limit(client, user, superuser):
    AppSettings.objects.update_or_create(pk=1, defaults={"backfill_limit_enabled": True, "backfill_limit_days": 3})
    today = timezone.localdate()
    old = today - timedelta(days=40)
    params = {"month": f"{old:%Y-%m}"}

    def cell(response):
        return next(
            item["cell"] for week in response.context["calendar"]["weeks"] for item in week
            if item and item["cell"].date == old
        )

    client.force_login(user)
    assert not cell(client.get(reverse("entry", args=[today]), params)).open
    client.force_login(superuser)  # superusers are never restricted
    assert cell(client.get(reverse("entry", args=[today]), params)).open
