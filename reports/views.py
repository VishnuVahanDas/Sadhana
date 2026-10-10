from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from sadhana.services import analytics, dates, periods
from sadhana.services.fields import effective_fields

User = get_user_model()

# Validated for colour-blind separation on a white surface; saffron first to match the theme.
SERIES_COLORS = ["#D9660F", "#2A78D6", "#1BAF7A", "#4A3AA7"]


def me(request):
    return redirect("dashboard", pk=request.user.pk)


def devotees(request):
    people = User.objects.select_related("coordinator").order_by("-is_participating", "spiritual_name", "name")
    query = request.GET.get("q", "").strip()
    coordinator = request.GET.get("coordinator", "")
    status = request.GET.get("status", "")
    if query:
        people = people.filter(Q(name__icontains=query) | Q(spiritual_name__icontains=query))
    if coordinator.isdigit():
        people = people.filter(Q(coordinator_id=coordinator) | Q(pk=coordinator))
    if status == "active":
        people = people.filter(is_participating=True)
    elif status == "inactive":
        people = people.filter(is_participating=False)
    context = {
        "people": people,
        "q": query,
        "coordinator": coordinator,
        "status": status,
        "coordinators": User.objects.filter(is_coordinator=True),
    }
    return render(request, "reports/devotees.html", context)


def _charts(days, fields, period):
    """One chart per unit, so minutes and rounds never share an axis."""
    groups = {}
    for field in fields:
        if field.is_numeric:
            groups.setdefault((field.field_type, field.unit), []).append(field)
    charts = []
    for (_field_type, unit), members in groups.items():
        members = members[: len(SERIES_COLORS)]
        charts.append(
            {
                "title": " · ".join(field.label for field in members),
                "unit": unit,
                "labels": [date.strftime("%-d %b") for date in period.dates()],
                "datasets": [
                    {"label": field.label, "color": SERIES_COLORS[index], "data": analytics.series(days, field, period)}
                    for index, field in enumerate(members)
                ],
            }
        )
    return charts


def _cell(value):
    """A stored value as text for the entries table; None when nothing was entered."""
    if value is None:
        return None
    if value is True:
        return _("Yes")
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def dashboard(request, pk):
    person = get_object_or_404(User.objects.select_related("coordinator"), pk=pk)
    today = dates.today()
    period = periods.from_request(request.GET, today)
    fields = effective_fields(person)
    days = analytics.load_days(person)
    rankable = [field for field in fields if field.is_rankable]

    cards = [
        {
            "field": field,
            "stats": analytics.field_stats(days, field, period, person.date_joined, today),
            "streaks": analytics.field_streaks(days, field, today) if field.has_streak else None,
        }
        for field in rankable
    ]

    heat_field = next((field for field in rankable if field.key == request.GET.get("heat")), None)
    heat_field = heat_field or (rankable[0] if rankable else None)

    can_edit = request.user == person or request.user.is_superuser
    suffix = "" if request.user == person else f"?user={person.pk}"
    rows = [
        {
            "date": day.date,
            "on_time": day.on_time,
            "cells": [_cell(day.values.get(field.id)) for field in fields],
            "edit_url": reverse("entry", args=[day.date]) + suffix,
        }
        for day in sorted(days.values(), key=lambda day: day.date, reverse=True)
        if period.start <= day.date <= period.end
    ]

    context = {
        "person": person,
        "period": period,
        "presets": periods.PRESETS,
        "fields": fields,
        "cards": cards,
        "charts": _charts(days, fields, period),
        "heat_fields": rankable,
        "heat_field": heat_field,
        "heatmap": analytics.heatmap(days, heat_field, today) if heat_field else [],
        "rows": rows,
        "can_edit": can_edit,
        "keep": {"heat": heat_field.key} if heat_field and "heat" in request.GET else {},
    }
    return render(request, "reports/dashboard.html", context)
