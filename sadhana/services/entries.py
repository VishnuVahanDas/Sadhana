from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from audit import services as audit
from audit.models import AuditLog

from ..models import EntryValue, SadhanaEntry


def restriction(actor, date, *, exists, app_settings, today):
    """Why `actor` may not save or delete the entry for `date`, or None if they may.

    Superusers are only stopped by future dates.
    """
    if date > today:
        return _("Entries cannot be made for future dates.")
    if actor.is_superuser:
        return None
    if exists and app_settings.edit_lock_enabled:
        if date < today - timedelta(days=app_settings.edit_window_days):
            return _("This entry is older than %(days)d days and can no longer be changed.") % {
                "days": app_settings.edit_window_days
            }
    if not exists and app_settings.backfill_limit_enabled:
        if date < today - timedelta(days=app_settings.backfill_limit_days):
            return _("Entries older than %(days)d days can no longer be added.") % {
                "days": app_settings.backfill_limit_days
            }
    return None


@transaction.atomic
def save_entry(owner, date, values, *, actor, ip=None):
    """Create or update the one entry for (owner, date).

    `values` maps SadhanaField -> typed value, with None meaning "not entered".
    Fields that are not in `values` are left untouched. Writes one audit row per
    changed value and returns (entry, created).
    """
    try:
        with transaction.atomic():
            entry, created = SadhanaEntry.objects.get_or_create(
                user=owner, date=date, defaults={"created_by": actor, "updated_by": actor}
            )
    except IntegrityError:
        # Lost a race with another request for the same day: update that entry instead.
        entry, created = SadhanaEntry.objects.get(user=owner, date=date), False

    entry = SadhanaEntry.objects.select_for_update().get(pk=entry.pk)
    existing = {row.field_id: row for row in entry.values.select_related("field")}
    action = AuditLog.Action.ENTRY_CREATE if created else AuditLog.Action.ENTRY_UPDATE
    changed = False

    for field, new in values.items():
        row = existing.get(field.id)
        old = row.value if row else None
        if old == new:
            continue
        if new is None:
            row.delete()
        else:
            row = row or EntryValue(entry=entry, field=field)
            row.value = new
            row.save()
        audit.log(
            action, actor, target_user=owner, entry_date=date, field_key=field.key,
            old_value=old, new_value=new, ip=ip,
        )
        changed = True

    if created and not changed:
        # An empty entry still counts as "filled"; keep its creation traceable.
        audit.log(action, actor, target_user=owner, entry_date=date, ip=ip)
    elif changed and not created:
        entry.updated_by = actor
        entry.save(update_fields=["updated_by", "updated_at"])
    return entry, created


@transaction.atomic
def delete_entry(entry, *, actor, ip=None):
    rows = list(entry.values.select_related("field"))
    for row in rows:
        audit.log(
            AuditLog.Action.ENTRY_DELETE, actor, target_user=entry.user, entry_date=entry.date,
            field_key=row.field.key, old_value=row.value, ip=ip,
        )
    if not rows:
        audit.log(AuditLog.Action.ENTRY_DELETE, actor, target_user=entry.user, entry_date=entry.date, ip=ip)
    entry.delete()
