"""Read order reports from historical items, independently of print versions."""

from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.printing.models import OrderDocument


def period_orders(start, end):
    """Select orders by their local opening date, including the entire last day."""
    zone = timezone.get_current_timezone()
    lower = timezone.make_aware(datetime.combine(start, time.min), zone)
    # Avoid overflowing date.max while preserving a half-open interval.
    if end.year == 9999 and end.month == 12 and end.day == 31:
        return Order.objects.filter(created_at__gte=lower, created_at__date__lte=end)
    upper = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), zone)
    return Order.objects.filter(created_at__gte=lower, created_at__lt=upper)


def order_report(start, end):
    """List one row per order with its preserved versions and active item total."""
    return period_orders(start, end).annotate(
        report_total=Sum("items__total_cents", filter=Q(items__active=True)),
    ).prefetch_related(Prefetch("documents", queryset=OrderDocument.objects.order_by("created_at", "pk"))).order_by("-created_at", "-pk")


def totals_report(start, end, mode, header):
    """Build a consistent snapshot with counts and sums of finalized items.

    Args:
        start: First local opening date, inclusive.
        end: Last local opening date, inclusive.
        mode: ``period`` or ``daily``.
        header: Display name frozen with the reviewed report.

    Returns:
        list[dict]: One consolidated report or one report per calendar day.
    """
    def empty(first, last):
        return {"version": 1, "header": header, "start": first.isoformat(), "end": last.isoformat(),
                "opened": 0, "closed": 0, "cancelled": 0, "items": [], "total_cents": 0}

    reports = ({(start + timedelta(days=index)).isoformat(): empty(start + timedelta(days=index), start + timedelta(days=index))
                for index in range((end - start).days + 1)} if mode == "daily" else {"period": empty(start, end)})
    generated_at = timezone.localtime().isoformat(timespec="seconds")
    with transaction.atomic():
        orders = period_orders(start, end)
        counts = list(orders.annotate(day=TruncDate("created_at")).values("day", "status").order_by().annotate(count=Count("pk")))
        items = OrderItem.objects.filter(order__in=orders.filter(status=Order.Status.FINALIZED), active=True)
        fields = ["product_id", "product_description", "unit"]
        if mode == "daily":
            items = items.annotate(day=TruncDate("order__created_at"))
            fields.append("day")
        rows = list(items.values(*fields).order_by(*fields).annotate(
            quantity=Sum("quantity_units"), weight=Sum("weight_grams"), value=Sum("total_cents")))
    names = {Order.Status.DRAFT: "opened", Order.Status.FINALIZED: "closed", Order.Status.CANCELLED: "cancelled"}
    for row in counts:
        report = reports[row["day"].isoformat() if mode == "daily" else "period"]
        report[names[row["status"]]] += row["count"]
    for row in rows:
        report = reports[row["day"].isoformat() if mode == "daily" else "period"]
        report["items"].append({"description": row["product_description"], "unit": row["unit"],
                                "quantity": row["quantity"] or 0, "weight": row["weight"] or 0,
                                "total_cents": row["value"]})
        report["total_cents"] += row["value"]
    for report in reports.values():
        report["generated_at"] = generated_at
    return list(reports.values())
