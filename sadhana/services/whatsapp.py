"""The "Send to coordinator on WhatsApp" link: a wa.me URL with the day's report pre-filled.

Nothing is sent by the server; the devotee's own WhatsApp opens and they tap Send.
"""

from urllib.parse import quote

from django.utils.formats import date_format
from django.utils.translation import gettext as _

from accounts.phones import whatsapp_number

from ..models import SadhanaField
from .fields import effective_fields

FieldType = SadhanaField.FieldType

SITE_DOMAIN = "sr.iskcongorakhpur.com"
NOTES_KEY = "notes"
NOTES_LIMIT = 300


def _shorten(text):
    text = text.strip()
    return text if len(text) <= NOTES_LIMIT else text[:NOTES_LIMIT].rstrip() + "…"


def _format(field, value):
    if field.field_type == FieldType.BOOLEAN:
        return _("Yes") if value else _("No")
    if field.field_type == FieldType.TIME:
        return value.strftime("%H:%M")
    if field.field_type == FieldType.TEXT:
        return _shorten(value)
    # "Rounds: 16", not "Rounds: 16 rounds".
    if field.unit and field.unit.casefold() != field.label.casefold():
        return f"{value} {field.unit}"
    return str(value)


def day_message(user, date, values, fields=None):
    """The report for one day: only the fields that are enabled for the devotee and filled, in field order.

    `values` maps field id -> typed value. Never mentions streaks, Utsāha or the Yatra level.
    """
    if fields is None:
        fields = effective_fields(user)
    lines = [
        _("🙏 Hare Krishna Prabhu"),
        _("Sadhana report — %(date)s") % {"date": date_format(date, "l, j M Y")},
        user.display_name,
    ]
    notes = None
    for field in fields:
        value = values.get(field.id)
        if value is None:
            continue
        if field.key == NOTES_KEY:
            notes = _shorten(value)
        else:
            lines.append(f"- {field.label}: {_format(field, value)}")
    if notes:
        lines.append(_("Notes: %(notes)s") % {"notes": notes})
    lines.append(SITE_DOMAIN)
    return "\n".join(lines)


def coordinator_number(user):
    """The WhatsApp number of the devotee's coordinator, or None when there is nobody to send to."""
    if not user.coordinator_id or user.coordinator_id == user.pk:
        return None
    return whatsapp_number(user.coordinator.phone)


def day_link(user, date, values, fields=None):
    """The wa.me link for one day's report, or None when the button is hidden for this devotee."""
    number = coordinator_number(user) if user.show_whatsapp_button else None
    if not number:
        return None
    # quote() percent-encodes as UTF-8, so the emoji, ā/ṛ/ṣ and the line breaks all survive.
    return f"https://wa.me/{number}?text={quote(day_message(user, date, values, fields), safe='')}"


def _values(entry):
    return {row.field_id: row.value for row in entry.values.select_related("field")}


def build_whatsapp_message(entry):
    return day_message(entry.user, entry.date, _values(entry))


def build_whatsapp_link(entry):
    """The wa.me link for this entry, or None when the button is hidden."""
    return day_link(entry.user, entry.date, _values(entry))
