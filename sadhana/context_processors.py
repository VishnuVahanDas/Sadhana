from .models import AppSettings


def site(request):
    return {"site_title": AppSettings.load().site_title}
