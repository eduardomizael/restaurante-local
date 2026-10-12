from apps.measurements.models import Measurement
from django.core.exceptions import ValidationError
from apps.core.domain import calculate_weight_total
from apps.products.selectors import scale_product_choices


def all_measurements():
    """Return captures for explicit identity lookup, including unavailable ones."""
    return Measurement.objects.all()


def measurement_product_choices(weight_grams):
    """Show eligible products and their exact total for the unchanged weight."""
    products = list(scale_product_choices())
    for product in products:
        try:
            product.measurement_total_cents = calculate_weight_total(product.unit_price_cents, weight_grams)
        except ValidationError:
            product.measurement_total_cents = None
    return products


def available_measurements():
    """Return all available captures without expiration or order filtering."""
    return Measurement.objects.filter(status=Measurement.Status.AVAILABLE)
