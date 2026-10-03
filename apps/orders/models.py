from django.db import models
from django.db.models import Q


class OrderSequence(models.Model):
    """One transaction-protected sequence, never reset by day or cancellation."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_number = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="order_sequence_singleton"),
            models.CheckConstraint(condition=Q(next_number__gte=1), name="order_sequence_positive"),
        ]


class Order(models.Model):
    """One of many simultaneous drafts; its number is never reused."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Aberta"
        FINALIZED = "FINALIZED", "Finalizada"
        CANCELLED = "CANCELLED", "Cancelada"

    number = models.PositiveBigIntegerField(unique=True)
    request_key = models.UUIDField(unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.CheckConstraint(condition=Q(number__gte=1, number__lte=2_147_483_647), name="order_number_limits"),
            models.CheckConstraint(condition=(Q(status="DRAFT", cancelled_at__isnull=True, finalized_at__isnull=True)
                                             | Q(status="CANCELLED", cancelled_at__isnull=False, finalized_at__isnull=True)
                                             | Q(status="FINALIZED", cancelled_at__isnull=True, finalized_at__isnull=False)), name="order_status_dates_consistent"),
        ]


class OrderItem(models.Model):
    """Immutable commercial snapshot with a reversible draft-only active link."""

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        SCALE = "SCALE", "Balança"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    measurement = models.ForeignKey("measurements.Measurement", null=True, blank=True, on_delete=models.PROTECT, related_name="item_links")
    request_key = models.UUIDField(unique=True)
    source = models.CharField(max_length=6, choices=Source.choices)
    product_description = models.CharField(max_length=120)
    unit = models.CharField(max_length=2)
    quantity_units = models.PositiveIntegerField(null=True, blank=True)
    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    unit_price_cents = models.PositiveBigIntegerField()
    total_cents = models.PositiveBigIntegerField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["measurement"], condition=Q(active=True, measurement__isnull=False), name="one_active_item_per_measurement"),
            models.CheckConstraint(condition=(Q(unit="UN", quantity_units__isnull=False, quantity_units__gte=1, quantity_units__lte=100_000, weight_grams__isnull=True)
                                             | Q(unit="KG", weight_grams__isnull=False, weight_grams__gte=1, weight_grams__lte=1_000_000, quantity_units__isnull=True)), name="item_quantity_matches_unit"),
            models.CheckConstraint(condition=(Q(source="MANUAL", measurement__isnull=True)
                                             | Q(source="SCALE", measurement__isnull=False, unit="KG")), name="item_source_matches_measurement"),
            models.CheckConstraint(condition=Q(unit_price_cents__lte=9_000_000_000_000, total_cents__lte=9_000_000_000_000), name="item_money_limits"),
            models.CheckConstraint(condition=(Q(active=True, removed_at__isnull=True)
                                             | Q(active=False, removed_at__isnull=False)), name="item_removal_consistent"),
        ]
