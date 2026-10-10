from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.me, name="me"),
    path("devotees/", views.devotees, name="devotees"),
    path("u/<int:pk>/", views.dashboard, name="dashboard"),
    path("analysis/", views.analysis, name="analysis"),
    path("ranks/", views.ranks, name="ranks"),
    path("export/u/<int:pk>/", views.dashboard_export, name="dashboard_export"),
    path("export/analysis/", views.analysis_export, name="analysis_export"),
    path("export/ranks/", views.ranks_export, name="ranks_export"),
]
