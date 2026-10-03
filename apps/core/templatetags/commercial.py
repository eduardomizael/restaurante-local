from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def money(value):
    """Format integer cents without a float conversion."""
    return f"{Decimal(value) / 100:.2f}".replace(".", ",")


@register.filter
def kilograms(value):
    """Format integer grams as three-decimal kilograms."""
    return f"{Decimal(value) / 1000:.3f}".replace(".", ",")
