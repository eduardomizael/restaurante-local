"""Live-reading worker; commercial capture belongs to the next increment."""

import logging
from threading import Thread

logger = logging.getLogger(__name__)


class ScaleWorker(Thread):
    """Read an injected adapter, independently of browser lifetime."""

    def __init__(self, adapter, state, stop_event, interval=0.5):
        super().__init__(name="scale-worker", daemon=True)
        self.adapter = adapter
        self.state = state
        self.stop_event = stop_event
        self.interval = interval

    def run(self):
        """Read until shutdown, always closing the adapter."""
        try:
            while not self.stop_event.is_set():
                if self.state.snapshot()["paused"]:
                    self.state.update(scale_status="PAUSED")
                else:
                    try:
                        sample = self.adapter.read()
                        self.state.update(
                            weight_grams=sample.net_weight_grams,
                            scale_status="SIMULATED", error="",
                        )
                    except Exception as exc:
                        logger.exception("Falha de leitura")
                        self.state.update(scale_status="ERROR", error=str(exc))
                self.stop_event.wait(self.interval)
        finally:
            try:
                self.adapter.close()
            finally:
                self.state.update(scale_status="STOPPED")
