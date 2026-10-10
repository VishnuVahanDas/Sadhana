from datetime import timedelta

from django.utils import timezone


def today():
    """Today's date in IST."""
    return timezone.localdate()


def default_entry_date(rollover_hour, now=None):
    """The date the entry form opens on: yesterday until the rollover hour (IST)."""
    local = timezone.localtime(now)
    if local.hour < rollover_hour:
        return local.date() - timedelta(days=1)
    return local.date()
