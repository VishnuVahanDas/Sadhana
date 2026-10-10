import ipaddress

from .models import AuditLog


def get_client_ip(request):
    """Client IP, preferring the address Nginx forwards. None if it is not a valid IP."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def to_text(value):
    """String form of a field value for the log; empty string for 'not entered'."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def log(action, actor, *, target_user=None, entry_date=None, field_key="", old_value=None, new_value=None, ip=None):
    return AuditLog.objects.create(
        action=action,
        actor=actor,
        target_user=target_user,
        entry_date=entry_date,
        field_key=field_key,
        old_value=to_text(old_value),
        new_value=to_text(new_value),
        ip_address=ip,
    )
