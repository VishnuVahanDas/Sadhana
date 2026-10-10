import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from sadhana.models import EntryValue, SadhanaEntry


def test_seed_demo_creates_and_deletes(user, capsys):
    call_command("seed_demo")
    demo = User.objects.filter(email__endswith="@demo.local")
    assert demo.count() == 15
    assert demo.filter(is_participating=False).count() == 1
    assert demo.filter(is_coordinator=True).count() == 3
    assert demo.filter(coordinator__isnull=False).count() == 10
    assert not demo.filter(is_superuser=True).exists()
    assert "password:" in capsys.readouterr().out

    entries = SadhanaEntry.objects.filter(user__in=demo)
    assert entries.count() > 300
    assert not entries.filter(date__gt=timezone.localdate()).exists()
    assert not entries.filter(created_at__gt=timezone.now()).exists()
    on_time = [entry.is_on_time for entry in entries]
    assert any(on_time) and not all(on_time)
    assert EntryValue.objects.filter(value_bool=True).exists()
    assert not AuditLog.objects.exists()

    with pytest.raises(CommandError):
        call_command("seed_demo")

    call_command("seed_demo", "--delete")
    assert list(User.objects.all()) == [user]
    assert not SadhanaEntry.objects.exists() and not EntryValue.objects.exists()
