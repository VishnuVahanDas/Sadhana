from django.urls import path, register_converter

from . import views

register_converter(views.DateConverter, "date")

urlpatterns = [
    path("", views.home, name="home"),
    path("entry/<date:date>/", views.entry, name="entry"),
    path("entry/<date:date>/delete/", views.entry_delete, name="entry_delete"),
    path("me/", views.me, name="me"),
    path("ranks/", views.ranks, name="ranks"),
    path("analysis/", views.analysis, name="analysis"),
    path("devotees/", views.devotees, name="devotees"),
]
