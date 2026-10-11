from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext as _


def superuser_required(view):
    """403 for anyone who is not a superuser. Login itself is enforced by middleware."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def superuser_or_home(view):
    """For pages a devotee may reach by an old link (Analysis): back to Today with a note, not an error page."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.info(request, _("Analysis is for the temple coordinators. Your own numbers are on My Report."))
            return redirect("home")
        return view(request, *args, **kwargs)

    return wrapped
