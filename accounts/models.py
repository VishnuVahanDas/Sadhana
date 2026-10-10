from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email address must be set")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_superuser"] = True
        # The person running createsuperuser has just chosen this password.
        extra_fields.setdefault("must_change_password", False)
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        # Login is case-insensitive.
        return self.get(email__iexact=email)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email"), unique=True)
    name = models.CharField(_("name"), max_length=150)
    spiritual_name = models.CharField(_("spiritual name"), max_length=150, blank=True)
    phone = models.CharField(_("phone"), max_length=20, blank=True)
    coordinator = models.ForeignKey(
        "self",
        verbose_name=_("coordinator"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_members",
    )
    is_coordinator = models.BooleanField(_("is a coordinator"), default=False)
    # "Active/Inactive" in the UI. Inactive users can still log in.
    is_participating = models.BooleanField(_("participating"), default=True)
    is_staff = models.BooleanField(_("staff"), default=False, editable=False)
    # Django's login flag: keep True; only for an emergency hard-disable.
    is_active = models.BooleanField(_("can log in"), default=True)
    must_change_password = models.BooleanField(_("must change password"), default=True)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["name"]

    def __str__(self):
        return self.display_name

    def clean(self):
        super().clean()
        # Never leave the system without a superuser who can log in.
        if self.pk and not (self.is_superuser and self.is_active):
            superusers = User.objects.filter(is_superuser=True, is_active=True)
            if superusers.filter(pk=self.pk).exists() and not superusers.exclude(pk=self.pk).exists():
                raise ValidationError(_("This is the last superuser. Make someone else a superuser first."))

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        # is_staff mirrors is_superuser so superusers can use /admin/ as a backup.
        self.is_staff = self.is_superuser
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.spiritual_name or self.name
