"""Reading/capture worker, independent of every HTTP page."""

import logging
from threading import Thread

from django.db import close_old_connections, connections
from django.core.exceptions import ValidationError
from hardware.scale.protocol import ScaleNoResponseError

logger = logging.getLogger(__name__)


class ScaleWorker(Thread):
    """Read an injected adapter, independently of browser lifetime."""

    def __init__(self, adapter, state, stop_event, interval=0.5, capture_controller=None):
        super().__init__(name="scale-worker", daemon=True)
        self.adapter = adapter
        self.state = state
        self.stop_event = stop_event
        self.interval = interval
        self.capture_controller = capture_controller

    def run(self):
        """Read until shutdown, always closing the adapter."""
        try:
            was_paused = False
            adapter_revision = None
            while not self.stop_event.is_set():
                close_old_connections()
                if self.state.snapshot()["paused"]:
                    if not was_paused and self.capture_controller:
                        self.capture_controller.reset()
                    was_paused = True
                    self.state.update(scale_status="PAUSED")
                else:
                    if was_paused and self.capture_controller:
                        self.capture_controller.reset()
                    was_paused = False
                    try:
                        sample = self.adapter.read()
                        revision = getattr(self.adapter, "revision", None)
                        if revision != adapter_revision:
                            if self.capture_controller:
                                self.capture_controller.reset()
                            adapter_revision = revision
                        if self.stop_event.is_set():
                            break
                        status = self.capture_controller.observe(sample) if self.capture_controller else "SIMULATED"
                        candidate = self.capture_controller.cycle.candidate if self.capture_controller else None
                        weight_unavailable = sample.protocol == "PROT_F" and sample.moving
                        self.state.update(
                            weight_grams=candidate.net_weight_grams if status == "WAITING_REMOVAL" and candidate
                            else self.state.snapshot()["weight_grams"] if weight_unavailable else sample.net_weight_grams,
                            live_weight_grams=None if weight_unavailable else sample.net_weight_grams,
                            scale_protocol=sample.protocol,
                            scale_status=status, error="",
                        )
                    except ScaleNoResponseError as exc:
                        recovering = bool(self.capture_controller and self.capture_controller.interrupt_silence())
                        logger.warning("Consulta sem resposta; recuperação breve=%s", recovering)
                        self.state.update(scale_status="RECOVERING" if recovering else "ERROR", error=str(exc))
                    except ValidationError as exc:
                        logger.warning("Captura comercial recusada: %s", exc.messages)
                        self.state.update(scale_status="ERROR", error=" ".join(exc.messages))
                    except Exception as exc:
                        logger.exception("Falha de leitura")
                        if self.capture_controller:
                            self.capture_controller.reset()
                        self.state.update(scale_status="ERROR", error=str(exc))
                self.stop_event.wait(self.interval)
        finally:
            try:
                self.adapter.close()
            finally:
                self.state.update(scale_status="STOPPED")
                connections.close_all()
