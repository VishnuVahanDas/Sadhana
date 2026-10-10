"""Temporary theme preview. Remove once a theme is finalised (see the "Theme preview" notes in input.css)."""

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


def header_color(theme):
    """The theme's header colour, or None for an unknown key."""
    return next((header for key, _label, header in THEMES if key == theme), None)
