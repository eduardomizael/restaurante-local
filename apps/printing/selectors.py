from django.db.models import Q

from apps.orders.models import OrderItem
from apps.products.models import Product
from apps.printing.documents import build_content
from apps.printing.models import DocumentConfiguration, OrderDocument, PrintJob


def document_configuration():
    """Read configuration without creating a singleton during GET."""
    return DocumentConfiguration.objects.filter(pk=1).first()


def draft_content(order):
    """Read current draft data; finalization repeats it under a write lock."""
    items = list(OrderItem.objects.filter(order=order, active=True))
    products = list(Product.objects.filter(
        Q(active=True, appears_on_order_slip=True) | Q(pk__in=[item.product_id for item in items]),
    ).order_by("slip_order", "id"))
    return build_content(order, items, products, document_configuration())


def order_document(order_id):
    """Read a previously frozen document."""
    return OrderDocument.objects.filter(order_id=order_id, is_final=True).first()


def latest_order_document(order_id):
    """Read the latest print snapshot without replacing the editable draft."""
    return OrderDocument.objects.filter(order_id=order_id).order_by("-id").first()


def print_history():
    """List saved documents including every failed or uncertain delivery."""
    return OrderDocument.objects.select_related("order").prefetch_related("jobs").order_by("-id")


def document_jobs(document_id):
    """Return delivery history without consulting the current catalogue."""
    return PrintJob.objects.filter(document_id=document_id)
