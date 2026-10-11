from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.forms import StyledFormMixin

from . import themes
from .models import AppSettings, Festival, SadhanaField, UtsahaLevel, VehicleLevel

FieldType = SadhanaField.FieldType
MEASURABLE = (FieldType.MINUTES, FieldType.COUNT, FieldType.BOOLEAN)


class SadhanaFieldForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SadhanaField
        fields = [
            "label", "key", "field_type", "unit", "min_value", "max_value",
            "has_streak", "is_rankable", "is_active", "enabled_by_default", "help_text", "target",
        ]
        labels = {
            "has_streak": _("Count streaks for this field"),
            "is_rankable": _("Show totals, chart and calendar on My Report (ranks and analysis use the core fields only)"),
            "is_active": _("Active (inactive fields are hidden from all forms; history is kept)"),
            "enabled_by_default": _("On by default for new users and users without their own setting"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Stored values depend on these two, so they are fixed once the field exists.
            self.fields["key"].disabled = True
            self.fields["field_type"].disabled = True
        else:
            # New fields are optional: nobody gets one until it is assigned or switched on for all users.
            self.fields["enabled_by_default"].initial = False

    def clean(self):
        cleaned = super().clean()
        field_type = cleaned.get("field_type")
        if field_type and field_type not in MEASURABLE:
            for name in ("has_streak", "is_rankable"):
                if cleaned.get(name):
                    self.add_error(name, _("Only minutes, count and yes/no fields can have streaks or ranks."))
        low, high = cleaned.get("min_value"), cleaned.get("max_value")
        if low is not None and low < 0:
            self.add_error("min_value", _("The minimum cannot be negative."))
        if low is not None and high is not None and low > high:
            self.add_error("max_value", _("The maximum must not be smaller than the minimum."))
        return cleaned


class AppSettingsForm(StyledFormMixin, forms.ModelForm):
    theme = forms.ChoiceField(
        label=_("Default theme"),
        choices=themes.CHOICES,
        help_text=_("Used on the login page and for devotees who have not picked their own theme."),
    )

    class Meta:
        model = AppSettings
        fields = [
            "site_title", "theme", "day_rollover_hour",
            "edit_lock_enabled", "edit_window_days",
            "backfill_limit_enabled", "backfill_limit_days",
            "rank_table_enabled",
        ]
        labels = {
            "rank_table_enabled": _("Rank table: show it again (for special events); otherwise Ranks opens Sanga Yatra"),
            "edit_lock_enabled": _("Edit lock: users cannot change entries older than the edit window"),
            "backfill_limit_enabled": _("Backfill limit: users cannot add entries older than the limit"),
        }
        help_texts = {
            "day_rollover_hour": _("Before this hour (IST) the entry form opens on yesterday."),
        }

    def clean_day_rollover_hour(self):
        hour = self.cleaned_data["day_rollover_hour"]
        if hour > 23:
            raise ValidationError(_("Enter an hour between 0 and 23."))
        return hour


class FestivalForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Festival
        fields = ["name", "start_date", "end_date", "notes"]
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", _("The end date cannot be before the start date."))
        return cleaned


class _LevelForm(StyledFormMixin, forms.ModelForm):
    """A Bhakti Yatra level. The lowest level starts at 0 and stays there, so every devotee has a level."""

    threshold = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self.instance, self.threshold) == 0:
            self.fields[self.threshold].disabled = True
            self.fields[self.threshold].help_text = _("The first level always starts at 0.")


class VehicleLevelForm(_LevelForm):
    threshold = "min_rounds"
    icon = forms.ChoiceField(label=_("Icon"), choices=VehicleLevel.ICONS)

    class Meta:
        model = VehicleLevel
        fields = ["name", "min_rounds", "icon", "description"]
        help_texts = {"min_rounds": _("A devotee travels at this Yatra level from this 7-day average of rounds upwards.")}


class UtsahaLevelForm(_LevelForm):
    threshold = "min_minutes"

    class Meta:
        model = UtsahaLevel
        fields = ["label", "min_minutes", "diya_count", "is_full_flame"]
        help_texts = {"min_minutes": _("Minutes of hearing, reading and seva in a day, from which this level applies.")}
