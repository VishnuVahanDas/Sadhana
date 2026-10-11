from django.db import migrations

# min_rounds, name, icon, description
VEHICLES = [
    (0, "Padayatra", "walking", "Walking — every step counts"),
    (4, "Cycle", "cycle", ""),
    (8, "Bike", "bike", ""),
    (12, "Three-wheeler", "three_wheeler", ""),
    (16, "Car", "car", ""),
    (32, "Train", "train", ""),
    (48, "Airplane", "airplane", ""),
    (64, "Vaikuntha Vimāna", "vimana", ""),
]

# min_minutes, label, diya_count, is_full_flame
UTSAHA = [
    (0, "No lamp yet", 0, False),
    (1, "One diya", 1, False),
    (30, "Two diyas", 2, False),
    (60, "Three diyas", 3, False),
    (120, "Full flame", 4, True),
]


def seed(apps, schema_editor):
    """Only fills empty tables, so running it again never touches levels a superuser has edited."""
    VehicleLevel = apps.get_model("sadhana", "VehicleLevel")
    UtsahaLevel = apps.get_model("sadhana", "UtsahaLevel")
    if not VehicleLevel.objects.exists():
        VehicleLevel.objects.bulk_create(
            VehicleLevel(min_rounds=rounds, name=name, icon=icon, description=description, order=position * 10)
            for position, (rounds, name, icon, description) in enumerate(VEHICLES, 1)
        )
    if not UtsahaLevel.objects.exists():
        UtsahaLevel.objects.bulk_create(
            UtsahaLevel(min_minutes=minutes, label=label, diya_count=diyas, is_full_flame=full)
            for minutes, label, diyas, full in UTSAHA
        )


class Migration(migrations.Migration):
    dependencies = [("sadhana", "0008_bhakti_yatra")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
