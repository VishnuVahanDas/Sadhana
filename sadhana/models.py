from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SadhanaField(models.Model):
    class FieldType(models.TextChoices):
        MINUTES = "minutes", _("Minutes")
        COUNT = "count", _("Count")
        TIME = "time", _("Time of day")
        BOOLEAN = "boolean", _("Yes / No")
        TEXT = "text", _("Text")

    # Upper bounds used when max_value is not set.
    DEFAULT_MAX = {FieldType.MINUTES: 1440, FieldType.COUNT: 9999}

    key = models.SlugField(_("key"), unique=True)
    label = models.CharField(_("label"), max_length=100)
    field_type = models.CharField(_("type"), max_length=10, choices=FieldType.choices)
    unit = models.CharField(_("unit"), max_length=20, blank=True)
    min_value = models.IntegerField(_("minimum"), null=True, blank=True)
    max_value = models.IntegerField(_("maximum"), null=True, blank=True)
    has_streak = models.BooleanField(_("has streak"), default=False)
    is_rankable = models.BooleanField(_("rankable"), default=False)
    is_core = models.BooleanField(_("core field"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    enabled_by_default = models.BooleanField(_("enabled by default"), default=True)
    order = models.IntegerField(_("order"), default=0)
    help_text = models.CharField(_("help text"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("sadhana field")
        verbose_name_plural = _("sadhana fields")
        ordering = ["order", "id"]

    def __str__(self):
        return self.label

    @property
    def is_numeric(self):
        return self.field_type in (self.FieldType.MINUTES, self.FieldType.COUNT)

    @property
    def effective_min(self):
        return max(self.min_value or 0, 0)

    @property
    def effective_max(self):
        if self.max_value is not None:
            return self.max_value
        return self.DEFAULT_MAX.get(self.field_type)


class UserFieldSetting(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="field_settings")
    field = models.ForeignKey(SadhanaField, on_delete=models.CASCADE, related_name="user_settings")
    enabled = models.BooleanField(_("enabled"))

    class Meta:
        verbose_name = _("user field setting")
        verbose_name_plural = _("user field settings")
        constraints = [
            models.UniqueConstraint(fields=["user", "field"], name="one_setting_per_user_per_field"),
        ]

    def __str__(self):
        return f"{self.user} / {self.field}: {'on' if self.enabled else 'off'}"


class SadhanaEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entries")
    # The sadhana day, not the submit time.
    date = models.DateField(_("date"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = _("sadhana entry")
        verbose_name_plural = _("sadhana entries")
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="one_entry_per_user_per_day"),
        ]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user} — {self.date}"

    @property
    def is_on_time(self):
        from .services.dates import is_on_time

        return is_on_time(self.created_at, self.date)


class EntryValue(models.Model):
    entry = models.ForeignKey(SadhanaEntry, on_delete=models.CASCADE, related_name="values")
    field = models.ForeignKey(SadhanaField, on_delete=models.PROTECT, related_name="values")
    value_int = models.PositiveIntegerField(null=True, blank=True)
    value_time = models.TimeField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    value_text = models.TextField(blank=True)

    class Meta:
        verbose_name = _("entry value")
        verbose_name_plural = _("entry values")
        constraints = [
            models.UniqueConstraint(fields=["entry", "field"], name="one_value_per_field_per_entry"),
        ]

    def __str__(self):
        return f"{self.field.key}={self.value}"

    @property
    def value(self):
        """The typed value for this field; None when nothing was entered."""
        field_type = self.field.field_type
        if self.field.is_numeric:
            return self.value_int
        if field_type == SadhanaField.FieldType.TIME:
            return self.value_time
        if field_type == SadhanaField.FieldType.BOOLEAN:
            return self.value_bool
        return self.value_text or None

    @value.setter
    def value(self, new):
        self.value_int = self.value_time = self.value_bool = None
        self.value_text = ""
        field_type = self.field.field_type
        if self.field.is_numeric:
            self.value_int = new
        elif field_type == SadhanaField.FieldType.TIME:
            self.value_time = new
        elif field_type == SadhanaField.FieldType.BOOLEAN:
            self.value_bool = new
        else:
            self.value_text = new or ""


class AppSettings(models.Model):
    """Singleton (id=1). Use AppSettings.load()."""

    edit_lock_enabled = models.BooleanField(_("edit lock enabled"), default=False)
    edit_window_days = models.PositiveIntegerField(_("edit window (days)"), default=7)
    backfill_limit_enabled = models.BooleanField(_("backfill limit enabled"), default=False)
    backfill_limit_days = models.PositiveIntegerField(_("backfill limit (days)"), default=7)
    day_rollover_hour = models.PositiveSmallIntegerField(_("day rollover hour"), default=4)
    site_title = models.CharField(_("site title"), max_length=100, default="Sadhana Report")

    class Meta:
        verbose_name = _("app settings")
        verbose_name_plural = _("app settings")

    def __str__(self):
        return self.site_title

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]
