"""Explicit attendance layout selection without changing commercial behavior."""

from django.urls import reverse


def compact_layout(request):
    """Use compact attendance by default and preserve the legacy alternative."""
    route = request.resolver_match.url_name if request.resolver_match else None
    if route == "attendance_alternative":
        return False
    if route in {"home", "alternative_products"}:
        return True
    return request.GET.get("layout", request.POST.get("layout")) != "alternative"


def attendance_url(request):
    """Return the attendance route selected for this request."""
    return reverse("home" if compact_layout(request) else "attendance_alternative")


def layout_url(request, url):
    """Carry the alternative layout through a known internal URL."""
    if not compact_layout(request):
        return url + ("&" if "?" in url else "?") + "layout=alternative"
    return url
