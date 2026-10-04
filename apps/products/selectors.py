from django.db import transaction

from apps.products.models import Product


def catalogue_products(search=""):
    """Return editable catalogue entries, including inactive products."""
    return Product.objects.filter(description__icontains=search)


def catalogue_snapshot(search=""):
    """Read the scale selection and remaining cards from one database snapshot."""
    with transaction.atomic():
        return {
            "selected_scale_product": scale_product(),
            "products": list(catalogue_products(search).filter(is_scale_product=False)),
        }


def active_products():
    """Return the complete active catalogue."""
    return Product.objects.filter(active=True)


def quick_access_products():
    """Return active quick-access products in configured order."""
    return active_products().filter(is_quick_access=True)


def scale_product():
    """Return the selected active kilogram product, if configured."""
    return active_products().filter(is_scale_product=True, unit=Product.Unit.KILOGRAM).first()
