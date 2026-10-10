from django.urls import path

from . import views

urlpatterns = [
    path("manage/audit/", views.audit_log, name="manage_audit"),
]
