"""Presentation-only context for the two attendance layouts."""

from django.urls import reverse

from .presentation import compact_layout, attendance_url


def attendance_layout(request):
    """Expose allowlisted routes and templates for the selected layout."""
    compact = compact_layout(request)
    return {
        "compact_attendance": compact,
        "attendance_url": attendance_url(request),
        "product_search_url": reverse("alternative_products") if compact else attendance_url(request),
        "attendance_layout_suffix": "" if compact else "?layout=alternative",
        "attendance_layout_query": "" if compact else "&layout=alternative",
        "order_panel_template": "orders/alternative/order_panel.html" if compact else "orders/order_panel.html",
    }
