import pytest

PAGES = [
    "/admin/",
    "/admin/sadhana/sadhanafield/",
    "/admin/sadhana/sadhanaentry/",
    "/admin/sadhana/sadhanaentry/add/",
    "/admin/sadhana/userfieldsetting/",
    "/admin/sadhana/appsettings/1/change/",
    "/admin/accounts/user/",
]


@pytest.mark.parametrize("path", PAGES)
def test_admin_pages_load_for_superuser(client, superuser, path):
    client.force_login(superuser)
    assert client.get(path).status_code == 200


def test_admin_is_closed_to_normal_users(client, user):
    client.force_login(user)
    assert client.get("/admin/sadhana/sadhanafield/").status_code == 302
