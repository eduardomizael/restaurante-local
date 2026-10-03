from django.db import models
from django.db.models import Q


class DocumentConfiguration(models.Model):
    """Singleton document settings; equipment configuration is separate."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    header = models.CharField(max_length=120, default="")
    footer = models.TextField(max_length=500, default="")
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="document_configuration_singleton"),
            models.CheckConstraint(condition=Q(revision__gte=1), name="document_configuration_revision"),
        ]


class OrderDocument(models.Model):
    """One immutable versioned commercial document for a finalized order."""

    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="document")
    content = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class PrintJob(models.Model):
    """Persistent delivery lifecycle, distinct from commercial finalization."""

    class Kind(models.TextChoices):
        INITIAL = "INITIAL", "Primeira via"
        REPRINT = "REPRINT", "Segunda via"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Aguardando envio"
        SUBMITTING = "SUBMITTING", "Envio em andamento"
        SIMULATED = "SIMULATED", "Simulada — sem impressão física"
        SPOOL_ACCEPTED = "SPOOL_ACCEPTED", "Aceita pelo spooler — confira o papel"
        FAILED = "FAILED", "Falha confirmada"
        UNKNOWN = "UNKNOWN", "Resultado incerto — revise antes de reimprimir"

    document = models.ForeignKey(OrderDocument, on_delete=models.PROTECT, related_name="jobs")
    request_key = models.UUIDField(unique=True)
    kind = models.CharField(max_length=7, choices=Kind.choices)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING)
    delivery_mode = models.CharField(max_length=7, default="PREVIEW", choices=[("PREVIEW", "Simulação"), ("RAW", "Impressão física")])
    printer_name = models.CharField(max_length=120, default="", blank=True)
    spooler_job_id = models.PositiveIntegerField(null=True, blank=True)
    attempt_key = models.UUIDField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    result_message = models.CharField(max_length=500, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["document"], condition=Q(kind="INITIAL"), name="one_initial_job_per_document"),
            models.UniqueConstraint(fields=["document"], condition=Q(status__in=["PENDING", "SUBMITTING"]), name="one_pending_job_per_document"),
            models.CheckConstraint(condition=Q(kind__in=["INITIAL", "REPRINT"]), name="print_job_valid_kind"),
            models.CheckConstraint(condition=(Q(delivery_mode="PREVIEW", printer_name="") | (Q(delivery_mode="RAW") & ~Q(printer_name=""))), name="print_job_transport_consistent"),
            models.CheckConstraint(condition=(Q(status="SPOOL_ACCEPTED", delivery_mode="RAW", spooler_job_id__isnull=False)
                                             | (~Q(status="SPOOL_ACCEPTED") & Q(spooler_job_id__isnull=True))), name="print_job_spooler_consistent"),
            models.CheckConstraint(condition=(
                Q(status="PENDING", attempt_key__isnull=True, attempts=0, submitted_at__isnull=True, completed_at__isnull=True)
                | Q(status="SUBMITTING", attempt_key__isnull=False, attempts__gte=1, submitted_at__isnull=False, completed_at__isnull=True)
                | Q(status__in=["SIMULATED", "SPOOL_ACCEPTED", "FAILED", "UNKNOWN"], attempt_key__isnull=False, attempts__gte=1, submitted_at__isnull=False, completed_at__isnull=False)
            ), name="print_job_state_consistent"),
        ]
