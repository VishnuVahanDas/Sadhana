from django.db import migrations

# key, label, type, unit, has_streak, is_rankable, is_core, enabled_by_default  (SPEC §4.2)
FIELDS = [
    ("hearing", "Hearing", "minutes", "min", True, True, True, True),
    ("reading", "Book Reading", "minutes", "min", True, True, True, True),
    ("seva", "Seva", "minutes", "min", True, True, True, True),
    ("rounds", "Rounds", "count", "rounds", False, True, True, True),
    ("notes", "Notes / Realizations", "text", "", False, False, True, True),
    ("wake_up_time", "Wake-up Time", "time", "", False, False, False, False),
    ("sleep_time", "Sleep Time", "time", "", False, False, False, False),
    ("mangala_arati", "Mangala Arati", "boolean", "", True, True, False, False),
    ("day_rest", "Day Rest", "minutes", "min", False, False, False, False),
]


def seed(apps, schema_editor):
    SadhanaField = apps.get_model("sadhana", "SadhanaField")
    AppSettings = apps.get_model("sadhana", "AppSettings")
    for position, (key, label, field_type, unit, has_streak, is_rankable, is_core, default_on) in enumerate(FIELDS, 1):
        numeric = field_type in ("minutes", "count")
        SadhanaField.objects.get_or_create(
            key=key,
            defaults={
                "label": label,
                "field_type": field_type,
                "unit": unit,
                "min_value": 0 if numeric else None,
                "max_value": 1440 if field_type == "minutes" else None,
                "has_streak": has_streak,
                "is_rankable": is_rankable,
                "is_core": is_core,
                "is_active": True,
                "enabled_by_default": default_on,
                "order": position * 10,
            },
        )
    AppSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("sadhana", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
