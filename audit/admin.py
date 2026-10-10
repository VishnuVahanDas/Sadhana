from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "action", "target_user", "entry_date", "field_key", "old_value", "new_value")
    list_filter = ("action", "timestamp")
    search_fields = ("field_key", "actor__name", "actor__spiritual_name", "target_user__name")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
