from datetime import date as date_cls
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from audit.services import get_client_ip

from .forms import EntryForm
from .models import AppSettings, SadhanaEntry
from .services import analytics, dates, entries
from .services.fields import effective_fields

RECENT_DAYS = 7


def placeholder(title, phase):
    """Stand-in page for a screen that a later build phase will replace."""

    def view(request):
        return render(request, "placeholder.html", {"title": title, "phase": phase})

    return view


ranks = placeholder(gettext_lazy("Ranks"), 5)
analysis = placeholder(gettext_lazy("Analysis"), 5)


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
    context = {
        "form": form,
        "owner": owner,
        "streak_badges": [
            {"field": field, "streaks": analytics.field_streaks(history, field, today)}
            for field in fields
            if field.has_streak
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
    }
    return render(request, "sadhana/entry.html", context)


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
