"""Persistent print queue consumer, owned only by the explicit initializer."""

import logging
from threading import Thread

from django.db import close_old_connections, connections

from apps.printing.documents import render_text
from apps.printing.models import PrintJob
from apps.printing.services import claim_next_job, complete_job
from hardware.printer.simulator import SimulatedPrinter, SimulatedPrintFailure

logger = logging.getLogger(__name__)


class PrintWorker(Thread):
    """Consume one job at a time without keeping DB locks during transport."""

    def __init__(self, stop_event, adapter=None, interval=0.5):
        super().__init__(name="print-worker", daemon=True)
        self.stop_event = stop_event
        self.adapter = adapter if adapter is not None else SimulatedPrinter()
        self.interval = interval

    def process_one(self):
        """Process a claimed job; uncertain outcomes are never auto-retried."""
        if self.stop_event.is_set():
            return False
        job = claim_next_job()
        if job is None:
            return False
        try:
            text = render_text(job.document.content, second_copy=job.kind == PrintJob.Kind.REPRINT)
            message = self.adapter.send(text)
            result = PrintJob.Status.SIMULATED
        except SimulatedPrintFailure as exc:
            result, message = PrintJob.Status.FAILED, str(exc)
        except Exception as exc:
            logger.exception("Resultado de simulação incerto")
            result, message = PrintJob.Status.UNKNOWN, str(exc)
        complete_job(job_id=job.pk, attempt_key=job.attempt_key, status=result, message=message)
        return True

    def run(self):
        """Stop between jobs; finish the current bounded simulated send."""
        try:
            while not self.stop_event.is_set():
                close_old_connections()
                try:
                    self.process_one()
                except Exception:
                    # Never resend if claiming or recording the result failed.
                    logger.exception("Falha na fila persistente de impressão")
                self.stop_event.wait(self.interval)
        finally:
            try:
                self.adapter.close()
            finally:
                connections.close_all()
