from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Append-only record of who changed what. One row per changed field value."""

    class Action(models.TextChoices):
        ENTRY_CREATE = "entry_create", _("Entry created")
        ENTRY_UPDATE = "entry_update", _("Entry updated")
        ENTRY_DELETE = "entry_delete", _("Entry deleted")
        USER_CREATE = "user_create", _("User created")
        USER_UPDATE = "user_update", _("User updated")
        USER_DELETE = "user_delete", _("User deleted")
        PASSWORD_RESET = "password_reset", _("Password reset")
        USER_DEACTIVATE = "user_deactivate", _("User marked inactive")
        USER_REACTIVATE = "user_reactivate", _("User reactivated")
        SUPERUSER_GRANT = "superuser_grant", _("Superuser granted")
        SUPERUSER_REVOKE = "superuser_revoke", _("Superuser revoked")
        FIELD_CREATE = "field_create", _("Field created")
        FIELD_UPDATE = "field_update", _("Field updated")
        FIELD_TOGGLE_USER = "field_toggle_user", _("Field toggled for user")
        SETTINGS_UPDATE = "settings_update", _("Settings updated")
        FESTIVAL_CREATE = "festival_create", _("Festival created")
        FESTIVAL_UPDATE = "festival_update", _("Festival updated")
        FESTIVAL_DELETE = "festival_delete", _("Festival deleted")

    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("actor"),
        null=True,
        on_delete=models.SET_NULL,
        related_name="audit_actions",
    )
    action = models.CharField(_("action"), max_length=32, choices=Action.choices)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("target user"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_targets",
    )
    entry_date = models.DateField(_("entry date"), null=True, blank=True)
    # The key is stored as a string so logs survive field changes.
    field_key = models.CharField(_("field key"), max_length=64, blank=True)
    old_value = models.TextField(_("old value"), blank=True)
    new_value = models.TextField(_("new value"), blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)

    class Meta:
        verbose_name = _("audit log entry")
        verbose_name_plural = _("audit log")
        ordering = ["-timestamp", "-id"]
        indexes = [models.Index(fields=["target_user", "entry_date"])]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} {self.field_key}".strip()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("Audit log rows are append-only and cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Audit log rows are append-only and cannot be deleted.")
