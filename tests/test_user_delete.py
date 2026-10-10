from datetime import date

import pytest
from django.urls import reverse

from accounts.models import User
from audit import services as audit
from audit.models import AuditLog
from sadhana.models import EntryValue, SadhanaEntry, UserFieldSetting


def url(person):
    return reverse("manage_user_delete", args=[person.pk])


@pytest.fixture
def devotee(make_user, field):
    """A devotee with two entries, a field setting and an earlier audit row."""
    person = make_user(email="gopal@example.com", name="Gopal Sharma", spiritual_name="Govinda Das")
    for day in (1, 2):
        entry = SadhanaEntry.objects.create(user=person, date=date(2026, 10, day))
        EntryValue.objects.create(entry=entry, field=field("hearing"), value_int=30)
    UserFieldSetting.objects.create(user=person, field=field("day_rest"), enabled=True)
    audit.log(AuditLog.Action.ENTRY_CREATE, person, target_user=person, field_key="hearing", new_value=30)
    return person


def test_only_superusers_can_delete(client, user, devotee):
    client.force_login(user)
    assert client.get(url(devotee)).status_code == 403
    assert client.post(url(devotee), {"confirm_name": "Govinda Das"}).status_code == 403
    assert User.objects.filter(pk=devotee.pk).exists()


def test_warning_page_says_what_will_be_deleted(client, superuser, devotee):
    client.force_login(superuser)
    response = client.get(url(devotee))
    html = response.content.decode()
    assert response.status_code == 200 and response.context["entry_count"] == 2
    assert "This cannot be undone." in html
    assert "Govinda Das and all 2 sadhana entries will be permanently deleted." in html
    assert "mark them inactive instead" in html
    # Not a coordinator: no question about where their devotees go.
    assert "new_coordinator" not in response.context["form"].fields
    # A plain visit deletes nothing.
    assert User.objects.filter(pk=devotee.pk).exists()


def test_edit_page_links_to_delete_but_not_for_yourself(client, superuser, devotee):
    client.force_login(superuser)
    assert url(devotee) in client.get(reverse("manage_user_edit", args=[devotee.pk])).content.decode()
    assert url(superuser) not in client.get(reverse("manage_user_edit", args=[superuser.pk])).content.decode()


def test_name_must_be_typed_to_confirm(client, superuser, devotee):
    client.force_login(superuser)
    for typed in ("", "Gopal Sharma", "Govinda"):
        response = client.post(url(devotee), {"confirm_name": typed})
        assert response.status_code == 200 and response.context["form"].errors["confirm_name"]
    assert User.objects.filter(pk=devotee.pk).exists()
    assert not AuditLog.objects.filter(action="user_delete").exists()


def test_delete_removes_the_devotee_and_their_entries(client, superuser, devotee):
    client.force_login(superuser)
    response = client.post(url(devotee), {"confirm_name": "  govinda das "}, follow=True)  # case and spaces forgiven
    assert "Govinda Das has been deleted." in response.content.decode()
    assert not User.objects.filter(pk=devotee.pk).exists()
    assert not SadhanaEntry.objects.exists() and not EntryValue.objects.exists()
    assert not UserFieldSetting.objects.exists()

    # The log says who was deleted and by whom, as text, since the link to the user is gone.
    log = AuditLog.objects.get(action="user_delete")
    assert log.actor == superuser and log.target_user is None
    assert log.old_value == "Govinda Das <gopal@example.com>, 2 entries"
    # Earlier audit rows survive, without the person attached.
    earlier = AuditLog.objects.get(action="entry_create")
    assert earlier.actor is None and earlier.target_user is None and earlier.new_value == "30"


@pytest.fixture
def team(make_user):
    old = make_user(email="old@example.com", name="Old Coordinator", is_coordinator=True)
    new = make_user(email="new@example.com", name="New Coordinator", is_coordinator=True)
    plain = make_user(email="plain@example.com", name="Not A Coordinator")
    members = [make_user(email=f"m{number}@example.com", name=f"Member {number}", coordinator=old) for number in (1, 2)]
    return old, new, plain, members


def test_coordinator_page_lists_their_devotees_and_offers_other_coordinators(client, superuser, team):
    old, new, plain, members = team
    client.force_login(superuser)
    response = client.get(url(old))
    choices = list(response.context["form"].fields["new_coordinator"].queryset)
    assert choices == [new]  # only coordinators, and never the one being deleted
    html = response.content.decode()
    assert "2 devotees have this person as coordinator" in html
    assert "Member 1" in html and "Member 2" in html
    assert "— no coordinator —" in html


def test_deleting_a_coordinator_moves_their_devotees(client, superuser, team):
    old, new, _plain, members = team
    client.force_login(superuser)
    client.post(url(old), {"confirm_name": "Old Coordinator", "new_coordinator": new.pk})
    assert not User.objects.filter(pk=old.pk).exists()
    for member in members:
        member.refresh_from_db()
        assert member.coordinator == new
    moves = AuditLog.objects.filter(action="user_update", field_key="coordinator")
    assert {(log.target_user.name, log.old_value, log.new_value) for log in moves} == {
        ("Member 1", "Old Coordinator", "New Coordinator"),
        ("Member 2", "Old Coordinator", "New Coordinator"),
    }


def test_deleting_a_coordinator_can_leave_their_devotees_without_one(client, superuser, team):
    old, _new, _plain, members = team
    client.force_login(superuser)
    client.post(url(old), {"confirm_name": "Old Coordinator", "new_coordinator": ""})
    assert not User.objects.filter(pk=old.pk).exists()
    for member in members:
        member.refresh_from_db()
        assert member.coordinator is None
    assert {log.new_value for log in AuditLog.objects.filter(field_key="coordinator")} == {""}


def test_devotees_cannot_be_moved_to_someone_who_is_not_a_coordinator(client, superuser, team):
    old, _new, plain, members = team
    client.force_login(superuser)
    response = client.post(url(old), {"confirm_name": "Old Coordinator", "new_coordinator": plain.pk})
    assert response.status_code == 200 and response.context["form"].errors["new_coordinator"]
    assert User.objects.filter(pk=old.pk).exists()


def test_cannot_delete_yourself(client, superuser, make_user):
    make_user(email="second@example.com", name="Second", is_superuser=True)
    client.force_login(superuser)
    response = client.get(url(superuser))
    assert "cannot delete your own account" in response.content.decode()
    client.post(url(superuser), {"confirm_name": "Admin"})
    assert User.objects.filter(pk=superuser.pk).exists()


def test_another_superuser_can_be_deleted_but_never_the_last_one(client, superuser, make_user):
    second = make_user(email="second@example.com", name="Second", is_superuser=True)
    client.force_login(superuser)
    client.post(url(second), {"confirm_name": "Second"})
    assert not User.objects.filter(pk=second.pk).exists()
    assert User.objects.filter(is_superuser=True).count() == 1



def test_last_superuser_guard(superuser, make_user):
    from accounts.manage_views import _delete_blocked

    other = make_user(email="other@example.com", name="Other")
    assert _delete_blocked(superuser, other) is None
    assert "your own account" in str(_delete_blocked(superuser, superuser))
    # A hard-disabled superuser does not count as a remaining one.
    disabled = make_user(email="off@example.com", name="Disabled", is_superuser=True, is_active=False)
    assert "last superuser" in str(_delete_blocked(disabled, superuser))
    assert _delete_blocked(superuser, disabled) is None


def test_admin_still_has_no_delete(client, superuser, devotee):
    client.force_login(superuser)
    assert client.post(f"/admin/accounts/user/{devotee.pk}/delete/", {"post": "yes"}).status_code == 403
