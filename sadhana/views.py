from datetime import date as date_cls
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dates import WEEKDAYS_ABBR
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from audit.services import get_client_ip

from .forms import EntryForm
from .models import AppSettings, SadhanaEntry
from . import themes
from .services import analytics, dates, entries, festivals, month_calendar, yatra
from .services.fields import effective_fields, has_personal_streak

RECENT_DAYS = 7


def _entry_owner(request):
    """The user whose entry is being edited: ?user=<id> for superusers, else the logged-in user."""
    user_id = request.GET.get("user")
    if not user_id or user_id == str(request.user.pk):
        return request.user
    if not request.user.is_superuser:
        raise PermissionDenied
    if not user_id.isdigit():
        raise PermissionDenied
    return get_object_or_404(get_user_model(), pk=user_id)


def _entry_url(date, owner, actor, name="entry"):
    url = reverse(name, args=[date])
    return url if owner == actor else f"{url}?user={owner.pk}"


def home(request):
    app_settings = AppSettings.load()
    return _entry_page(request, dates.default_entry_date(app_settings.day_rollover_hour), app_settings)


def entry(request, date):
    return _entry_page(request, date, AppSettings.load())


def _entry_page(request, date, app_settings):
    actor = request.user
    owner = _entry_owner(request)
    today = dates.today()
    existing = SadhanaEntry.objects.filter(user=owner, date=date).first()
    blocked = entries.restriction(actor, date, exists=existing is not None, app_settings=app_settings, today=today)
    fields = effective_fields(owner)
    page_url = _entry_url(date, owner, actor)

    if request.method == "POST":
        if blocked:
            messages.error(request, blocked)
            return redirect(page_url)
        form = EntryForm(request.POST, fields=fields, entry=existing)
        if form.is_valid():
            entries.save_entry(owner, date, form.values(), actor=actor, ip=get_client_ip(request))
            messages.success(request, _("Hare Krishna! Your sadhana has been saved."))
            return redirect(page_url)
    else:
        form = EntryForm(fields=fields, entry=existing)

    recent_dates = [today - timedelta(days=offset) for offset in range(RECENT_DAYS - 1, -1, -1)]
    filled = set(
        SadhanaEntry.objects.filter(user=owner, date__in=recent_dates).values_list("date", flat=True)
    )
    history = analytics.load_days(owner)
    month = month_calendar.parse(request.GET.get("month"), date, today)
    context = {
        "form": form,
        "owner": owner,
        "owner_is_user": owner == actor,
        "streak_badges": [
            {"field": field, "streaks": analytics.field_streaks(history, field, today)}
            for field in fields
            if has_personal_streak(field)
        ],
        "date": date,
        "today": today,
        "is_today": date == today,
        "entry": existing,
        "blocked": blocked,
        "saved_values": existing.values.select_related("field").order_by("field__order") if existing else [],
        "page_url": page_url,
        "delete_url": _entry_url(date, owner, actor, name="entry_delete"),
        "prev_url": _entry_url(date - timedelta(days=1), owner, actor),
        "next_url": _entry_url(date + timedelta(days=1), owner, actor) if date < today else None,
        "user_query": "" if owner == actor else f"?user={owner.pk}",
        "recent": [
            {"date": day, "filled": day in filled, "url": _entry_url(day, owner, actor), "current": day == date}
            for day in recent_dates
        ],
        "calendar": _calendar(month, date, set(history), owner, actor, app_settings, today),
        # Once the day is saved: the vehicle and that day's Utsāha.
        "journey": yatra.journey(owner, history, yatra.Setup.load(), utsaha_day=date) if existing else None,
    }
    return render(request, "sadhana/entry.html", context)


def _calendar(month, date, filled, owner, actor, app_settings, today):
    """The month grid under the entry form: filled and missed days, festivals, and links to each day."""
    festival_days = festivals.festival_dates(month, month_calendar.last_day(month))

    def is_closed(day):
        return entries.restriction(actor, day, exists=False, app_settings=app_settings, today=today) is not None

    def month_url(first):
        url = _entry_url(date, owner, actor)
        return f"{url}{'&' if '?' in url else '?'}month={first:%Y-%m}#calendar"

    weeks = month_calendar.weeks(
        month, filled=filled, festivals=festival_days, today=today, selected=date, is_closed=is_closed,
    )
    previous, following = month_calendar.neighbours(month, today)
    days_filled, days_so_far = month_calendar.filled_summary(month, filled, today)
    return {
        "month": month,
        "weekdays": [WEEKDAYS_ABBR[index] for index in range(7)],
        "weeks": [
            [cell and {"cell": cell, "url": _entry_url(cell.date, owner, actor)} for cell in week] for week in weeks
        ],
        "prev_url": month_url(previous),
        "next_url": month_url(following) if following else None,
        "days_filled": days_filled,
        "days_so_far": days_so_far,
        "festivals": sorted(festival_days.items()),
    }


@require_POST
def entry_delete(request, date):
    actor = request.user
    owner = _entry_owner(request)
    existing = get_object_or_404(SadhanaEntry, user=owner, date=date)
    blocked = entries.restriction(
        actor, date, exists=True, app_settings=AppSettings.load(), today=dates.today()
    )
    if blocked:
        messages.error(request, blocked)
    else:
        entries.delete_entry(existing, actor=actor, ip=get_client_ip(request))
        messages.success(request, _("The entry has been deleted."))
    return redirect(_entry_url(date, owner, actor))


class DateConverter:
    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value):
        return date_cls.fromisoformat(value)

    def to_url(self, value):
        return value.isoformat() if hasattr(value, "isoformat") else value


@require_POST
def my_theme(request):
    """A devotee picks their own colour theme; an empty choice goes back to the site default."""
    theme = request.POST.get("theme", "")
    if theme == "" or themes.header_color(theme):
        request.user.theme = theme
        request.user.save(update_fields=["theme"])
    back = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = "home"
    return redirect(back)
