from django.urls import path, register_converter

from . import manage_views, views

register_converter(views.DateConverter, "date")

urlpatterns = [
    path("", views.home, name="home"),
    path("entry/<date:date>/", views.entry, name="entry"),
    path("entry/<date:date>/delete/", views.entry_delete, name="entry_delete"),
    path("theme/", views.my_theme, name="my_theme"),
    path("manage/users/<int:pk>/fields/", manage_views.user_fields, name="manage_user_fields"),
    path("manage/fields/", manage_views.field_list, name="manage_fields"),
    path("manage/fields/add/", manage_views.field_create, name="manage_field_add"),
    path("manage/fields/<int:pk>/", manage_views.field_edit, name="manage_field_edit"),
    path("manage/fields/<int:pk>/move/", manage_views.field_move, name="manage_field_move"),
    path("manage/fields/<int:pk>/apply/", manage_views.field_apply_to_all, name="manage_field_apply"),
    path("manage/fields/<int:pk>/reset/", manage_views.field_reset, name="manage_field_reset"),
    path("manage/fields/<int:pk>/users/", manage_views.field_users, name="manage_field_users"),
    path("manage/fields/<int:pk>/delete/", manage_views.field_delete, name="manage_field_delete"),
    path("manage/settings/", manage_views.app_settings, name="manage_settings"),
    path("manage/festivals/", manage_views.festival_list, name="manage_festivals"),
    path("manage/festivals/add/", manage_views.festival_edit, name="manage_festival_add"),
    path("manage/festivals/<int:pk>/", manage_views.festival_edit, name="manage_festival_edit"),
    path("manage/festivals/<int:pk>/delete/", manage_views.festival_delete, name="manage_festival_delete"),
    path("manage/yatra/", manage_views.yatra_levels, name="manage_yatra"),
    path("manage/yatra/<str:kind>/<int:pk>/", manage_views.yatra_level_edit, name="manage_yatra_edit"),
    path("manage/theme/reset/", manage_views.reset_user_themes, name="manage_theme_reset"),
]
