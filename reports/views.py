from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from sadhana.models import Festival, SadhanaEntry, SadhanaField
from sadhana.services import analytics, comparison, dates, festivals, periods, ranking
from sadhana.services.fields import effective_fields, has_personal_streak

from .exports import workbook_response
from .services import scaling

User = get_user_model()

Period = periods.Period


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


def _scale(field):
    """(clean axis steps, floor) for a field's "usual range" cap."""
    if field.field_type == SadhanaField.FieldType.MINUTES:
        return scaling.MINUTE_STEPS, field.target or scaling.MINUTE_FLOOR
    if field.field_type == SadhanaField.FieldType.COUNT:
        return scaling.COUNT_STEPS, field.target or scaling.COUNT_FLOOR
    return scaling.COUNT_STEPS, field.target


def _chart(title, unit, period, values, lead_in, festival_days, steps, floor):
    """One bar chart: daily values, a 7-day average line, the usual-range cap and festival bands.

    `values` are always the real numbers. The cap only tells the page where to
    cut the axis; days above it are listed in `clipped` with their real value.
    """
    dates = period.dates()
    labels = [date.strftime("%-d %b") for date in dates]
    cap = scaling.usual_cap(values, steps, floor)
    return {
        "title": title,
        "unit": unit,
        "labels": labels,
        "values": values,
        "average": scaling.rolling_average(values, lead_in),
        "cap": cap,
        "clipped": [{"index": index, "label": labels[index], "value": value} for index, value in scaling.clipped(values, cap)],
        "festivals": {index: ", ".join(festival_days[date]) for index, date in enumerate(dates) if date in festival_days},
    }


def _compare_chart(title, unit, period, previous_period, values, previous_values, festival_days, steps, floor):
    """Two periods overlaid day by day: this period as bars, the previous one as a line."""
    chart = _chart(title, unit, period, values, (), festival_days, steps, floor)
    earlier = comparison.align(previous_values, len(values))
    # One cap for both, so the two periods are read against the same axis.
    cap = scaling.usual_cap(values + [value for value in earlier if value], steps, floor)
    previous_dates = previous_period.dates()
    chart.update(
        cap=cap,
        clipped=[{"index": index, "label": chart["labels"][index], "value": value} for index, value in scaling.clipped(values, cap)],
        previous=earlier,
        previous_labels=comparison.align([date.strftime("%-d %b") for date in previous_dates], len(values)),
    )
    del chart["average"]
    return chart


def _number_charts(*groups):
    """Give every chart on the page its position in the one JSON list the chart script reads."""
    everything = [chart for group in groups for chart in group]
    for index, chart in enumerate(everything):
        chart["id"] = index
    return everything


def _comparing(request):
    return request.GET.get("compare") == "1"


def _compare_url(request):
    """The current page with the comparison switched the other way."""
    query = request.GET.copy()
    if _comparing(request):
        query.pop("compare", None)
    else:
        query["compare"] = "1"
    return f"{request.path}?{query.urlencode()}" if query else request.path


def _festival_note(period, previous_period, festival_days, previous_festival_days):
    """Festival names when only one of the two periods has festival days — usually why the numbers differ."""
    if bool(festival_days) == bool(previous_festival_days):
        return None
    days = festival_days or previous_festival_days
    names = sorted({name for names in days.values() for name in names})
    return {"names": ", ".join(names), "in_current": bool(festival_days)}


def _lead_in(period):
    """The six days before a period, so the 7-day average starts with a full window."""
    return Period(periods.CUSTOM, period.start - timedelta(days=scaling.ROLLING_WINDOW - 1), period.start - timedelta(days=1))


def _period_line(period):
    return _("Period: %(start)s to %(end)s") % {"start": period.start.isoformat(), "end": period.end.isoformat()}


def _previous_line(period):
    return _("Compared with: %(start)s to %(end)s") % {"start": period.start.isoformat(), "end": period.end.isoformat()}


def _change_cells(change):
    """A Change as Excel cells: now, before, difference, percent (blank where there is nothing to compare)."""
    return [change.current, change.previous, change.difference, change.percent]


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
    """The field picked with ?<name>=<key>, defaulting to the first one.

    Ranks and analysis compare everyone, so they only offer the core fields (hearing, reading, seva,
    rounds); optional fields are switched on for some devotees only and show on My Report instead.
    """
    fields = list(SadhanaField.objects.filter(is_active=True, is_rankable=True, is_core=True))
    chosen = next((field for field in fields if field.key == request.GET.get(name)), None)
    return fields, chosen or (fields[0] if fields else None)


def _coordinator_name(user):
    return user.coordinator.display_name if user.coordinator else ""


# --- Individual dashboard -------------------------------------------------


def _charts(days, fields, period, festival_days):
    """One chart per numeric field, each with its own axis, so a spike in one never squashes another."""
    charts = []
    for field in fields:
        if field.is_numeric:
            steps, floor = _scale(field)
            charts.append(
                _chart(
                    field.label, field.unit, period,
                    analytics.series(days, field, period),
                    analytics.series(days, field, _lead_in(period)),
                    festival_days, steps, floor,
                )
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
            "levels": [None] * len(fields),
            "edit_url": reverse("entry", args=[day.date]) + suffix,
        }
        for day in sorted(days.values(), key=lambda day: day.date, reverse=True)
        if period.start <= day.date <= period.end
    ]
    # Shade each number / yes-no column on its own scale; the text columns stay plain.
    for position, field in enumerate(fields):
        if analytics.is_measurable(field):
            values = [days[row["date"]].values.get(field.id) for row in rows]
            steps, floor = _scale(field)
            top = scaling.daily_top([analytics.number(value) for value in values], steps, floor)
            for row, value in zip(rows, values):
                row["levels"][position] = scaling.shade_level(value, top)
    for row in rows:
        row["shaded"] = list(zip(row["cells"], row["levels"]))
    return person, today, period, fields, days, rows


def dashboard(request, pk):
    person, today, period, fields, days, rows = _dashboard_data(request, pk)
    rankable = [field for field in fields if field.is_rankable]
    cards = [
        {
            "field": field,
            "stats": analytics.field_stats(days, field, period, person.date_joined, today),
            "streaks": analytics.field_streaks(days, field, today) if has_personal_streak(field) else None,
        }
        for field in rankable
    ]
    for card in cards:
        # Percentages for the progress ring (days filled) and the bar (daily average against the target).
        stats, target = card["stats"], card["field"].target
        card["filled_pct"] = min(100, round(100 * stats.days_filled / period.days))
        card["target_pct"] = min(100, round(100 * stats.daily_average / target)) if target else None
    heat_field = next((field for field in rankable if field.key == request.GET.get("heat")), None)
    heat_field = heat_field or (rankable[0] if rankable else None)
    heat_top = None
    if heat_field and heat_field.is_numeric:
        # Colour by the usual range, not the year's biggest day; real values stay in the tooltips.
        steps, floor = _scale(heat_field)
        heat_top = scaling.usual_cap(list(analytics.heatmap_values(days, heat_field, today).values()), steps, floor)
    festival_days = festivals.festival_dates(period.start, period.end)
    charts = _charts(days, fields, period, festival_days)
    compare = _dashboard_comparison(person, days, fields, period, today, festival_days) if _comparing(request) else None
    keep = {"heat": heat_field.key} if heat_field and "heat" in request.GET else {}
    if compare:
        keep["compare"] = "1"
    context = {
        "person": person,
        "period": period,
        "presets": periods.PRESETS,
        "fields": fields,
        "cards": cards,
        "charts": charts,
        "compare": compare,
        "compare_url": _compare_url(request),
        "chart_data": _number_charts(charts, [item["chart"] for item in compare["fields"] if item["chart"]] if compare else []),
        "heat_fields": rankable,
        "heat_field": heat_field,
        "heatmap": analytics.heatmap(days, heat_field, today, top=heat_top) if heat_field else [],
        "heat_top": heat_top,
        "rows": rows,
        "can_edit": request.user == person or request.user.is_superuser,
        "keep": keep,
    }
    return render(request, "reports/dashboard.html", context)


def _dashboard_comparison(person, days, fields, period, today, festival_days):
    """Each rankable field in this period against the previous one."""
    earlier = periods.previous(period)
    earlier_festival_days = festivals.festival_dates(earlier.start, earlier.end)
    # Nothing to compare with if the devotee had not started yet in the earlier period.
    had_started = analytics.average_days(earlier, person.date_joined, today, min(days, default=None)) > 0
    items = []
    for field in fields:
        if not field.is_rankable:
            continue
        current = analytics.field_stats(days, field, period, person.date_joined, today)
        previous = analytics.field_stats(days, field, earlier, person.date_joined, today) if had_started else None
        chart = None
        if field.is_numeric and had_started:
            steps, floor = _scale(field)
            chart = _compare_chart(
                field.label, field.unit, period, earlier,
                analytics.series(days, field, period), analytics.series(days, field, earlier),
                festival_days, steps, floor,
            )
        items.append({"field": field, "metrics": comparison.compare_stats(current, previous), "chart": chart})
    return {
        "previous": earlier,
        "had_started": had_started,
        "fields": items,
        "festival_note": _festival_note(period, earlier, festival_days, earlier_festival_days),
    }


def dashboard_export(request, pk):
    person, today, period, fields, _days, rows = _dashboard_data(request, pk)
    headers = [_("Date")] + [field.label for field in fields] + [_("On time")]
    data = []
    for row, day in ((row, _days[row["date"]]) for row in rows):
        values = [day.values.get(field.id) for field in fields]
        # Numbers stay numbers in Excel; everything else is written as text.
        cells = [value if isinstance(value, int) and not isinstance(value, bool) else (_cell(value) or "") for value in values]
        data.append([row["date"], *cells, _("Yes") if row["on_time"] else _("Late")])
    extra_sheets = []
    if _comparing(request):
        compare = _dashboard_comparison(person, _days, fields, period, today, {})
        extra_sheets.append(
            (
                _("Comparison"),
                [person.display_name, _period_line(period), _previous_line(compare["previous"])],
                [_("Field"), _("Measure"), _("This period"), _("Previous period"), _("Change"), _("Change %")],
                [
                    [item["field"].label, str(metric["label"]), *_change_cells(metric["change"])]
                    for item in compare["fields"]
                    for metric in item["metrics"]
                ],
            )
        )
    return workbook_response(
        f"sadhana-{person.display_name}-{period.start}-to-{period.end}",
        _("Entries"),
        [person.display_name, _period_line(period)],
        headers,
        data,
        extra_sheets,
        shade=[[position + 2] for position, field in enumerate(fields) if field.is_numeric],
    )


# --- Group / All analysis -------------------------------------------------


def _day_filter(request, period):
    """(?days= key, festival dates in the period, date -> bool filter or None)."""
    key = festivals.choose(request.GET.get("days", ""))
    festival_days = festivals.festival_dates(period.start, period.end)
    return key, festival_days, festivals.day_filter(key, festival_days)


def _analysis_data(request):
    today = dates.today()
    period = periods.from_request(request.GET, today)
    people, coordinator = _scope(request)
    fields, field = _rankable_field(request, "field")
    days_key, festival_days, day_filter = _day_filter(request, period)
    days_by_user = analytics.load_days_for_users(people)
    rows = analytics.user_rows(people, days_by_user, field, period, today, day_filter) if field else []
    rows.sort(key=lambda row: (-row.stats.total, row.user.display_name.lower()))
    return today, period, people, coordinator, fields, field, days_by_user, rows, days_key, festival_days, day_filter


def _analysis_comparison(request, period, people, field, days_by_user, rows, today, days_key, festival_days, day_filter):
    """The group, and each devotee, in this period against the previous one (same Days filter)."""
    earlier = periods.previous(period)
    earlier_festival_days = festivals.festival_dates(earlier.start, earlier.end)
    earlier_filter = festivals.day_filter(days_key, earlier_festival_days)
    earlier_rows = {
        row.user.pk: row for row in analytics.user_rows(people, days_by_user, field, earlier, today, earlier_filter)
    }
    now = analytics.group_summary(rows, period, today, day_filter)
    before = analytics.group_summary(list(earlier_rows.values()), earlier, today, earlier_filter)
    by_user = {}
    for row in rows:
        user = row.user
        # "—" rather than 0 for someone who had not started yet in the earlier period.
        had_started = analytics.average_days(
            earlier, user.date_joined, today, min(days_by_user[user.pk], default=None), earlier_filter
        ) > 0
        previous = earlier_rows[user.pk].stats.daily_average if had_started else None
        by_user[user.pk] = comparison.Change(row.stats.daily_average, previous)
    steps, floor = _scale(field)
    averages = analytics.community_series(people, days_by_user, field, period)[1]
    earlier_averages = analytics.community_series(people, days_by_user, field, earlier)[1]
    unit = field.unit or (_("days") if field.field_type == SadhanaField.FieldType.BOOLEAN else "")
    return {
        "previous": earlier,
        "summary": [
            {"label": _("Per person per day"), "change": comparison.Change(now.average_per_person_per_day, before.average_per_person_per_day)},
            {"label": _("Average per person"), "change": comparison.Change(now.average_per_person, before.average_per_person)},
            {"label": _("Total"), "change": comparison.Change(now.total, before.total)},
        ],
        "by_user": by_user,
        "chart": _compare_chart(
            f"{field.label} — {_('Daily average per person')}", unit, period, earlier,
            averages, earlier_averages, festival_days, steps, floor,
        ),
        "festival_note": None if days_key != festivals.ALL else _festival_note(period, earlier, festival_days, earlier_festival_days),
    }


def _festival_summaries(period, people, days_by_user, field):
    """For each festival in the period: the field's total on its days and how many devotees took part."""
    summaries = []
    for festival in Festival.objects.filter(start_date__lte=period.end, end_date__gte=period.start).order_by("start_date"):
        start, end = max(festival.start_date, period.start), min(festival.end_date, period.end)
        totals = [
            sum(
                analytics.number(day.values.get(field.id))
                for date, day in days_by_user[user.pk].items()
                if start <= date <= end
            )
            for user in people
        ]
        summaries.append({"festival": festival, "total": sum(totals), "devotees": sum(1 for total in totals if total)})
    return summaries


def analysis(request):
    (today, period, people, coordinator, fields, field, days_by_user, rows,
     days_key, festival_days, day_filter) = _analysis_data(request)
    charts = []
    if field:
        totals, averages = analytics.community_series(people, days_by_user, field, period)
        lead_totals, lead_averages = analytics.community_series(people, days_by_user, field, _lead_in(period))
        unit = field.unit or (_("days") if field.field_type == SadhanaField.FieldType.BOOLEAN else "")
        steps, floor = _scale(field)
        charts = [
            # The group total has no per-person floor: it grows with the number of devotees.
            _chart(f"{field.label} — {_('Daily total')}", unit, period, totals, lead_totals, festival_days, steps, None),
            _chart(
                f"{field.label} — {_('Daily average per person')}", unit, period,
                averages, lead_averages, festival_days, steps, floor,
            ),
        ]
    filled_today = set(SadhanaEntry.objects.filter(date=today, user__in=people).values_list("user_id", flat=True))
    keep = {"field": field.key} if field else {}
    if coordinator:
        keep["coordinator"] = coordinator.pk
    if days_key != festivals.ALL:
        keep["days"] = days_key
    compare = None
    if field and _comparing(request):
        compare = _analysis_comparison(
            request, period, people, field, days_by_user, rows, today, days_key, festival_days, day_filter
        )
        keep["compare"] = "1"
    context = {
        "compare": compare,
        "compare_url": _compare_url(request),
        "chart_data": _number_charts(charts, [compare["chart"]] if compare else []),
        "period": period,
        "presets": periods.PRESETS,
        "keep": keep,
        "fields": fields,
        "field": field,
        "coordinator": coordinator,
        "coordinators": User.objects.filter(is_coordinator=True),
        "day_filters": festivals.DAY_FILTERS,
        "days_key": days_key,
        "summary": analytics.group_summary(rows, period, today, day_filter),
        "festival_summaries": _festival_summaries(period, people, days_by_user, field) if field else [],
        "charts": charts,
        "rows": rows,
        # (row, Change in daily average or None) so the table can show the comparison columns.
        "table": _analysis_table(rows, compare),
        "not_filled": sorted((user for user in people if user.pk not in filled_today), key=lambda u: u.display_name.lower()),
        "today": today,
    }
    return render(request, "reports/analysis.html", context)


def _analysis_table(rows, compare):
    """(row, Change in daily average or None, shade of the total, shade of the daily average) per devotee."""
    total_top = scaling.relative_top([row.stats.total for row in rows])
    average_top = scaling.relative_top([row.stats.daily_average for row in rows])
    return [
        (
            row,
            compare["by_user"][row.user.pk] if compare else None,
            scaling.shade_level(row.stats.total, total_top),
            scaling.shade_level(row.stats.daily_average, average_top),
        )
        for row in rows
    ]


def analysis_export(request):
    (today, period, people, coordinator, _fields, field, days_by_user, rows,
     days_key, festival_days, day_filter) = _analysis_data(request)
    compare = None
    if field and _comparing(request):
        compare = _analysis_comparison(
            request, period, people, field, days_by_user, rows, today, days_key, festival_days, day_filter
        )
    headers = [_("Name"), _("Coordinator"), _("Total"), _("Daily average"), _("Typical day"), _("Days filled")]
    if field and field.has_streak:
        headers += [_("Current streak"), _("On-time streak")]
    if compare:
        headers += [_("Previous daily average"), _("Change"), _("Change %")]
    data = []
    for row in rows:
        line = [
            row.user.display_name, _coordinator_name(row.user),
            row.stats.total, row.stats.daily_average, row.stats.typical_day, row.stats.days_filled,
        ]
        if row.streaks:
            line += [row.streaks.current, row.streaks.on_time_current]
        if compare:
            line += _change_cells(compare["by_user"][row.user.pk])[1:]
        data.append(line)
    scope = coordinator.display_name if coordinator else _("All devotees")
    label = field.label if field else ""
    intro = [f"{label} — {scope}", _period_line(period), str(dict(festivals.DAY_FILTERS)[days_key])]
    if compare:
        intro.append(_previous_line(compare["previous"]))
    return workbook_response(
        f"sadhana-analysis-{label}-{period.start}-to-{period.end}", _("Analysis"), intro, headers, data,
        shade=[[3], [4]],  # Total and Daily average, each on its own scale
    )


# --- Rank table -----------------------------------------------------------


def _ranks_data(request):
    today = dates.today()
    period = periods.from_request(request.GET, today)
    people, coordinator = _scope(request)
    fields, field = _rankable_field(request, "metric")
    option = ranking.choose(field, request.GET.get("by", "")) if field else None
    days_key, _festival_days, day_filter = _day_filter(request, period)
    ranked = []
    if field:
        days_by_user = analytics.load_days_for_users(people)
        ranked = ranking.rank_rows(analytics.user_rows(people, days_by_user, field, period, today, day_filter), option)
    return period, coordinator, fields, field, option, ranked, days_key


def ranks(request):
    period, coordinator, fields, field, option, ranked, days_key = _ranks_data(request)
    keep = {"metric": field.key, "by": option.key} if field else {}
    if coordinator:
        keep["coordinator"] = coordinator.pk
    if days_key != festivals.ALL:
        keep["days"] = days_key
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
        "day_filters": festivals.DAY_FILTERS,
        "days_key": days_key,
        "ranked": ranked,
    }
    return render(request, "reports/ranks.html", context)


def ranks_export(request):
    period, coordinator, _fields, field, option, ranked, days_key = _ranks_data(request)
    label = f"{field.label} — {option.label}" if field else ""
    intro = [label, coordinator.display_name if coordinator else _("All devotees")]
    if option and option.uses_period:
        intro += [_period_line(period), str(dict(festivals.DAY_FILTERS)[days_key])]
    return workbook_response(
        f"sadhana-ranks-{field.key if field else ''}-{option.key if option else ''}",
        _("Ranks"),
        intro,
        [_("Rank"), _("Name"), _("Coordinator"), str(option.label) if option else ""],
        [[item["rank"], item["row"].user.display_name, _coordinator_name(item["row"].user), item["value"]] for item in ranked],
    )


# --- Sheet: every devotee and the core fields in one table -----------------

SHEET_TOTAL, SHEET_DAILY = "total", "daily"
SHEET_SHOWS = [(SHEET_TOTAL, _lazy("Totals")), (SHEET_DAILY, _lazy("Daily"))]
SHEET_MAX_DAYS = 31  # the on-screen daily grid stops here; the Excel export has every day


def _sheet_data(request, max_days=None):
    """Rows for the sheet. Totals: one number per field. Daily: per day (newest first), one value per field."""
    today = dates.today()
    period = periods.from_request(request.GET, today)
    people, coordinator = _scope(request)
    people.sort(key=lambda person: person.display_name.lower())
    fields, _field = _rankable_field(request, "")
    show = SHEET_DAILY if request.GET.get("show") == SHEET_DAILY else SHEET_TOTAL
    days_by_user = analytics.load_days_for_users(people)
    data = {"period": period, "coordinator": coordinator, "fields": fields, "show": show, "today": today}

    if show == SHEET_TOTAL:
        rows = []
        for person in people:
            stats = [analytics.field_stats(days_by_user[person.pk], field, period, person.date_joined, today) for field in fields]
            rows.append({
                "user": person,
                "cells": [item.total for item in stats],
                "days_filled": stats[0].days_filled if stats else 0,
            })
        columns = list(zip(*(row["cells"] for row in rows))) or [() for _field in fields]
        # Each field column is shaded relative to the group.
        tops = [scaling.relative_top(column) for column in columns]
        for row in rows:
            row["shaded"] = [(value, scaling.shade_level(value, top)) for value, top in zip(row["cells"], tops)]
        return {**data, "rows": rows, "footer": [sum(column) for column in columns]}

    all_days = [day for day in reversed(period.dates()) if day <= today]
    shown = all_days[:max_days] if max_days else all_days
    festival_days = festivals.festival_dates(period.start, period.end)
    rows = []
    for person in people:
        entered = days_by_user[person.pk]
        # None = nothing entered for that field on that day.
        rows.append({
            "user": person,
            "days": [[entered[day].values.get(field.id) if day in entered else None for field in fields] for day in shown],
        })
    # One scale per field across every devotee and day shown, so the same shade means the same value.
    tops = []
    for position, field in enumerate(fields):
        steps, floor = _scale(field)
        values = [analytics.number(day[position]) for row in rows for day in row["days"]]
        tops.append(scaling.daily_top(values, steps, floor))
    for row in rows:
        row["shaded_days"] = [
            [(value, scaling.shade_level(value, top)) for value, top in zip(day, tops)] for day in row["days"]
        ]
    footer = [
        [sum(analytics.number(row["days"][index][position]) for row in rows) for position in range(len(fields))]
        for index in range(len(shown))
    ]
    return {
        **data,
        "rows": rows,
        "footer": footer,
        "days": [{"date": day, "festivals": festival_days.get(day, [])} for day in shown],
        "hidden_days": len(all_days) - len(shown),
    }


def sheet(request):
    data = _sheet_data(request, max_days=SHEET_MAX_DAYS)
    period, coordinator, today = data["period"], data["coordinator"], data["today"]
    keep = {"show": data["show"]} if data["show"] != SHEET_TOTAL else {}
    if coordinator:
        keep["coordinator"] = coordinator.pk

    def day_link(label, day):
        query = urlencode({**keep, "period": periods.CUSTOM, "start": day.isoformat(), "end": day.isoformat()})
        return {"label": label, "url": f"?{query}", "active": period.start == period.end == day}

    context = {
        **data,
        "presets": periods.PRESETS,
        "keep": keep,
        "shows": SHEET_SHOWS,
        "coordinators": User.objects.filter(is_coordinator=True),
        "day_links": [day_link(_("Today"), today), day_link(_("Yesterday"), today - timedelta(days=1))],
    }
    return render(request, "reports/sheet.html", context)


def sheet_export(request):
    data = _sheet_data(request)
    period, coordinator, fields, rows = data["period"], data["coordinator"], data["fields"], data["rows"]
    labels = [f"{field.label} ({field.unit})" if field.unit else field.label for field in fields]
    headers = [_("Name"), _("Coordinator")]
    if data["show"] == SHEET_TOTAL:
        headers += labels + [_("Days filled")]
        lines = [[row["user"].display_name, _coordinator_name(row["user"]), *row["cells"], row["days_filled"]] for row in rows]
        lines.append([_("Group total"), "", *data["footer"], ""])
        shade = [[position + 3] for position in range(len(fields))]
    else:
        # One block of field columns per day, newest first, as on the page.
        headers += [f"{day['date']:%a %d %b} · {label}" for day in data["days"] for label in labels]
        lines = [
            [row["user"].display_name, _coordinator_name(row["user"]), *(_sheet_cell(value) for day in row["days"] for value in day)]
            for row in rows
        ]
        lines.append([_("Group total"), "", *(value for day in data["footer"] for value in day)])
        # A field's columns, one per day, share one scale.
        shade = [
            [3 + day * len(fields) + position for day in range(len(data["days"]))] for position in range(len(fields))
        ]
    return workbook_response(
        f"sadhana-sheet-{period.start}-to-{period.end}",
        _("Sheet"),
        [coordinator.display_name if coordinator else _("All devotees"), _period_line(period), str(dict(SHEET_SHOWS)[data["show"]])],
        headers,
        lines,
        shade=shade,
        unshaded_last_rows=1,  # the group total
    )


def _sheet_cell(value):
    """Numbers stay numbers in Excel; nothing entered is an empty cell."""
    return "" if value is None else analytics.number(value)
