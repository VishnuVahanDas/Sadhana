import secrets

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import User

# No look-alike characters (0/o, 1/l/i), so it is easy to read out to a devotee.
PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def generate_password(user=None, length=10):
    while True:
        password = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))
        try:
            validate_password(password, user)
        except ValidationError:
            continue
        return password


class StyledFormMixin:
    """Give every widget the theme's input / checkbox class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "checkbox" if isinstance(field.widget, forms.CheckboxInput) else "input"
            field.widget.attrs.setdefault("class", css)


class EmailAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.EmailInput(
            attrs={"class": "input", "autofocus": True, "autocomplete": "email", "inputmode": "email"}
        )
        self.fields["password"].widget.attrs.update({"class": "input"})

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name")


class TemporaryPasswordMixin(forms.Form):
    temporary_password = forms.CharField(
        label=_("Temporary password"),
        required=False,
        help_text=_("Leave empty to generate one. The devotee must change it at first login."),
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    def clean_temporary_password(self):
        password = self.cleaned_data["temporary_password"].strip()
        if password:
            validate_password(password, getattr(self, "instance", None) or getattr(self, "user", None))
        return password


class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "email", "name", "spiritual_name", "phone",
            "coordinator", "is_coordinator", "is_participating", "is_superuser", "ui_mode",
        ]
        labels = {
            "is_coordinator": _("Is a coordinator (appears in the coordinator list)"),
            "is_participating": _("Active (shown in ranks and group analysis)"),
            "is_superuser": _("Superuser (can manage users, fields and settings)"),
        }
        help_texts = {
            "ui_mode": _("Simple hides the streaks. Advanced also shows them on Today and My Report."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = Q(is_coordinator=True)
        if self.instance.pk:
            if self.instance.coordinator_id:
                choices |= Q(pk=self.instance.coordinator_id)
            self.fields["coordinator"].queryset = User.objects.filter(choices).exclude(pk=self.instance.pk)
        else:
            self.fields["coordinator"].queryset = User.objects.filter(choices)
        self.fields["coordinator"].empty_label = _("— none —")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("A user with this email already exists."))
        return email


class UserCreateForm(TemporaryPasswordMixin, UserForm):
    def save(self):
        """Create the user. Returns (user, temporary password)."""
        user = super().save(commit=False)
        password = self.cleaned_data["temporary_password"] or generate_password(user)
        user.set_password(password)
        user.must_change_password = True
        user.save()
        return user, password


class PasswordResetForm(StyledFormMixin, TemporaryPasswordMixin):
    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def save(self):
        """Set a temporary password and force a change at next login. Returns the password."""
        password = self.cleaned_data["temporary_password"] or generate_password(self.user)
        self.user.set_password(password)
        self.user.must_change_password = True
        self.user.save(update_fields=["password", "must_change_password"])
        return password


class UserDeleteForm(StyledFormMixin, forms.Form):
    """Confirmation for permanently deleting a devotee.

    If they coordinate anyone, `new_coordinator` says who takes over their team
    (empty = nobody). Typing the name guards against a slip of the thumb.
    """

    new_coordinator = forms.ModelChoiceField(
        label=_("Move their devotees to"),
        queryset=User.objects.none(),
        required=False,
        empty_label=_("— no coordinator —"),
    )
    confirm_name = forms.CharField(label=_("Type the devotee's name to confirm"))

    def __init__(self, *args, target, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = target
        if target.team_members.exists():
            self.fields["new_coordinator"].queryset = User.objects.filter(is_coordinator=True).exclude(pk=target.pk)
        else:
            del self.fields["new_coordinator"]
        self.fields["confirm_name"].widget.attrs.update({"autocomplete": "off", "autocapitalize": "off"})

    def clean_confirm_name(self):
        typed = self.cleaned_data["confirm_name"].strip()
        if typed.casefold() != self.target.display_name.strip().casefold():
            raise ValidationError(
                _("That does not match. Type “%(name)s” to confirm.") % {"name": self.target.display_name}
            )
        return typed
