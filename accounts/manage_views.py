from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from audit import services as audit
from audit.models import AuditLog

from .decorators import superuser_required
from .forms import PasswordResetForm, UserCreateForm, UserDeleteForm, UserForm
from .models import UiMode, User

Action = AuditLog.Action

AUDITED_FIELDS = [
    "email", "name", "spiritual_name", "phone", "coordinator", "is_coordinator", "is_participating", "is_superuser",
    "ui_mode",
]


def _snapshot(user):
    values = {name: getattr(user, name) for name in AUDITED_FIELDS}
    values["coordinator"] = user.coordinator.display_name if user.coordinator else None
    return values


def _action_for(name, new):
    if name == "is_participating":
        return Action.USER_REACTIVATE if new else Action.USER_DEACTIVATE
    if name == "is_superuser":
        return Action.SUPERUSER_GRANT if new else Action.SUPERUSER_REVOKE
    if name == "ui_mode":
        return Action.UI_MODE_CHANGE
    return Action.USER_UPDATE


@superuser_required
def user_list(request):
    users = User.objects.select_related("coordinator").order_by("-is_participating", "name")
    mode = request.GET.get("mode", "")
    if mode in UiMode.values:
        users = users.filter(ui_mode=mode)
    else:
        mode = ""
    return render(request, "manage/user_list.html", {"users": users, "mode": mode, "modes": UiMode.choices})


@superuser_required
@require_POST
def user_bulk_mode(request):
    """Set the display mode of the ticked users. One audit row per user whose mode really changed."""
    mode = request.POST.get("ui_mode", "")
    ids = [value for value in request.POST.getlist("users") if value.isdigit()]
    if mode not in UiMode.values:
        messages.error(request, _("Choose Simple or Advanced."))
    elif not ids:
        messages.error(request, _("Tick at least one user first."))
    else:
        ip = audit.get_client_ip(request)
        changed = 0
        with transaction.atomic():
            for target in User.objects.filter(pk__in=ids).exclude(ui_mode=mode):
                old, target.ui_mode = target.ui_mode, mode
                target.save(update_fields=["ui_mode"])
                audit.log(
                    Action.UI_MODE_CHANGE, request.user, target_user=target,
                    field_key="ui_mode", old_value=old, new_value=mode, ip=ip,
                )
                changed += 1
        messages.success(
            request,
            ngettext(
                "%(count)d user set to %(mode)s.", "%(count)d users set to %(mode)s.", changed
            ) % {"count": changed, "mode": UiMode(mode).label},
        )
    back = request.POST.get("filter", "")
    url = redirect("manage_users").url
    return redirect(f"{url}?mode={back}" if back in UiMode.values else url)


@superuser_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user, password = form.save()
        audit.log(
            Action.USER_CREATE, request.user, target_user=user, new_value=user.email, ip=audit.get_client_ip(request)
        )
        return render(request, "manage/password_result.html", {"target": user, "password": password, "created": True})
    return render(request, "manage/user_form.html", {"form": form, "target": None})


@superuser_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    before = _snapshot(target)
    form = UserForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        target = form.save()
        ip = audit.get_client_ip(request)
        for name, new in _snapshot(target).items():
            if new != before[name]:
                audit.log(
                    _action_for(name, new), request.user, target_user=target,
                    field_key=name, old_value=before[name], new_value=new, ip=ip,
                )
        messages.success(request, _("%(name)s has been updated.") % {"name": target.display_name})
        return redirect("manage_users")
    return render(request, "manage/user_form.html", {"form": form, "target": target})


@superuser_required
def user_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = PasswordResetForm(request.POST or None, user=target)
    if request.method == "POST" and form.is_valid():
        password = form.save()
        audit.log(Action.PASSWORD_RESET, request.user, target_user=target, ip=audit.get_client_ip(request))
        return render(request, "manage/password_result.html", {"target": target, "password": password, "created": False})
    return render(request, "manage/password_form.html", {"form": form, "target": target})


def _delete_blocked(actor, target):
    """Why `target` cannot be deleted by `actor`, or None if they can."""
    if target == actor:
        return _("You cannot delete your own account. Ask another superuser.")
    others = User.objects.filter(is_superuser=True, is_active=True).exclude(pk=target.pk)
    if target.is_superuser and not others.exists():
        return _("This is the last superuser and cannot be deleted.")
    return None


@superuser_required
def user_delete(request, pk):
    """Permanently delete a devotee and everything they entered, after a warning.

    A coordinator's devotees are first moved to another coordinator, or to none.
    """
    target = get_object_or_404(User, pk=pk)
    blocked = _delete_blocked(request.user, target)
    team = list(target.team_members.order_by("name"))
    form = UserDeleteForm(request.POST or None, target=target)
    if request.method == "POST" and not blocked and form.is_valid():
        ip = audit.get_client_ip(request)
        new_coordinator = form.cleaned_data.get("new_coordinator")
        name, entry_count = target.display_name, target.entries.count()
        with transaction.atomic():
            for member in team:
                member.coordinator = new_coordinator
                member.save(update_fields=["coordinator"])
                audit.log(
                    Action.USER_UPDATE, request.user, target_user=member, field_key="coordinator",
                    old_value=name, new_value=new_coordinator.display_name if new_coordinator else None, ip=ip,
                )
            # The log's link to the user goes blank once they are deleted, so keep who it was as text.
            audit.log(
                Action.USER_DELETE, request.user,
                old_value=f"{name} <{target.email}>, {entry_count} entries", ip=ip,
            )
            target.delete()
        messages.success(request, _("%(name)s has been deleted.") % {"name": name})
        return redirect("manage_users")
    context = {
        "form": form,
        "target": target,
        "blocked": blocked,
        "team": team,
        "entry_count": target.entries.count(),
    }
    return render(request, "manage/user_delete.html", context)
