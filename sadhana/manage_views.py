from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, Max, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.decorators import superuser_required
from audit import services as audit
from audit.models import AuditLog

from .manage_forms import AppSettingsForm, SadhanaFieldForm
from .models import AppSettings, EntryValue, SadhanaField, UserFieldSetting

Action = AuditLog.Action


def _log_changes(request, action, form, before, *, field_key=None):
    """One audit row per changed form field. With field_key, the attribute name goes into the values."""
    ip = audit.get_client_ip(request)
    for name in form.changed_data:
        old, new = before.get(name), form.cleaned_data.get(name)
        if field_key:
            audit.log(action, request.user, field_key=field_key, old_value=f"{name}={old}", new_value=f"{name}={new}", ip=ip)
        else:
            audit.log(action, request.user, field_key=name, old_value=old, new_value=new, ip=ip)


def _fields_with_usage():
    return SadhanaField.objects.annotate(has_values=Exists(EntryValue.objects.filter(field=OuterRef("pk"))))


# --- Fields ---------------------------------------------------------------


@superuser_required
def field_list(request):
    return render(request, "manage/field_list.html", {"fields": _fields_with_usage()})


@superuser_required
def field_create(request):
    form = SadhanaFieldForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        field = form.save(commit=False)
        field.order = (SadhanaField.objects.aggregate(last=Max("order"))["last"] or 0) + 10
        field.save()
        audit.log(
            Action.FIELD_CREATE, request.user, field_key=field.key,
            new_value=f"{field.label} ({field.field_type})", ip=audit.get_client_ip(request),
        )
        messages.success(request, _("Field “%(label)s” has been added.") % {"label": field.label})
        return redirect("manage_fields")
    return render(request, "manage/field_form.html", {"form": form, "field": None})


@superuser_required
def field_edit(request, pk):
    field = get_object_or_404(SadhanaField, pk=pk)
    form = SadhanaFieldForm(request.POST or None, instance=field)
    before = {name: getattr(field, name) for name in form.fields}
    if request.method == "POST" and form.is_valid():
        form.save()
        _log_changes(request, Action.FIELD_UPDATE, form, before, field_key=field.key)
        messages.success(request, _("Field “%(label)s” has been updated.") % {"label": field.label})
        return redirect("manage_fields")
    return render(request, "manage/field_form.html", {"form": form, "field": field})


@superuser_required
@require_POST
@transaction.atomic
def field_move(request, pk):
    fields = list(SadhanaField.objects.all())
    index = next((i for i, field in enumerate(fields) if field.pk == pk), None)
    target = None if index is None else index + (-1 if request.POST.get("direction") == "up" else 1)
    if target is not None and 0 <= target < len(fields):
        fields[index], fields[target] = fields[target], fields[index]
        for position, field in enumerate(fields, 1):
            if field.order != position * 10:
                field.order = position * 10
                field.save(update_fields=["order"])
    return redirect("manage_fields")


@superuser_required
@require_POST
@transaction.atomic
def field_apply_to_all(request, pk):
    """Switch a field on or off for everyone: set the default and drop the per-user overrides."""
    field = get_object_or_404(SadhanaField, pk=pk)
    enabled = request.POST.get("enabled") == "1"
    overrides = UserFieldSetting.objects.filter(field=field)
    audit.log(
        Action.FIELD_UPDATE, request.user, field_key=field.key,
        old_value=f"enabled_by_default={field.enabled_by_default}, user overrides={overrides.count()}",
        new_value=f"enabled_by_default={enabled}, applied to all users",
        ip=audit.get_client_ip(request),
    )
    overrides.delete()
    field.enabled_by_default = enabled
    field.save(update_fields=["enabled_by_default"])
    if enabled:
        messages.success(request, _("“%(label)s” is now on for all users.") % {"label": field.label})
    else:
        messages.success(request, _("“%(label)s” is now off for all users.") % {"label": field.label})
    return redirect("manage_fields")


@superuser_required
@require_POST
def field_delete(request, pk):
    field = get_object_or_404(_fields_with_usage(), pk=pk)
    if field.is_core or field.has_values:
        messages.error(request, _("This field is in use and can only be deactivated, not deleted."))
    else:
        audit.log(
            Action.FIELD_UPDATE, request.user, field_key=field.key,
            old_value=f"{field.label} ({field.field_type})", new_value="deleted", ip=audit.get_client_ip(request),
        )
        field.delete()
        messages.success(request, _("Field “%(label)s” has been deleted.") % {"label": field.label})
    return redirect("manage_fields")


# --- Per-user field toggles -----------------------------------------------


@superuser_required
def user_fields(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    overrides = dict(UserFieldSetting.objects.filter(user=target).values_list("field_id", "enabled"))
    rows = [
        {"field": field, "enabled": overrides.get(field.id, field.enabled_by_default), "overridden": field.id in overrides}
        for field in SadhanaField.objects.filter(is_active=True)
    ]
    if request.method == "POST":
        wanted = set(request.POST.getlist("field"))
        ip = audit.get_client_ip(request)
        with transaction.atomic():
            for row in rows:
                enabled = str(row["field"].id) in wanted
                if enabled != row["enabled"]:
                    UserFieldSetting.objects.update_or_create(
                        user=target, field=row["field"], defaults={"enabled": enabled}
                    )
                    audit.log(
                        Action.FIELD_TOGGLE_USER, request.user, target_user=target,
                        field_key=row["field"].key, old_value=row["enabled"], new_value=enabled, ip=ip,
                    )
        messages.success(request, _("Fields for %(name)s have been saved.") % {"name": target.display_name})
        return redirect("manage_users")
    return render(request, "manage/user_fields.html", {"target": target, "rows": rows})


# --- Settings -------------------------------------------------------------


@superuser_required
def app_settings(request):
    settings = AppSettings.load()
    form = AppSettingsForm(request.POST or None, instance=settings)
    before = {name: getattr(settings, name) for name in form.fields}
    if request.method == "POST" and form.is_valid():
        form.save()
        _log_changes(request, Action.SETTINGS_UPDATE, form, before)
        messages.success(request, _("Settings have been saved."))
        return redirect("manage_settings")
    return render(request, "manage/settings.html", {"form": form})
