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
