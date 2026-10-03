from django.db.models import Sum

from apps.orders.models import Order, OrderItem


def open_orders():
    """Return all recoverable drafts in number order."""
    return Order.objects.filter(status=Order.Status.DRAFT)


def active_items(order_id):
    """Return only active snapshots for the explicitly selected order."""
    return OrderItem.objects.filter(order_id=order_id, active=True)


def subtotal_cents(order_id):
    """Sum stored cents without consulting current product prices."""
    return active_items(order_id).aggregate(total=Sum("total_cents"))["total"] or 0
