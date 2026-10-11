from . import themes
from .models import AppSettings


def site(request):
    settings = AppSettings.load()
    default = themes.for_user(None, settings.theme)
    user = getattr(request, "user", None)
    theme = themes.for_user(user, default)
    return {
        "site_title": settings.site_title,
        "theme": theme,
        "theme_color": themes.header_color(theme),
        "themes": themes.THEMES,
        "default_theme_label": dict(themes.CHOICES)[default],
        "rank_table_enabled": settings.rank_table_enabled,
        # Simple mode hides the streaks; the views do not compute them either.
        "show_streaks": bool(user and user.is_authenticated and user.is_advanced),
    }
