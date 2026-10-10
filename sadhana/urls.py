from django.urls import path, register_converter

from . import manage_views, views

register_converter(views.DateConverter, "date")

urlpatterns = [
    path("", views.home, name="home"),
    path("entry/<date:date>/", views.entry, name="entry"),
    path("entry/<date:date>/delete/", views.entry_delete, name="entry_delete"),
    path("me/", views.me, name="me"),
    path("ranks/", views.ranks, name="ranks"),
    path("analysis/", views.analysis, name="analysis"),
    path("devotees/", views.devotees, name="devotees"),
    path("manage/users/<int:pk>/fields/", manage_views.user_fields, name="manage_user_fields"),
    path("manage/fields/", manage_views.field_list, name="manage_fields"),
    path("manage/fields/add/", manage_views.field_create, name="manage_field_add"),
    path("manage/fields/<int:pk>/", manage_views.field_edit, name="manage_field_edit"),
    path("manage/fields/<int:pk>/move/", manage_views.field_move, name="manage_field_move"),
    path("manage/fields/<int:pk>/apply/", manage_views.field_apply_to_all, name="manage_field_apply"),
    path("manage/fields/<int:pk>/delete/", manage_views.field_delete, name="manage_field_delete"),
    path("manage/settings/", manage_views.app_settings, name="manage_settings"),
]
