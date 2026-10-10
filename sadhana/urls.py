from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("me/", views.me, name="me"),
    path("ranks/", views.ranks, name="ranks"),
    path("analysis/", views.analysis, name="analysis"),
    path("devotees/", views.devotees, name="devotees"),
]
