from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.EmailInput(
            attrs={"class": "input", "autofocus": True, "autocomplete": "email", "inputmode": "email"}
        )
        self.fields["password"].widget.attrs.update({"class": "input"})

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "input"})


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name")
