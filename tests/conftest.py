import pytest

from accounts.models import User

PASSWORD = "hare-krishna-108"


@pytest.fixture
def make_user(db):
    def _make_user(email="devotee@example.com", **kwargs):
        kwargs.setdefault("name", "Test Devotee")
        kwargs.setdefault("must_change_password", False)
        return User.objects.create_user(email=email, password=PASSWORD, **kwargs)

    return _make_user


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def superuser(make_user):
    return make_user(email="admin@example.com", name="Admin", is_superuser=True)


@pytest.fixture
def app_settings(db):
    from sadhana.models import AppSettings

    return AppSettings.load()


@pytest.fixture
def field(db):
    """Look up a seeded SadhanaField by key."""
    from sadhana.models import SadhanaField

    return lambda key: SadhanaField.objects.get(key=key)
