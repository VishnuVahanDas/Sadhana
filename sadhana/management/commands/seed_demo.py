"""Create (or remove) demo devotees dev1..dev15 with varied sadhana history, for trying out the reports.

    python manage.py seed_demo            # create the demo users and about 60 days of entries
    python manage.py seed_demo --delete   # remove the demo users and everything they entered
"""

import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.forms import generate_password
from accounts.models import User
from sadhana.models import EntryValue, SadhanaEntry, SadhanaField, UserFieldSetting

DOMAIN = "demo.local"
COUNT = 15
DAYS = 60

# (how often they fill, typical hearing / reading / seva minutes, usual rounds, how often they enter late)
PROFILES = [
    (0.98, 60, 45, 90, 16, 0.02),  # dev1  steady coordinator
    (0.95, 45, 30, 120, 16, 0.05),  # dev2  coordinator, lots of seva
    (0.90, 30, 60, 60, 16, 0.10),  # dev3  coordinator, reader
    (0.97, 90, 30, 30, 16, 0.00),  # dev4  long unbroken streaks
    (0.85, 40, 20, 45, 16, 0.30),  # dev5  fills well but often late
    (0.75, 30, 30, 30, 12, 0.10),
    (0.70, 20, 15, 60, 8, 0.20),
    (0.65, 45, 0, 30, 16, 0.10),  # dev8  never reads
    (0.60, 15, 10, 20, 4, 0.40),
    (0.55, 30, 20, 0, 8, 0.15),  # dev10 no seva
    (0.50, 25, 25, 25, 16, 0.50),  # dev11 mostly backfills
    (0.40, 20, 10, 15, 4, 0.20),
    (0.30, 15, 5, 10, 2, 0.30),  # dev13 irregular
    (0.90, 60, 40, 60, 16, 0.05),  # dev14 joined recently
    (0.80, 30, 30, 30, 16, 0.10),  # dev15 inactive
]
NOTES = [
    "Good hearing today.", "Attended the morning class.", "Chanted attentively.", "Busy day at work.",
    "Kirtan in the evening.", "Read Bhagavad-gita chapter 2.", "Travelling.", "Book distribution seva.",
]


class Command(BaseCommand):
    help = "Create or delete demo devotees dev1..dev15 with sample sadhana entries."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Remove the demo users and their entries.")

    def handle(self, *args, **options):
        demo = User.objects.filter(email__endswith=f"@{DOMAIN}")
        if options["delete"]:
            count = demo.count()
            demo.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} demo users and their entries."))
            return
        if demo.exists():
            raise CommandError("Demo users already exist. Run with --delete first.")
        password = generate_password()
        with transaction.atomic():
            users = self.create_users(password)
            entries, values = self.create_entries(users)
        self.stdout.write(self.style.SUCCESS(f"Created {len(users)} demo users, {entries} entries, {values} values."))
        self.stdout.write(f"Login: dev1@{DOMAIN} … dev{COUNT}@{DOMAIN}   password: {password}")

    def create_users(self, password):
        now = timezone.now()
        users = []
        for number in range(1, COUNT + 1):
            user = User(
                email=f"dev{number}@{DOMAIN}",
                name=f"dev{number}",
                is_coordinator=number <= 3,
                is_participating=number != 15,
                must_change_password=False,
                date_joined=now - timedelta(days=20 if number == 14 else DAYS),
            )
            user.set_password(password)
            user.save()
            users.append(user)
        # dev4-dev13 are spread over the three coordinators; dev14 and dev15 have none.
        for index, user in enumerate(users[3:13]):
            user.coordinator = users[index % 3]
            user.save(update_fields=["coordinator"])
        # A few devotees also track Mangala Arati and wake-up time.
        extras = SadhanaField.objects.filter(key__in=["mangala_arati", "wake_up_time"])
        for user in (users[0], users[3], users[5], users[8]):
            for field in extras:
                UserFieldSetting.objects.create(user=user, field=field, enabled=True)
        return users

    def create_entries(self, users):
        rng = random.Random(108)
        fields = {field.key: field for field in SadhanaField.objects.all()}
        now = timezone.now()
        today = timezone.localdate()
        zone = timezone.get_current_timezone()
        entry_count = value_count = 0

        for user, (fill, hearing, reading, seva, rounds, late) in zip(users, PROFILES):
            has_extras = UserFieldSetting.objects.filter(user=user).exists()
            first_day = max(timezone.localdate(user.date_joined), today - timedelta(days=DAYS - 1))
            stamps, rows = {}, []
            day = first_day
            while day <= today:
                # About half of them have not filled today yet.
                chance = fill * 0.5 if day == today else fill
                if rng.random() < chance:
                    entered_late = day < today - timedelta(days=1) and rng.random() < late
                    entered = day + timedelta(days=rng.randint(2, 6) if entered_late else rng.randint(0, 1))
                    stamp = datetime.combine(entered, time(rng.randint(6, 22), rng.randint(0, 59)), tzinfo=zone)
                    stamps[day] = min(stamp, now)
                    rows.append((day, self.day_values(rng, hearing, reading, seva, rounds, has_extras)))
                day += timedelta(days=1)

            created = SadhanaEntry.objects.bulk_create(
                [SadhanaEntry(user=user, date=day, created_by=user, updated_by=user) for day, _ in rows]
            )
            # auto_now_add always stamps "now", so set the real entry times afterwards.
            for entry in created:
                SadhanaEntry.objects.filter(pk=entry.pk).update(created_at=stamps[entry.date], updated_at=stamps[entry.date])
            values = []
            for entry, (_, day_values) in zip(created, rows):
                for key, value in day_values.items():
                    row = EntryValue(entry=entry, field=fields[key])
                    row.value = value
                    values.append(row)
            EntryValue.objects.bulk_create(values)
            entry_count += len(created)
            value_count += len(values)
        return entry_count, value_count

    def day_values(self, rng, hearing, reading, seva, rounds, has_extras):
        """One day's values around the devotee's typical numbers; some fields are skipped on some days."""
        values = {}
        for key, typical in (("hearing", hearing), ("reading", reading), ("seva", seva)):
            if typical and rng.random() < 0.85:
                minutes = max(0, round(rng.gauss(typical, typical * 0.35) / 5) * 5)
                values[key] = minutes
        if rng.random() < 0.95:
            values["rounds"] = max(0, min(rounds + rng.choice([0, 0, 0, 0, -4, -8, 2]), 64))
        if rng.random() < 0.2:
            values["notes"] = rng.choice(NOTES)
        if has_extras:
            if rng.random() < 0.6:
                values["mangala_arati"] = True
            values["wake_up_time"] = time(rng.choice([3, 4, 4, 4, 5, 5, 6]), rng.choice([0, 15, 30, 45]))
        return values
