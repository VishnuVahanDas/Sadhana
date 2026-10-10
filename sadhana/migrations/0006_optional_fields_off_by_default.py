from django.db import migrations


def optional_fields_off_by_default(apps, schema_editor):
    """New devotees start with the core fields only; optional fields are assigned to them afterwards.

    Devotees who have an optional field today because it was on by default keep it: they get their
    own "on" setting before the default is switched off.
    """
    SadhanaField = apps.get_model("sadhana", "SadhanaField")
    UserFieldSetting = apps.get_model("sadhana", "UserFieldSetting")
    User = apps.get_model("accounts", "User")
    for field in SadhanaField.objects.filter(is_core=False, enabled_by_default=True):
        decided = UserFieldSetting.objects.filter(field=field).values_list("user_id", flat=True)
        UserFieldSetting.objects.bulk_create(
            UserFieldSetting(user=user, field=field, enabled=True) for user in User.objects.exclude(pk__in=decided)
        )
        field.enabled_by_default = False
        field.save(update_fields=["enabled_by_default"])


class Migration(migrations.Migration):
    dependencies = [
        ("sadhana", "0005_seed_field_targets"),
        ("accounts", "0002_user_theme"),
    ]

    operations = [migrations.RunPython(optional_fields_off_by_default, migrations.RunPython.noop)]
