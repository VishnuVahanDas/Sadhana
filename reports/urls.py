from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.me, name="me"),
    path("devotees/", views.devotees, name="devotees"),
    path("u/<int:pk>/", views.dashboard, name="dashboard"),
]
