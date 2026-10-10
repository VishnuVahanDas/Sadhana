import pytest
from django.urls import reverse

from .conftest import PASSWORD


def attempt(client, email, password, ip="10.1.1.1"):
    return client.post(reverse("login"), {"username": email, "password": password}, REMOTE_ADDR=ip)


def test_five_failed_logins_lock_that_email_from_that_address(client, user):
    for _ in range(4):
        assert attempt(client, user.email, "wrong").status_code == 200
    locked = attempt(client, user.email, "wrong")
    assert locked.status_code == 429
    assert "Too many attempts" in locked.content.decode()
    # Even the right password is refused while locked.
    assert attempt(client, user.email, PASSWORD).status_code == 429


def test_lockout_does_not_affect_other_people_or_other_addresses(client, user, make_user):
    other = make_user(email="other@example.com")
    for _ in range(5):
        attempt(client, user.email, "wrong")
    # Someone else on the same temple Wi-Fi can still log in...
    assert attempt(client, other.email, PASSWORD).status_code == 302
    client.post(reverse("logout"))
    # ...and the locked devotee can log in from another address.
    assert attempt(client, user.email, PASSWORD, ip="10.2.2.2").status_code == 302


def test_changing_the_case_of_the_email_does_not_dodge_the_lock(client, user):
    for variant in ["Devotee@example.com", "DEVOTEE@EXAMPLE.COM", " devotee@example.com ", "devotee@Example.com"]:
        assert attempt(client, variant, "wrong").status_code == 200
    assert attempt(client, user.email, "wrong").status_code == 429


def test_successful_login_resets_the_counter(client, user):
    for _ in range(4):
        attempt(client, user.email, "wrong")
    assert attempt(client, user.email, PASSWORD).status_code == 302
    client.post(reverse("logout"))
    for _ in range(4):
        assert attempt(client, user.email, "wrong").status_code == 200


def test_lockout_uses_the_forwarded_address(client, user):
    for _ in range(5):
        client.post(reverse("login"), {"username": user.email, "password": "wrong"}, HTTP_X_FORWARDED_FOR="203.0.113.7")
    blocked = client.post(
        reverse("login"), {"username": user.email, "password": PASSWORD}, HTTP_X_FORWARDED_FOR="203.0.113.7"
    )
    assert blocked.status_code == 429
    allowed = client.post(
        reverse("login"), {"username": user.email, "password": PASSWORD}, HTTP_X_FORWARDED_FOR="203.0.113.8"
    )
    assert allowed.status_code == 302


def test_themed_error_pages(client, user):
    client.force_login(user)
    missing = client.get("/no-such-page/")
    assert missing.status_code == 404 and "Page not found" in missing.content.decode()
    forbidden = client.get(reverse("manage_users"))
    assert forbidden.status_code == 403 and "only for temple administrators" in forbidden.content.decode()


@pytest.mark.parametrize("name", ["SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"])
def test_production_settings_follow_debug(name):
    """With DEBUG=False the hardening block is active; this guards against it being removed."""
    import subprocess
    import sys

    code = f"import os; os.environ['DEBUG']='False'; from django.conf import settings; print(settings.{name}, settings.SECURE_HSTS_SECONDS > 0, settings.SECURE_PROXY_SSL_HEADER)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={**__import__("os").environ, "DJANGO_SETTINGS_MODULE": "config.settings", "DEBUG": "False"},
    )
    assert result.stdout.strip() == "True True ('HTTP_X_FORWARDED_PROTO', 'https')", result.stderr
