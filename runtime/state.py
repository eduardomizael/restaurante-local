"""Small thread-safe technical state; no ORM objects cross thread boundaries."""

from threading import RLock


class RuntimeState:
    """Provide coherent snapshots to HTTP and the tray."""

    def __init__(self):
        self.lock = RLock()
        self._shutdown_handler = None
        self.values = {
            "running": False, "paused": False, "weight_grams": 0,
            "live_weight_grams": 0,
            "scale_status": "STOPPED", "revision": 0,
            "mode": "SIMULATION", "error": "",
            "scale_mode": "SIMULATION", "print_mode": "PREVIEW",
        }

    def update(self, **values):
        """Publish one atomic update.

        Args:
            **values: Technical state fields to update.
        """
        with self.lock:
            self.values.update(values)
            self.values["revision"] += 1

    def snapshot(self):
        """Return an independent state dictionary."""
        with self.lock:
            return dict(self.values)

    def toggle_pause(self):
        """Toggle reading only while the runtime accepts actions."""
        with self.lock:
            if not self.values["running"]:
                raise RuntimeError("Inicializador indisponível ou encerrando.")
            self.update(paused=not self.values["paused"])

    def bind_shutdown(self, handler):
        """Bind shutdown only from the explicitly started runtime."""
        with self.lock:
            self._shutdown_handler = handler

    def unbind_shutdown(self, handler):
        """Remove the owner without disturbing another runtime."""
        with self.lock:
            if self._shutdown_handler == handler:
                self._shutdown_handler = None

    def prepare_shutdown(self):
        """Reject mutations and return the stop signal for after HTTP delivery."""
        with self.lock:
            if not self.values["running"] or self._shutdown_handler is None:
                raise RuntimeError("Inicializador indisponível ou encerrando. Reabra o programa.")
            handler = self._shutdown_handler
            self._shutdown_handler = None
            self.update(running=False)
            return handler


state = RuntimeState()
