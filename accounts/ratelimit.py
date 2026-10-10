def login_email(request, credentials=None):
    """The email a login attempt is counted against: trimmed and lowercased, so
    "Name@Example.com" and "name@example.com" share one failure counter."""
    source = credentials or (request.POST if request is not None else {})
    return (source.get("username") or "").strip().lower()
