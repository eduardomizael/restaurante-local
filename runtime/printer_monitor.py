"""One low-frequency printer check, independent of HTTP and print delivery."""

from datetime import datetime, timezone
from threading import Thread
from time import monotonic

from django.db import close_old_connections, connections

from apps.configuration.selectors import hardware_configuration
from hardware.printer.availability import printer_availability


class PrinterMonitor(Thread):
    """Check once per ten seconds, never spawning parallel probes or printing."""

    def __init__(self, state, stop_event, *, probe=printer_availability,
                 configuration=hardware_configuration, interval=10):
        super().__init__(name="printer-monitor", daemon=True)
        self.state, self.stop_event = state, stop_event
        self.probe, self.configuration, self.interval = probe, configuration, interval

    def check_once(self):
        """Publish a cached result; failures do not interrupt the print worker."""
        name = ""
        try:
            name = self.configuration().printer_name
            access, message = self.probe(name)
        except Exception:
            access, message = "UNAVAILABLE", "Não foi possível consultar a impressora configurada."
        if not self.stop_event.is_set():
            self.state.update(printer_access=access, printer_access_message=message,
                              printer_device=name, printer_checked_at=datetime.now(timezone.utc),
                              printer_checked_tick=monotonic())

    def run(self):
        """Wait between completed checks and close this thread's DB connection."""
        try:
            while not self.stop_event.is_set():
                close_old_connections()
                self.check_once()
                connections.close_all()
                self.stop_event.wait(self.interval)
        finally:
            connections.close_all()
