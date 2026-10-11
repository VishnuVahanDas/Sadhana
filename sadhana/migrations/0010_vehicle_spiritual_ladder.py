from django.db import migrations

# min_rounds -> (name, icon, description). Rows are matched by min_rounds; thresholds are never changed,
# and no row is added or deleted.
NEW = {
    0: ("Padayātrī", "padayatri", "On foot, like pilgrims on Braj parikrama — every step counts"),
    4: ("Bail-gāḍī", "bail_gadi", "The simple Braj bullock cart on the village path of Vrindavan"),
    8: ("Naukā", "nauka", "A boat on the Yamunā — chanting begins to carry you across"),
    12: ("Pālkī", "palki", "A palanquin, carried with care and dignity"),
    16: ("Ratha", "ratha", "A chariot, like Arjuna's with Krishna as charioteer — the 16-round standard"),
    32: ("Haṁsa", "hamsa", "The swan — like the paramahaṁsa, taking the essence and leaving the rest"),
    48: ("Puṣpaka Vimāna", "pushpaka", "The flower-chariot of the Rāmāyaṇa, flying beyond earthly roads"),
    64: ("Vaikuṇṭha Vimāna", "vaikuntha", "The vehicle of the spiritual world"),
}

# What 0009 seeded, restored when this migration is reversed.
OLD = {
    0: ("Padayatra", "walking", "Walking — every step counts"),
    4: ("Cycle", "cycle", ""),
    8: ("Bike", "bike", ""),
    12: ("Three-wheeler", "three_wheeler", ""),
    16: ("Car", "car", ""),
    32: ("Train", "train", ""),
    48: ("Airplane", "airplane", ""),
    64: ("Vaikuntha Vimāna", "vimana", ""),
}


def _apply(apps, values):
    VehicleLevel = apps.get_model("sadhana", "VehicleLevel")
    for min_rounds, (name, icon, description) in values.items():
        VehicleLevel.objects.filter(min_rounds=min_rounds).update(name=name, icon=icon, description=description)


def forwards(apps, schema_editor):
    _apply(apps, NEW)


def backwards(apps, schema_editor):
    _apply(apps, OLD)


class Migration(migrations.Migration):
    dependencies = [("sadhana", "0009_seed_yatra_levels")]

    operations = [migrations.RunPython(forwards, backwards)]
