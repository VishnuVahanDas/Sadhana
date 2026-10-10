from . import themes
from .models import AppSettings


def site(request):
    settings = AppSettings.load()
    theme = settings.theme if themes.header_color(settings.theme) else themes.DEFAULT
    return {
        "site_title": settings.site_title,
        "theme": theme,
        "theme_color": themes.header_color(theme),
        "themes": themes.THEMES,
    }
