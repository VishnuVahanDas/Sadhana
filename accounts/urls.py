from django.contrib.auth.views import LogoutView
from django.urls import path

from . import manage_views, views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("manage/users/", manage_views.user_list, name="manage_users"),
    path("manage/users/add/", manage_views.user_create, name="manage_user_add"),
    path("manage/users/mode/", manage_views.user_bulk_mode, name="manage_users_mode"),
    path("manage/users/<int:pk>/", manage_views.user_edit, name="manage_user_edit"),
    path("manage/users/<int:pk>/password/", manage_views.user_password, name="manage_user_password"),
    path("manage/users/<int:pk>/delete/", manage_views.user_delete, name="manage_user_delete"),
]
