import pytest
from django.db import IntegrityError

from accounts.models import User


def test_display_name_prefers_spiritual_name(make_user):
    user = make_user(name="Gopal Sharma", spiritual_name="Govinda Das")
    assert user.display_name == "Govinda Das"
    assert str(user) == "Govinda Das"


def test_display_name_falls_back_to_name(make_user):
    assert make_user(name="Gopal Sharma").display_name == "Gopal Sharma"


def test_new_user_defaults(db):
    user = User.objects.create_user(email="new@example.com", password="x", name="New")
    assert user.must_change_password is True
    assert user.is_participating is True
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.is_staff is False
    assert user.coordinator is None


def test_email_is_lowercased_and_unique(make_user):
    user = make_user(email="  Devotee@Example.COM ")
    assert user.email == "devotee@example.com"
    with pytest.raises(IntegrityError):
        make_user(email="DEVOTEE@example.com")


def test_email_is_required(db):
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x", name="No Email")


def test_is_staff_mirrors_is_superuser(make_user):
    user = make_user()
    user.is_superuser = True
    user.save()
    assert user.is_staff is True
    user.is_superuser = False
    user.save()
    assert user.is_staff is False


def test_create_superuser(db):
    admin = User.objects.create_superuser(email="admin@example.com", password="x", name="Admin")
    assert admin.is_superuser and admin.is_staff
    assert admin.must_change_password is False


def test_deleting_coordinator_keeps_team_members(make_user):
    coordinator = make_user(email="coord@example.com", is_coordinator=True)
    member = make_user(email="member@example.com", coordinator=coordinator)
    assert list(coordinator.team_members.all()) == [member]
    coordinator.delete()
    member.refresh_from_db()
    assert member.coordinator is None
