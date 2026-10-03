"""Small thread-safe technical state; no ORM objects cross thread boundaries."""

from threading import RLock


class RuntimeState:
    """Provide coherent snapshots to HTTP and the tray."""

    def __init__(self):
        self.lock = RLock()
        self.values = {
            "running": False, "paused": False, "weight_grams": 0,
            "scale_status": "STOPPED", "revision": 0,
            "mode": "SIMULATION", "error": "",
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


state = RuntimeState()
