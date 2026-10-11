import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Spaces, dashes, dots, brackets and "+" are how people write numbers; anything else is a mistake.
SEPARATORS = re.compile(r"[\s\-.()+]")


def normalise_phone(value):
    """An Indian mobile number as wa.me wants it: digits only with the country code, e.g. 919876543210.

    Accepts 9876543210, 09876543210, +91 98765 43210 and 919876543210. Raises ValidationError otherwise.
    """
    digits = SEPARATORS.sub("", value or "")
    if digits.isascii() and digits.isdigit():
        if len(digits) == 10:
            return "91" + digits
        if len(digits) == 11 and digits.startswith("0"):
            return "91" + digits[1:]
        if len(digits) == 12 and digits.startswith("91"):
            return digits
    raise ValidationError(
        _("Enter a 10-digit mobile number, with or without +91 (for example 98765 43210)."), code="invalid_phone"
    )


def whatsapp_number(value):
    """The number for a wa.me link, or None when the stored phone is empty or not valid."""
    try:
        return normalise_phone(value)
    except ValidationError:
        return None
