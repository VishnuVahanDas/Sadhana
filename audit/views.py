from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from accounts.decorators import superuser_required

from .forms import AuditFilterForm
from .models import AuditLog

PAGE_SIZE = 50


@superuser_required
def audit_log(request):
    form = AuditFilterForm(request.GET or None)
    rows = AuditLog.objects.select_related("actor", "target_user")
    if form.is_valid():
        filters = form.cleaned_data
        if filters["user"]:
            rows = rows.filter(Q(actor=filters["user"]) | Q(target_user=filters["user"]))
        if filters["action"]:
            rows = rows.filter(action=filters["action"])
        if filters["date_from"]:
            rows = rows.filter(timestamp__date__gte=filters["date_from"])
        if filters["date_to"]:
            rows = rows.filter(timestamp__date__lte=filters["date_to"])
    page = Paginator(rows, PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "manage/audit.html", {"form": form, "page": page, "query": query.urlencode()})
