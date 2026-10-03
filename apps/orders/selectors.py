from uuid import uuid4

from django.db.models import Max, Sum

from apps.orders.models import Order, OrderItem, OrderSequence
from apps.core.models import DomainEvent
from apps.measurements.selectors import available_measurements
from apps.products.selectors import active_products, quick_access_products, scale_product


def all_orders():
    """Return orders for explicit HTTP identity lookup."""
    return Order.objects.all()


def next_order_number():
    """Read the configured sequence without creating it during GET."""
    return OrderSequence.objects.filter(pk=1).values_list("next_number", flat=True).first() or 1


def board_snapshot(selected_id=None):
    """Read a board with fixed destination identities and revision-before-data.

    Args:
        selected_id: Explicit requested order identity or None for initial selection.

    Returns:
        dict: Presentation data; revision is read first so a concurrent write
        cannot mark stale list contents with a newer version.
    """
    revision = DomainEvent.objects.aggregate(last=Max("id"))["last"] or 0
    orders = list(open_orders())
    selected = next((order for order in orders if order.pk == selected_id), None)
    if selected_id is None and orders:
        selected = orders[0]
    measurements = list(available_measurements())
    for measurement in measurements:
        measurement.action_key = uuid4()
    items = list(active_items(selected.pk)) if selected else []
    return {
        "revision": revision, "orders": orders, "selected": selected,
        "selected_id": selected_id if selected_id is not None else (selected.pk if selected else ""),
        "measurements": measurements,
        "items": items,
        "subtotal": sum(item.total_cents for item in items),
    }


def attendance_snapshot(selected_id=None, search=""):
    """Add current order snapshots and catalogue choices to the shared board."""
    data = board_snapshot(selected_id)
    data.update({
        "quick_products": list(quick_access_products()),
        "products": list(active_products().filter(description__icontains=search)),
        "scale_product": scale_product(), "search": search,
        "open_key": uuid4(),
    })
    return data


def open_orders():
    """Return all recoverable drafts in number order."""
    return Order.objects.filter(status=Order.Status.DRAFT)


def active_items(order_id):
    """Return only active snapshots for the explicitly selected order."""
    return OrderItem.objects.filter(order_id=order_id, active=True)


def subtotal_cents(order_id):
    """Sum stored cents without consulting current product prices."""
    return active_items(order_id).aggregate(total=Sum("total_cents"))["total"] or 0
