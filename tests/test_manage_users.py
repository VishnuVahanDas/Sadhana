import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog

from .conftest import PASSWORD

FORM = {"email": "new@example.com", "name": "Gopal Sharma", "spiritual_name": "", "phone": "", "coordinator": ""}


def edit_data(user, **changes):
    data = {
        "email": user.email, "name": user.name, "spiritual_name": user.spiritual_name, "phone": user.phone,
        "coordinator": user.coordinator_id or "",
    }
    for flag in ("is_coordinator", "is_participating", "is_superuser"):
        if getattr(user, flag):
            data[flag] = "on"
    for key, value in changes.items():
        if value is False:
            data.pop(key, None)
        else:
            data[key] = "on" if value is True else value
    return data


def manage_urls(user):
    return [
        reverse("manage_users"), reverse("manage_user_add"), reverse("manage_user_edit", args=[user.pk]),
        reverse("manage_user_password", args=[user.pk]), reverse("manage_user_fields", args=[user.pk]),
        reverse("manage_fields"), reverse("manage_field_add"), reverse("manage_settings"), reverse("manage_audit"),
    ]


def test_manage_pages_are_superuser_only(client, user, superuser):
    client.force_login(user)
    for path in manage_urls(user):
        assert client.get(path).status_code == 403, path
        assert client.post(path, {}).status_code == 403, path
    client.force_login(superuser)
    for path in manage_urls(user):
        assert client.get(path).status_code == 200, path


def test_manage_pages_require_login(client, user):
    assert client.get(reverse("manage_users")).status_code == 302


def test_create_user_with_generated_password(client, superuser):
    client.force_login(superuser)
    response = client.post(reverse("manage_user_add"), {**FORM, "email": " New@Example.com ", "is_participating": "on"})
    assert response.status_code == 200
    password = response.context["password"]
    assert len(password) == 10 and password in response.content.decode()

    new = User.objects.get(email="new@example.com")
    assert new.must_change_password is True and new.is_participating is True and new.is_superuser is False
    assert new.check_password(password)
    log = AuditLog.objects.get(action="user_create")
    assert (log.actor, log.target_user, log.new_value) == (superuser, new, "new@example.com")
    assert password not in "".join(f"{row.old_value}{row.new_value}" for row in AuditLog.objects.all())

    # The devotee can log in with it and is sent to change it.
    client.logout()
    response = client.post(reverse("login"), {"username": "new@example.com", "password": password}, follow=True)
    assert response.redirect_chain[-1][0] == reverse("password_change")


def test_create_user_with_chosen_password(client, superuser):
    client.force_login(superuser)
    response = client.post(reverse("manage_user_add"), {**FORM, "temporary_password": "radhe-shyam-2026"})
    assert response.context["password"] == "radhe-shyam-2026"
    assert User.objects.get(email="new@example.com").check_password("radhe-shyam-2026")


def test_weak_or_duplicate_input_is_rejected(client, superuser, user):
    client.force_login(superuser)
    response = client.post(reverse("manage_user_add"), {**FORM, "temporary_password": "12345"})
    assert response.context["form"].errors["temporary_password"]
    response = client.post(reverse("manage_user_add"), {**FORM, "email": user.email.upper()})
    assert response.context["form"].errors["email"]
    assert User.objects.count() == 2


def test_edit_user_audits_each_changed_field(client, superuser, user, make_user):
    coordinator = make_user(email="coord@example.com", name="Coord", spiritual_name="Madhava Das", is_coordinator=True)
    client.force_login(superuser)
    response = client.post(
        reverse("manage_user_edit", args=[user.pk]),
        edit_data(user, spiritual_name="Govinda Das", coordinator=coordinator.pk),
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.display_name == "Govinda Das" and user.coordinator == coordinator
    logs = AuditLog.objects.filter(target_user=user)
    assert {(log.action, log.field_key, log.old_value, log.new_value) for log in logs} == {
        ("user_update", "spiritual_name", "", "Govinda Das"),
        ("user_update", "coordinator", "", "Madhava Das"),
    }


def test_coordinator_dropdown_lists_only_coordinators(client, superuser, user, make_user):
    coordinator = make_user(email="coord@example.com", is_coordinator=True)
    client.force_login(superuser)
    choices = client.get(reverse("manage_user_edit", args=[user.pk])).context["form"].fields["coordinator"].queryset
    assert list(choices) == [coordinator]
    # Nobody can be their own coordinator.
    own = client.get(reverse("manage_user_edit", args=[coordinator.pk])).context["form"].fields["coordinator"].queryset
    assert coordinator not in own


def test_deactivate_and_reactivate(client, superuser, user):
    client.force_login(superuser)
    edit = reverse("manage_user_edit", args=[user.pk])
    client.post(edit, edit_data(user, is_participating=False))
    user.refresh_from_db()
    assert user.is_participating is False and user.is_active is True
    client.post(edit, edit_data(user, is_participating=True))
    assert [log.action for log in AuditLog.objects.order_by("id")] == ["user_deactivate", "user_reactivate"]
    # Inactive users can still log in.
    user.is_participating = False
    user.save()
    client.logout()
    assert client.post(reverse("login"), {"username": user.email, "password": PASSWORD}).status_code == 302


def test_grant_and_revoke_superuser(client, superuser, user):
    client.force_login(superuser)
    edit = reverse("manage_user_edit", args=[user.pk])
    client.post(edit, edit_data(user, is_superuser=True))
    user.refresh_from_db()
    assert user.is_superuser and user.is_staff
    client.post(edit, edit_data(user, is_superuser=False))
    user.refresh_from_db()
    assert not user.is_superuser and not user.is_staff
    assert [log.action for log in AuditLog.objects.order_by("id")] == ["superuser_grant", "superuser_revoke"]


def test_last_superuser_cannot_be_demoted(client, superuser):
    client.force_login(superuser)
    edit = reverse("manage_user_edit", args=[superuser.pk])
    response = client.post(edit, edit_data(superuser, is_superuser=False))
    assert response.status_code == 200
    assert "last superuser" in response.content.decode()
    superuser.refresh_from_db()
    assert superuser.is_superuser
    assert not AuditLog.objects.exists()


def test_superuser_can_be_demoted_when_another_exists(client, superuser, make_user):
    make_user(email="second@example.com", is_superuser=True)
    client.force_login(superuser)
    response = client.post(reverse("manage_user_edit", args=[superuser.pk]), edit_data(superuser, is_superuser=False))
    assert response.status_code == 302
    superuser.refresh_from_db()
    assert not superuser.is_superuser


def test_last_superuser_rule_also_covers_admin_and_hard_disable(superuser, make_user):
    superuser.is_active = False
    with pytest.raises(ValidationError):
        superuser.full_clean()
    superuser.is_active = True
    # A hard-disabled superuser does not count as a remaining one.
    make_user(email="disabled@example.com", is_superuser=True, is_active=False)
    superuser.is_superuser = False
    with pytest.raises(ValidationError):
        superuser.full_clean()


def test_users_cannot_be_deleted_in_admin(client, superuser, user):
    client.force_login(superuser)
    assert client.post(f"/admin/accounts/user/{user.pk}/delete/", {"post": "yes"}).status_code == 403
    assert User.objects.filter(pk=user.pk).exists()


def test_reset_password(client, superuser, user):
    client.force_login(superuser)
    response = client.post(reverse("manage_user_password", args=[user.pk]), {"temporary_password": ""})
    password = response.context["password"]
    user.refresh_from_db()
    assert user.check_password(password) and not user.check_password(PASSWORD)
    assert user.must_change_password is True
    log = AuditLog.objects.get()
    assert (log.action, log.actor, log.target_user, log.old_value, log.new_value) == ("password_reset", superuser, user, "", "")


def test_user_list_shows_everyone_with_email(client, superuser, user):
    client.force_login(superuser)
    html = client.get(reverse("manage_users")).content.decode()
    assert user.email in html and superuser.email in html
