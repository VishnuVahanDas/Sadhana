from ..models import SadhanaField, UserFieldSetting


def effective_fields(user):
    """Active fields shown on this user's form: the per-user setting if one exists, else the field default."""
    overrides = dict(UserFieldSetting.objects.filter(user=user).values_list("field_id", "enabled"))
    return [
        field
        for field in SadhanaField.objects.filter(is_active=True)
        if overrides.get(field.id, field.enabled_by_default)
    ]
