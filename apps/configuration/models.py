from django.db import models
from django.db.models import Q


class ApplicationConfiguration(models.Model):
    """Versioned display identity, separate from printed document content."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    display_name = models.CharField(max_length=80, default="Restaurante Local")
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="application_configuration_singleton"),
            models.CheckConstraint(condition=Q(revision__gte=1), name="application_configuration_revision"),
            models.CheckConstraint(condition=~Q(display_name=""), name="application_configuration_name_nonempty"),
        ]


class HardwareConfiguration(models.Model):
    """One versioned equipment configuration, independent of installation files."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    scale_port = models.CharField(max_length=8, default="COM3")
    printer_name = models.CharField(max_length=120, default="balanca")
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="hardware_configuration_singleton"),
            models.CheckConstraint(condition=Q(revision__gte=1), name="hardware_configuration_revision"),
        ]
