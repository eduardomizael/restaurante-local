"""Small thread-safe technical state; no ORM objects cross thread boundaries."""

from threading import RLock
import hmac


class RuntimeState:
    """Provide coherent snapshots to HTTP and the tray."""

    def __init__(self):
        self.lock = RLock()
        self._shutdown_handler = None
        self._browser_handler = None
        self._browser_token = None
        self.values = {
            "running": False, "paused": False, "weight_grams": 0,
            "live_weight_grams": 0,
            "scale_status": "STOPPED", "revision": 0,
            "mode": "SIMULATION", "error": "",
            "scale_mode": "SIMULATION", "print_mode": "PREVIEW",
            "scale_protocol": "",
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

    def bind_browser(self, handler, token):
        """Bind a private window-control capability from the explicit runtime."""
        with self.lock:
            self._browser_handler, self._browser_token = handler, token

    def unbind_browser(self, token):
        """Remove only the window control owned by this runtime."""
        with self.lock:
            if self._browser_token == token:
                self._browser_handler, self._browser_token = None, None

    def open_browser(self, token):
        """Reopen through the owner so it retains every browser process handle."""
        with self.lock:
            if (not self._browser_token or not isinstance(token, str) or not token.isascii()
                    or not hmac.compare_digest(token, self._browser_token)):
                raise PermissionError("Controle da janela não autorizado.")
            if not self.values["running"] or self._browser_handler is None:
                raise RuntimeError("Inicializador indisponível ou encerrando.")
            handler = self._browser_handler
        handler()


state = RuntimeState()
