"""Freeze explicitly reviewed reports in the durable shared print queue."""

from uuid import uuid5

from django.core.exceptions import ValidationError

from apps.configuration.selectors import hardware_configuration
from apps.core.domain import DomainConflict, require_uuid, write_transaction
from apps.core.services import record_event
from apps.printing.models import PrintJob
from apps.printing.report_documents import render_report


def request_report_print(*, reports, selection, request_key, delivery_mode, expected_printer_revision):
    """Queue one report or a daily batch atomically with idempotent request keys.

    Args:
        reports: Trusted snapshots recovered from the signed browser preview.
        selection: ``all`` or a zero-based report index.
        request_key: UUID shared by retries of this reviewed preview.
        delivery_mode: Reviewed PREVIEW or RAW mode.
        expected_printer_revision: Queue configuration revision from the preview.

    Returns:
        UUID: Batch identity for delivery results.
    """
    key = require_uuid(request_key)
    if delivery_mode not in ("PREVIEW", "RAW") or not reports:
        raise ValidationError("Solicitação de relatório inválida.")
    if selection == "all":
        selected = list(enumerate(reports))
    else:
        try:
            index = int(selection)
        except (ValueError, TypeError) as exc:
            raise ValidationError("Selecione um relatório válido.") from exc
        if index < 0 or index >= len(reports):
            raise ValidationError("Selecione um relatório válido.")
        selected = [(index, reports[index])]
    # Validate before queueing anything; transport encoding remains the worker's job.
    for _, content in selected:
        render_report(content)
    with write_transaction():
        target = hardware_configuration()
        if delivery_mode == "RAW" and target.revision != expected_printer_revision:
            raise DomainConflict("Fila de impressão mudou após a prévia. Gere o relatório novamente.")
        for index, content in selected:
            job_key = uuid5(key, str(index))
            existing = PrintJob.objects.filter(request_key=job_key).first()
            if existing:
                if (existing.report_batch_key != key or existing.report_content != content
                        or existing.delivery_mode != delivery_mode):
                    raise DomainConflict("Solicitação já utilizada para outro relatório.")
                continue
            job = PrintJob.objects.create(report_content=content, report_batch_key=key,
                                          request_key=job_key, kind=PrintJob.Kind.INITIAL,
                                          delivery_mode=delivery_mode,
                                          printer_name=target.printer_name if delivery_mode == "RAW" else "")
            record_event("REPORT_PRINT_REQUESTED", job, batch_key=str(key), start=content["start"], end=content["end"])
    return key
