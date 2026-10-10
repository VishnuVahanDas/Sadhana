from django.db import migrations


def seed(apps, schema_editor):
    # 16 rounds is the standard daily vow; charts for Rounds never zoom in closer than that.
    apps.get_model("sadhana", "SadhanaField").objects.filter(key="rounds", target__isnull=True).update(target=16)


class Migration(migrations.Migration):
    dependencies = [("sadhana", "0004_festivals_and_field_target")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
