from django.contrib import admin

from .models import AppSettings, EntryValue, SadhanaEntry, SadhanaField, UserFieldSetting


@admin.register(SadhanaField)
class SadhanaFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "field_type", "order", "is_active", "enabled_by_default", "has_streak", "is_rankable", "is_core")
    list_editable = ("order", "is_active", "enabled_by_default")
    prepopulated_fields = {"key": ("label",)}

    def has_delete_permission(self, request, obj=None):
        # Core fields can only be deactivated. Fields with stored values are protected by the FK.
        return not (obj and obj.is_core)


@admin.register(UserFieldSetting)
class UserFieldSettingAdmin(admin.ModelAdmin):
    list_display = ("user", "field", "enabled")
    list_filter = ("field", "enabled")


class EntryValueInline(admin.TabularInline):
    model = EntryValue
    extra = 0


@admin.register(SadhanaEntry)
class SadhanaEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "created_at", "updated_at", "updated_by")
    list_filter = ("user",)
    date_hierarchy = "date"
    inlines = [EntryValueInline]


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
