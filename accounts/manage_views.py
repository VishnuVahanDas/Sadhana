from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from audit import services as audit
from audit.models import AuditLog

from .decorators import superuser_required
from .forms import PasswordResetForm, UserCreateForm, UserForm
from .models import User

Action = AuditLog.Action

AUDITED_FIELDS = [
    "email", "name", "spiritual_name", "phone", "coordinator", "is_coordinator", "is_participating", "is_superuser",
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
    return Action.USER_UPDATE


@superuser_required
def user_list(request):
    users = User.objects.select_related("coordinator").order_by("-is_participating", "name")
    return render(request, "manage/user_list.html", {"users": users})


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
