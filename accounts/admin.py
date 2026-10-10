from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import AdminUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = AdminUserCreationForm
    ordering = ("name",)
    list_display = ("email", "name", "spiritual_name", "coordinator", "is_participating", "is_superuser")
    list_filter = ("is_participating", "is_coordinator", "is_superuser")
    search_fields = ("email", "name", "spiritual_name")
    readonly_fields = ("last_login",)
    filter_horizontal = ()
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Devotee"), {"fields": ("name", "spiritual_name", "phone", "coordinator", "is_coordinator")}),
        (
            _("Status"),
            {"fields": ("is_participating", "is_superuser", "is_active", "must_change_password")},
        ),
        (_("Dates"), {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),
    )
