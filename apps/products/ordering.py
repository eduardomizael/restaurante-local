"""Shared list definitions and deterministic optimistic concurrency tokens."""

import hashlib
import json


PRODUCT_LISTS = {
    "slip": ("appears_on_order_slip", "slip_order", "Ordem na comanda"),
    "quick": ("is_quick_access", "quick_access_order", "Ordem dos produtos rápidos"),
}


def order_fingerprint(products, field):
    """Identify membership and saved positions, independently of the other list."""
    values = sorted((product.pk, getattr(product, field)) for product in products)
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()
