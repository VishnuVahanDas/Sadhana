from django import forms

from .models import SadhanaField

FieldType = SadhanaField.FieldType


def build_form_field(field):
    common = {"label": field.label, "required": False, "help_text": field.help_text}
    if field.is_numeric:
        attrs = {"class": "input", "inputmode": "numeric", "placeholder": field.unit}
        return forms.IntegerField(
            min_value=field.effective_min,
            max_value=field.effective_max,
            widget=forms.NumberInput(attrs=attrs),
            **common,
        )
    if field.field_type == FieldType.TIME:
        return forms.TimeField(widget=forms.TimeInput(format="%H:%M", attrs={"class": "input", "type": "time"}), **common)
    if field.field_type == FieldType.BOOLEAN:
        return forms.BooleanField(widget=forms.CheckboxInput(attrs={"class": "checkbox"}), **common)
    return forms.CharField(widget=forms.Textarea(attrs={"class": "input", "rows": 3}), **common)


class EntryForm(forms.Form):
    """One input per sadhana field that is enabled for the entry's owner."""

    def __init__(self, *args, fields, entry=None, **kwargs):
        super().__init__(*args, **kwargs)
        current = {row.field_id: row.value for row in entry.values.select_related("field")} if entry else {}
        self.sadhana_fields = list(fields)
        for field in self.sadhana_fields:
            form_field = build_form_field(field)
            form_field.sadhana_field = field
            form_field.initial = current.get(field.id)
            self.fields[field.key] = form_field

    def values(self):
        """SadhanaField -> typed value, with None for anything left empty or unticked."""
        result = {}
        for field in self.sadhana_fields:
            value = self.cleaned_data.get(field.key)
            if field.field_type == FieldType.TEXT:
                value = (value or "").strip()
            if value == "" or value is False:
                value = None
            result[field] = value
        return result
