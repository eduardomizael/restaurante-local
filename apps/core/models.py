from django.db import models


class DomainEvent(models.Model):
    """Append-only history written by services in the same domain transaction."""

    kind = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=30)
    entity_id = models.CharField(max_length=64)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
