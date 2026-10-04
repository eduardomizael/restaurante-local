"""Atomic document finalization and durable, explicit delivery transitions."""

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.domain import DomainConflict, require_integer, require_uuid, write_transaction
from apps.core.services import record_event
from apps.configuration.selectors import hardware_configuration
from apps.orders.models import Order
from apps.printing.documents import fingerprint
from apps.printing.models import DocumentConfiguration, OrderDocument, PrintJob
from apps.printing.selectors import draft_content


def save_document_configuration(*, header, footer, expected_revision):
    """Save document text with optimistic revision and no hardware effects."""
    if not isinstance(header, str) or not 1 <= len(header.strip()) <= 120:
        raise ValidationError("Cabeçalho deve conter de 1 a 120 caracteres.")
    if not isinstance(footer, str) or len(footer.strip()) > 500:
        raise ValidationError("Rodapé deve conter no máximo 500 caracteres.")
    if any(ord(char) < 32 and char not in "\n\r" for char in header + footer):
        raise ValidationError("Texto contém caracteres de controle inválidos.")
    require_integer(expected_revision, minimum=0, maximum=2_147_483_647, label="Revisão")
    with write_transaction():
        configuration = DocumentConfiguration.objects.filter(pk=1).first()
        if (configuration.revision if configuration else 0) != expected_revision:
            raise DomainConflict("Configuração alterada em outra tela. Recarregue antes de salvar.")
        if configuration is None:
            configuration = DocumentConfiguration(pk=1)
        else:
            configuration.revision += 1
        configuration.header, configuration.footer = header.strip(), footer.strip()
        configuration.save()
        record_event("DOCUMENT_CONFIGURATION_SAVED", configuration, revision=configuration.revision)
        return configuration


def finalize_order(*, order_id, request_key, expected_fingerprint, delivery_mode="PREVIEW", expected_printer_revision=None):
    """Print a frozen closing snapshot and close only the selected order."""
    return _print_order(order_id=order_id, request_key=request_key, expected_fingerprint=expected_fingerprint,
                        delivery_mode=delivery_mode, expected_printer_revision=expected_printer_revision,
                        close_order=True)


def print_open_order(*, order_id, request_key, expected_fingerprint, delivery_mode="PREVIEW", expected_printer_revision=None):
    """Print a frozen snapshot while keeping the selected order editable."""
    return _print_order(order_id=order_id, request_key=request_key, expected_fingerprint=expected_fingerprint,
                        delivery_mode=delivery_mode, expected_printer_revision=expected_printer_revision,
                        close_order=False)


def _print_order(*, order_id, request_key, expected_fingerprint, delivery_mode, expected_printer_revision, close_order):
    """Freeze one order and initial job in the same short transaction.

    Args:
        order_id: Explicit selected order identity.
        request_key: UUID reused on double click or retry.
        expected_fingerprint: Commercial content reviewed in the draft preview.
        delivery_mode: PREVIEW or RAW, frozen for the resulting job.
        expected_printer_revision: Configuration revision reviewed by the operator.

    Returns:
        PrintJob: Exactly one initial job, including idempotent retries.
    """
    key = require_uuid(request_key)
    if delivery_mode not in ("PREVIEW", "RAW"):
        raise ValidationError("Modo de impressão inválido.")
    with write_transaction():
        existing = PrintJob.objects.filter(request_key=key).select_related("document").first()
        if existing:
            reviewed = {name: value for name, value in existing.document.content.items()
                        if name not in ("finalized_at", "printed_at")}
            if (existing.document.order_id != order_id or existing.kind != PrintJob.Kind.INITIAL
                    or fingerprint(reviewed) != expected_fingerprint or existing.delivery_mode != delivery_mode
                    or existing.document.is_final != close_order):
                raise DomainConflict("Identificador de impressão já usado com outro destino.")
            return existing
        order = Order.objects.filter(pk=order_id).first()
        if order is None:
            raise ValidationError("Comanda não encontrada.")
        if order.status != Order.Status.DRAFT:
            raise DomainConflict("Comanda encerrada. Consulte o documento salvo no histórico.")
        if PrintJob.objects.filter(document__order=order, status__in=["PENDING", "SUBMITTING"]).exists():
            raise DomainConflict("Já há uma impressão pendente para esta comanda. Aguarde o resultado.")
        content = draft_content(order)
        if not content["header"]:
            raise ValidationError("Configure o cabeçalho antes de finalizar a comanda.")
        if not content["items"]:
            raise ValidationError("Inclua pelo menos um item antes de finalizar.")
        if fingerprint(content) != expected_fingerprint:
            raise DomainConflict("Itens ou configuração mudaram após a prévia. Revise o documento novamente.")
        now = timezone.now()
        content["finalized_at" if close_order else "printed_at"] = timezone.localtime(now).isoformat(timespec="seconds")
        target = hardware_configuration()
        if delivery_mode == "RAW" and expected_printer_revision is not None and target.revision != expected_printer_revision:
            raise DomainConflict("Fila de impressão mudou após a prévia. Revise novamente.")
        document = OrderDocument.objects.create(order=order, is_final=close_order,
                                                content=content, fingerprint=fingerprint(content))
        job = PrintJob.objects.create(document=document, request_key=key, kind=PrintJob.Kind.INITIAL,
                                      delivery_mode=delivery_mode,
                                      printer_name=target.printer_name if delivery_mode == "RAW" else "")
        if close_order:
            order.status, order.finalized_at = Order.Status.FINALIZED, now
            order.save(update_fields=["status", "finalized_at"])
        record_event("ORDER_FINALIZED" if close_order else "OPEN_ORDER_PRINT_REQUESTED", order,
                     document_id=document.pk, job_id=job.pk)
        return job


def request_reprint(*, document_id, request_key, delivery_mode="PREVIEW", expected_printer_revision=None):
    """Create an explicit second copy without changing the frozen content."""
    key = require_uuid(request_key)
    if delivery_mode not in ("PREVIEW", "RAW"):
        raise ValidationError("Modo de impressão inválido.")
    with write_transaction():
        existing = PrintJob.objects.filter(request_key=key).first()
        if existing:
            if (existing.document_id, existing.kind, existing.delivery_mode) != (document_id, PrintJob.Kind.REPRINT, delivery_mode):
                raise DomainConflict("Identificador de segunda via já usado com outros dados.")
            return existing
        document = OrderDocument.objects.filter(pk=document_id).first()
        if document is None:
            raise ValidationError("Documento não encontrado.")
        if PrintJob.objects.filter(document__order_id=document.order_id, status__in=["PENDING", "SUBMITTING"]).exists():
            raise DomainConflict("Já há um envio pendente para esta comanda. Aguarde o resultado.")
        target = hardware_configuration()
        if delivery_mode == "RAW" and expected_printer_revision is not None and target.revision != expected_printer_revision:
            raise DomainConflict("Fila de impressão mudou após a revisão. Reabra a segunda via.")
        job = PrintJob.objects.create(document=document, request_key=key, kind=PrintJob.Kind.REPRINT,
                                      delivery_mode=delivery_mode,
                                      printer_name=target.printer_name if delivery_mode == "RAW" else "")
        record_event("REPRINT_REQUESTED", job, document_id=document.pk)
        return job


def claim_next_job(delivery_mode=None):
    """Persist intent before invoking any transport outside the transaction."""
    with write_transaction():
        jobs = PrintJob.objects.filter(status=PrintJob.Status.PENDING)
        if delivery_mode is not None:
            jobs = jobs.filter(delivery_mode=delivery_mode)
        job = jobs.select_related("document").first()
        if job is None:
            return None
        job.status, job.attempt_key = PrintJob.Status.SUBMITTING, uuid4()
        job.attempts += 1
        job.submitted_at = timezone.now()
        job.save(update_fields=["status", "attempt_key", "attempts", "submitted_at"])
        record_event("PRINT_SUBMITTING", job, attempt_key=str(job.attempt_key))
        return job


def complete_job(*, job_id, attempt_key, status, message, spooler_job_id=None):
    """Record simulated delivery, spooler acceptance, failure or uncertainty."""
    if status not in (PrintJob.Status.SIMULATED, PrintJob.Status.SPOOL_ACCEPTED, PrintJob.Status.FAILED, PrintJob.Status.UNKNOWN):
        raise ValidationError("Resultado de impressão inválido.")
    key = require_uuid(attempt_key)
    with write_transaction():
        job = PrintJob.objects.filter(pk=job_id, attempt_key=key).first()
        if job is None:
            raise DomainConflict("Tentativa de impressão não corresponde ao trabalho.")
        if job.status != PrintJob.Status.SUBMITTING:
            if job.status == status:
                return job
            raise DomainConflict("Resultado já registrado; nenhuma alteração aplicada.")
        job.status, job.result_message = status, str(message)[:500]
        if status == PrintJob.Status.SPOOL_ACCEPTED:
            if job.delivery_mode != "RAW":
                raise ValidationError("Trabalho simulado não pode registrar aceitação física.")
            require_integer(spooler_job_id, maximum=4_294_967_295, label="Trabalho do spooler")
        elif spooler_job_id is not None or (status == PrintJob.Status.SIMULATED and job.delivery_mode != "PREVIEW"):
            raise ValidationError("Resultado incompatível com o modo de envio.")
        job.spooler_job_id = spooler_job_id
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "result_message", "completed_at", "spooler_job_id"])
        record_event("PRINT_RESULT", job, status=status)
        return job


def recover_interrupted_jobs():
    """Mark in-flight jobs uncertain once, under exclusive runtime ownership."""
    with write_transaction():
        count = 0
        for job in PrintJob.objects.filter(status=PrintJob.Status.SUBMITTING):
            job.status = PrintJob.Status.UNKNOWN
            job.completed_at = timezone.now()
            job.result_message = "Envio interrompido. Revise o resultado antes de solicitar segunda via."
            job.save(update_fields=["status", "completed_at", "result_message"])
            record_event("PRINT_RECOVERED_UNKNOWN", job)
            count += 1
        return count
