"""Colour themes. Superusers set the site default; each devotee may pick their own in the More menu."""

from django.utils.translation import gettext_lazy as _

DEFAULT = "saffron"

# (key, label, header colour for the browser's theme-color). Colours live in static/src/input.css.
THEMES = [
    ("saffron", _("Saffron & Maroon (current)"), "#7A1F2B"),
    ("kesari", _("Kesari"), "#B8470F"),
    ("sunrise", _("Sunrise"), "#B4374A"),
    ("sandalwood", _("Sandalwood"), "#5B3A21"),
    ("govardhan", _("Govardhan"), "#4A5D23"),
    ("tulsi", _("Tulsi Green"), "#1F4D3A"),
    ("peacock", _("Peacock"), "#0F4C5C"),
    ("krishna", _("Krishna Blue"), "#1E2F6B"),
    ("royal", _("Royal Purple"), "#4B2A7B"),
    ("lotus", _("Lotus"), "#8A2456"),
    ("aurora", _("Aurora"), "#4F46E5"),
    ("jagannath", _("Jagannath"), "#1C1917"),
    ("slate", _("Slate"), "#24303F"),
    ("midnight", _("Midnight Saffron (dark)"), "#1F1814"),
    ("night", _("Night Blue (dark)"), "#141A30"),
    ("emerald", _("Emerald (dark)"), "#12201A"),
    ("graphite", _("Graphite Violet (dark)"), "#18181D"),
]


CHOICES = [(key, label) for key, label, _header in THEMES]


def header_color(theme):
    """The theme's header colour, or None for an unknown key."""
    return next((header for key, _label, header in THEMES if key == theme), None)


def for_user(user, default):
    """The theme a page is drawn in: the devotee's own choice if valid, else the site default."""
    own = getattr(user, "theme", "")
    if header_color(own):
        return own
    return default if header_color(default) else DEFAULT
