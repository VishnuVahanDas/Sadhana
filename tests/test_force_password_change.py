import pytest
from django.urls import reverse

from .conftest import PASSWORD

NEW_PASSWORD = "govinda-jaya-jaya-16"


@pytest.fixture
def new_user(make_user):
    return make_user(must_change_password=True)


@pytest.mark.parametrize("path", ["/", "/me/", "/ranks/", "/analysis/", "/devotees/", "/admin/"])
def test_every_page_redirects_to_password_change(client, new_user, path):
    client.force_login(new_user)
    response = client.get(path)
    assert response.status_code == 302
    assert response.url == reverse("password_change")


def test_first_login_lands_on_password_change(client, new_user):
    response = client.post(reverse("login"), {"username": new_user.email, "password": PASSWORD}, follow=True)
    assert response.redirect_chain[-1][0] == reverse("password_change")
    html = response.content.decode()
    assert "choose your own password" in html
    assert "<nav" not in html


def test_can_log_out_without_changing_password(client, new_user):
    client.force_login(new_user)
    assert client.post(reverse("logout")).url == reverse("login")


def test_changing_password_clears_the_flag(client, new_user):
    client.force_login(new_user)
    response = client.post(
        reverse("password_change"),
        {"old_password": PASSWORD, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    assert response.url == reverse("home")
    new_user.refresh_from_db()
    assert new_user.must_change_password is False
    assert new_user.check_password(NEW_PASSWORD)
    # Still logged in, and no longer redirected.
    assert client.get(reverse("home")).status_code == 200


def test_weak_password_is_rejected(client, new_user):
    client.force_login(new_user)
    response = client.post(
        reverse("password_change"),
        {"old_password": PASSWORD, "new_password1": "12345678", "new_password2": "12345678"},
    )
    assert response.status_code == 200
    new_user.refresh_from_db()
    assert new_user.must_change_password is True


def test_voluntary_password_change(client, user):
    client.force_login(user)
    assert client.get(reverse("password_change")).status_code == 200
    client.post(
        reverse("password_change"),
        {"old_password": PASSWORD, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
