from django.db import models
from django.db.models import Q


class Product(models.Model):
    """Current catalogue; historical values belong to measurements and items."""

    class Unit(models.TextChoices):
        UNIT = "UN", "Unidade"
        KILOGRAM = "KG", "Quilograma"

    description = models.CharField(max_length=120)
    unit = models.CharField(max_length=2, choices=Unit.choices)
    unit_price_cents = models.PositiveBigIntegerField()
    active = models.BooleanField(default=True)
    is_scale_product = models.BooleanField(default=False)
    is_quick_access = models.BooleanField(default=False)
    appears_on_order_slip = models.BooleanField(default=False)
    quick_access_order = models.PositiveIntegerField(default=0)
    slip_order = models.PositiveIntegerField(default=0)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["quick_access_order", "description", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(unit__in=["UN", "KG"]), name="product_valid_unit"),
            models.CheckConstraint(condition=~Q(description=""), name="product_description_not_empty"),
            models.CheckConstraint(condition=Q(unit_price_cents__lte=9_000_000_000_000), name="product_price_limit"),
            models.CheckConstraint(condition=Q(revision__gte=1), name="product_positive_revision"),
            models.CheckConstraint(condition=Q(is_scale_product=False) | Q(unit="KG", active=True), name="scale_product_active_kg"),
            models.UniqueConstraint(fields=["is_scale_product"], condition=Q(is_scale_product=True), name="one_scale_product"),
        ]
