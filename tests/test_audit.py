import pytest

from audit import services
from audit.models import AuditLog


def test_audit_rows_are_append_only(user):
    row = services.log(AuditLog.Action.ENTRY_CREATE, user, target_user=user, field_key="hearing", new_value=30)
    row.new_value = "999"
    with pytest.raises(TypeError):
        row.save()
    with pytest.raises(TypeError):
        row.delete()
    assert AuditLog.objects.get().new_value == "30"


def test_audit_rows_survive_user_deletion(make_user, user):
    other = make_user(email="other@example.com")
    services.log(AuditLog.Action.ENTRY_CREATE, other, target_user=other, field_key="hearing", new_value=30)
    other.delete()
    row = AuditLog.objects.get()
    assert row.actor is None and row.target_user is None and row.field_key == "hearing"


def test_admin_cannot_change_audit_rows(client, superuser):
    row = services.log(AuditLog.Action.ENTRY_CREATE, superuser, field_key="hearing", new_value=30)
    client.force_login(superuser)
    assert client.get("/admin/audit/auditlog/").status_code == 200
    assert client.get("/admin/audit/auditlog/add/").status_code == 403
    assert client.post(f"/admin/audit/auditlog/{row.pk}/delete/", {"post": "yes"}).status_code == 403
    assert AuditLog.objects.count() == 1
