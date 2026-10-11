from . import themes
from .models import AppSettings


def site(request):
    settings = AppSettings.load()
    default = themes.for_user(None, settings.theme)
    theme = themes.for_user(getattr(request, "user", None), default)
    return {
        "site_title": settings.site_title,
        "theme": theme,
        "theme_color": themes.header_color(theme),
        "themes": themes.THEMES,
        "default_theme_label": dict(themes.CHOICES)[default],
        "rank_table_enabled": settings.rank_table_enabled,
    }
