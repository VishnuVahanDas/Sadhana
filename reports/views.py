from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from sadhana.models import SadhanaEntry, SadhanaField
from sadhana.services import analytics, dates, periods, ranking
from sadhana.services.fields import effective_fields

from .exports import workbook_response

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


# --- Shared helpers -------------------------------------------------------


def _labels(period):
    return [date.strftime("%-d %b") for date in period.dates()]


def _period_line(period):
    return _("Period: %(start)s to %(end)s") % {"start": period.start.isoformat(), "end": period.end.isoformat()}


def _cell(value):
    """A stored value as text for the entries table; None when nothing was entered."""
    if value is None:
        return None
    if value is True:
        return _("Yes")
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def _scope(request):
    """Participating users for the group views: everyone, or one coordinator with their team."""
    people = User.objects.filter(is_participating=True).select_related("coordinator")
    coordinator = None
    coordinator_id = request.GET.get("coordinator", "")
    if coordinator_id.isdigit():
        coordinator = User.objects.filter(pk=coordinator_id).first()
    if coordinator:
        people = people.filter(Q(coordinator=coordinator) | Q(pk=coordinator.pk))
    return list(people), coordinator


def _rankable_field(request, name):
    """The rankable field picked with ?<name>=<key>, defaulting to the first one."""
    fields = list(SadhanaField.objects.filter(is_active=True, is_rankable=True))
    chosen = next((field for field in fields if field.key == request.GET.get(name)), None)
    return fields, chosen or (fields[0] if fields else None)


def _coordinator_name(user):
    return user.coordinator.display_name if user.coordinator else ""


# --- Individual dashboard -------------------------------------------------


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
                "labels": _labels(period),
                "datasets": [
                    {"label": field.label, "color": SERIES_COLORS[index], "data": analytics.series(days, field, period)}
                    for index, field in enumerate(members)
                ],
            }
        )
    return charts


def _dashboard_data(request, pk):
    person = get_object_or_404(User.objects.select_related("coordinator"), pk=pk)
    today = dates.today()
    period = periods.from_request(request.GET, today)
    fields = effective_fields(person)
    days = analytics.load_days(person)
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
    return person, today, period, fields, days, rows


def dashboard(request, pk):
    person, today, period, fields, days, rows = _dashboard_data(request, pk)
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
        "can_edit": request.user == person or request.user.is_superuser,
        "keep": {"heat": heat_field.key} if heat_field and "heat" in request.GET else {},
    }
    return render(request, "reports/dashboard.html", context)


def dashboard_export(request, pk):
    person, _today, period, fields, _days, rows = _dashboard_data(request, pk)
    headers = [_("Date")] + [field.label for field in fields] + [_("On time")]
    data = []
    for row, day in ((row, _days[row["date"]]) for row in rows):
        values = [day.values.get(field.id) for field in fields]
        # Numbers stay numbers in Excel; everything else is written as text.
        cells = [value if isinstance(value, int) and not isinstance(value, bool) else (_cell(value) or "") for value in values]
        data.append([row["date"], *cells, _("Yes") if row["on_time"] else _("Late")])
    return workbook_response(
        f"sadhana-{person.display_name}-{period.start}-to-{period.end}",
        _("Entries"),
        [person.display_name, _period_line(period)],
        headers,
        data,
    )


# --- Group / All analysis -------------------------------------------------


def _analysis_data(request):
    today = dates.today()
    period = periods.from_request(request.GET, today)
    people, coordinator = _scope(request)
    fields, field = _rankable_field(request, "field")
    days_by_user = analytics.load_days_for_users(people)
    rows = analytics.user_rows(people, days_by_user, field, period, today) if field else []
    rows.sort(key=lambda row: (-row.stats.total, row.user.display_name.lower()))
    return today, period, people, coordinator, fields, field, days_by_user, rows


def analysis(request):
    today, period, people, coordinator, fields, field, days_by_user, rows = _analysis_data(request)
    charts = []
    if field:
        totals, averages = analytics.community_series(people, days_by_user, field, period)
        unit = field.unit or (_("days") if field.field_type == SadhanaField.FieldType.BOOLEAN else "")
        for title, data in [(_("Daily total"), totals), (_("Daily average per person"), averages)]:
            charts.append(
                {
                    "title": f"{field.label} — {title}",
                    "unit": unit,
                    "labels": _labels(period),
                    "datasets": [{"label": title, "color": SERIES_COLORS[0], "data": data}],
                }
            )
    filled_today = set(SadhanaEntry.objects.filter(date=today, user__in=people).values_list("user_id", flat=True))
    keep = {"field": field.key} if field else {}
    if coordinator:
        keep["coordinator"] = coordinator.pk
    context = {
        "period": period,
        "presets": periods.PRESETS,
        "keep": keep,
        "fields": fields,
        "field": field,
        "coordinator": coordinator,
        "coordinators": User.objects.filter(is_coordinator=True),
        "summary": analytics.group_summary(rows, period, today),
        "charts": charts,
        "rows": rows,
        "not_filled": sorted((user for user in people if user.pk not in filled_today), key=lambda u: u.display_name.lower()),
        "today": today,
    }
    return render(request, "reports/analysis.html", context)


def analysis_export(request):
    _today, period, _people, coordinator, _fields, field, _days, rows = _analysis_data(request)
    headers = [_("Name"), _("Coordinator"), _("Total"), _("Daily average"), _("Days filled")]
    if field and field.has_streak:
        headers += [_("Current streak"), _("On-time streak")]
    data = []
    for row in rows:
        line = [row.user.display_name, _coordinator_name(row.user), row.stats.total, row.stats.daily_average, row.stats.days_filled]
        if row.streaks:
            line += [row.streaks.current, row.streaks.on_time_current]
        data.append(line)
    scope = coordinator.display_name if coordinator else _("All devotees")
    label = field.label if field else ""
    return workbook_response(
        f"sadhana-analysis-{label}-{period.start}-to-{period.end}",
        _("Analysis"),
        [f"{label} — {scope}", _period_line(period)],
        headers,
        data,
    )


# --- Rank table -----------------------------------------------------------


def _ranks_data(request):
    today = dates.today()
    period = periods.from_request(request.GET, today)
    people, coordinator = _scope(request)
    fields, field = _rankable_field(request, "metric")
    option = ranking.choose(field, request.GET.get("by", "")) if field else None
    ranked = []
    if field:
        days_by_user = analytics.load_days_for_users(people)
        ranked = ranking.rank_rows(analytics.user_rows(people, days_by_user, field, period, today), option)
    return period, coordinator, fields, field, option, ranked


def ranks(request):
    period, coordinator, fields, field, option, ranked = _ranks_data(request)
    keep = {"metric": field.key, "by": option.key} if field else {}
    if coordinator:
        keep["coordinator"] = coordinator.pk
    context = {
        "period": period,
        "presets": periods.PRESETS,
        "keep": keep,
        "fields": fields,
        "field": field,
        "option": option,
        "options": ranking.options_for(field) if field else [],
        "coordinator": coordinator,
        "coordinators": User.objects.filter(is_coordinator=True),
        "ranked": ranked,
    }
    return render(request, "reports/ranks.html", context)


def ranks_export(request):
    period, coordinator, _fields, field, option, ranked = _ranks_data(request)
    label = f"{field.label} — {option.label}" if field else ""
    intro = [label, coordinator.display_name if coordinator else _("All devotees")]
    if option and option.uses_period:
        intro.append(_period_line(period))
    return workbook_response(
        f"sadhana-ranks-{field.key if field else ''}-{option.key if option else ''}",
        _("Ranks"),
        intro,
        [_("Rank"), _("Name"), _("Coordinator"), str(option.label) if option else ""],
        [[item["rank"], item["row"].user.display_name, _coordinator_name(item["row"].user), item["value"]] for item in ranked],
    )
