import json
import unicodedata

from django.db import transaction

from apps.products.models import Product
from apps.products.ordering import PRODUCT_LISTS, order_fingerprint


def catalogue_products(search=""):
    """Return editable catalogue entries, including inactive products."""
    return Product.objects.filter(description__icontains=search).order_by("description", "id")


def _alphabetical_key(product):
    """Compare Portuguese names without case or accent differences."""
    name = unicodedata.normalize("NFD", product.description.casefold())
    return ("".join(char for char in name if not unicodedata.combining(char)), product.pk)


def catalogue_snapshot(search=""):
    """Read the scale selection and remaining cards from one database snapshot."""
    with transaction.atomic():
        return {
            "selected_scale_product": scale_product(),
            "products": sorted(catalogue_products(search).filter(is_scale_product=False), key=_alphabetical_key),
        }


def product_ordering_snapshot():
    """Read both ordering lists from one consistent database snapshot."""
    with transaction.atomic():
        return {"ordering_lists": product_ordering_lists()}


def active_products():
    """Return the complete active catalogue."""
    return Product.objects.filter(active=True)


def quick_access_products():
    """Return active quick-access products in configured order."""
    return active_products().filter(is_quick_access=True)


def ordered_products(kind):
    """Return the complete active membership in its consumer's display order."""
    flag, field, _ = PRODUCT_LISTS[kind]
    tie_breakers = ["description", "id"] if kind == "quick" else ["id"]
    return active_products().filter(**{flag: True}).order_by(field, *tie_breakers)


def product_ordering_lists():
    """Build complete ordering controls, unaffected by catalogue searches."""
    lists = []
    for kind, (_, field, title) in PRODUCT_LISTS.items():
        products = list(ordered_products(kind))
        lists.append({
            "kind": kind, "title": title, "products": products,
            "fingerprint": order_fingerprint(products, field),
            "product_ids": json.dumps([product.pk for product in products]),
        })
    return lists


def scale_product_choices():
    """Return only products eligible for scale capture."""
    return active_products().filter(unit=Product.Unit.KILOGRAM)


def scale_product():
    """Return the selected active kilogram product, if configured."""
    return active_products().filter(is_scale_product=True, unit=Product.Unit.KILOGRAM).first()
