from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from accounts.forms import StyledFormMixin

from .models import AuditLog


class AuditFilterForm(StyledFormMixin, forms.Form):
    user = forms.ModelChoiceField(
        label=_("Devotee"), queryset=get_user_model().objects.all(), required=False, empty_label=_("Everyone")
    )
    action = forms.ChoiceField(
        label=_("Action"), choices=[("", _("All actions"))] + AuditLog.Action.choices, required=False
    )
    date_from = forms.DateField(label=_("From"), required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label=_("To"), required=False, widget=forms.DateInput(attrs={"type": "date"}))
