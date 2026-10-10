from functools import wraps

from django.core.exceptions import PermissionDenied


def superuser_required(view):
    """403 for anyone who is not a superuser. Login itself is enforced by middleware."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
