import uuid

from django.db import models
from django.db.models import Q


class Measurement(models.Model):
    """Shared persisted scale capture, independent of any order at capture time."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponível"
        USED = "USED", "Utilizada"
        DISCARDED = "DISCARDED", "Descartada"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    capture_key = models.UUIDField(unique=True)
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    product_description = models.CharField(max_length=120)
    unit_price_cents = models.PositiveBigIntegerField()
    total_cents = models.PositiveBigIntegerField()
    net_weight_grams = models.PositiveIntegerField()
    tare_grams = models.PositiveIntegerField(default=0)
    device = models.CharField(max_length=120)
    stability_parameters = models.JSONField(default=dict)
    captured_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    discard_reason = models.CharField(max_length=30, blank=True)
    discarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=["AVAILABLE", "USED", "DISCARDED"]), name="measurement_valid_status"),
            models.CheckConstraint(condition=Q(net_weight_grams__gte=1, net_weight_grams__lte=1_000_000), name="measurement_weight_limits"),
            models.CheckConstraint(condition=Q(unit_price_cents__lte=9_000_000_000_000, total_cents__lte=9_000_000_000_000), name="measurement_money_limits"),
            models.CheckConstraint(condition=(Q(status="DISCARDED", discard_reason="MANUAL_DISCARD", discarded_at__isnull=False)
                                             | (~Q(status="DISCARDED") & Q(discard_reason="", discarded_at__isnull=True))), name="measurement_discard_consistent"),
        ]
