import pytest
from django.urls import reverse

from .conftest import PASSWORD

PROTECTED = ["home", "me", "ranks", "analysis", "devotees", "password_change"]


@pytest.mark.parametrize("name", PROTECTED)
def test_pages_require_login(client, db, name):
    url = reverse(name)
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={url}"


def test_admin_requires_login(client, db):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "login" in response.url


def test_login_page_is_public_and_has_no_nav(client, db):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "Hare Krishna" in response.content.decode()
    assert "<nav" not in response.content.decode()


def test_login_with_email(client, user):
    response = client.post(reverse("login"), {"username": user.email, "password": PASSWORD})
    assert response.status_code == 302
    assert response.url == reverse("home")
    assert client.get(reverse("home")).status_code == 200


def test_login_is_case_insensitive(client, user):
    response = client.post(reverse("login"), {"username": " DEVOTEE@Example.com ", "password": PASSWORD})
    assert response.status_code == 302


def test_login_wrong_password(client, user):
    response = client.post(reverse("login"), {"username": user.email, "password": "wrong"})
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()


def test_hard_disabled_user_cannot_log_in(client, make_user):
    user = make_user(is_active=False)
    response = client.post(reverse("login"), {"username": user.email, "password": PASSWORD})
    assert response.status_code == 200


def test_non_participating_user_can_log_in(client, make_user):
    user = make_user(is_participating=False)
    response = client.post(reverse("login"), {"username": user.email, "password": PASSWORD})
    assert response.status_code == 302


def test_session_lasts_30_days(client, user):
    client.post(reverse("login"), {"username": user.email, "password": PASSWORD})
    assert client.session.get_expiry_age() == 60 * 60 * 24 * 30


def test_logout_is_post_only(client, user):
    client.force_login(user)
    assert client.get(reverse("logout")).status_code == 405
    response = client.post(reverse("logout"))
    assert response.status_code == 302
    assert response.url == reverse("login")
    assert client.get(reverse("home")).status_code == 302


def test_layout_shows_display_name_and_bottom_nav(client, make_user):
    user = make_user(name="Gopal Sharma", spiritual_name="Govinda Das")
    client.force_login(user)
    html = client.get(reverse("home")).content.decode()
    assert "Govinda Das" in html
    assert user.email not in html
    for label in ["Today", "My Report", "Ranks", "Analysis", "More", "Devotees", "Logout"]:
        assert label in html
    assert 'aria-current="page"' in html


def test_manage_links_only_for_superusers(client, make_user):
    client.force_login(make_user())
    assert "/manage/" not in client.get(reverse("home")).content.decode()
    client.force_login(make_user(email="admin@example.com", is_superuser=True))
    html = client.get(reverse("home")).content.decode()
    for name in ["manage_users", "manage_fields", "manage_settings", "manage_audit"]:
        assert reverse(name) in html


def test_theme_dropdown_only_for_superusers(client, make_user):
    client.force_login(make_user())
    assert 'id="theme-select"' not in client.get(reverse("devotees")).content.decode()
    client.force_login(make_user(email="admin@example.com", is_superuser=True))
    assert 'id="theme-select"' in client.get(reverse("devotees")).content.decode()


def test_superuser_theme_choice_applies_to_everyone(client, make_user):
    devotee = make_user()
    admin = make_user(email="admin@example.com", is_superuser=True)
    page, change = reverse("devotees"), reverse("manage_theme")

    client.force_login(devotee)
    assert 'data-theme="saffron"' in client.get(page).content.decode()
    assert client.post(change, {"theme": "peacock"}).status_code == 403

    client.force_login(admin)
    response = client.post(change, {"theme": "peacock", "next": page})
    assert response.status_code == 302 and response.url == page
    assert client.post(change, {"theme": "no-such-theme", "next": "https://evil.example/"}).url == reverse("home")

    client.force_login(devotee)
    assert 'data-theme="peacock"' in client.get(page).content.decode()
    client.logout()
    assert 'data-theme="peacock"' in client.get(reverse("login")).content.decode()
