"""Explicit runtime composition, readiness and bounded shutdown."""

import json
import logging
import time
import uuid
import webbrowser
from threading import Event, Thread
from urllib.request import ProxyHandler, build_opener

from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from hardware.scale.simulator import SimulatedScale
from runtime.instance_lock import InstanceLock
from runtime.http_server import LocalHTTPServer
from runtime.scale_worker import ScaleWorker
from runtime.scale_capture import ScaleCaptureController
from runtime.print_worker import PrintWorker
from runtime.configured_scale import ConfiguredSerialScale
from hardware.scale.cycle import CaptureCycle
from apps.printing.services import recover_interrupted_jobs
from runtime.state import state

logger = logging.getLogger(__name__)


def probe_instance(url, instance_id, timeout=5):
    """Wait for HTTP identity instead of assuming a bound port is ready.

    Args:
        url: Loopback base URL.
        instance_id: Expected runtime identity.
        timeout: Deadline in seconds.

    Raises:
        RuntimeError: The server is absent or its identity does not match.
    """
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with opener.open(url + "health/", timeout=0.5) as response:
                data = json.load(response)
            if data.get("instance_id") == instance_id and data.get("ready") is True:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise RuntimeError("Servidor local não confirmou a identidade e prontidão.")


def validate_schema(data_dir):
    """Reject missing database or pending migrations without applying them."""
    if not (data_dir / "db.sqlite3").is_file():
        raise RuntimeError("Banco ausente. Execute initialize_local antes de iniciar.")
    connection = connections["default"]
    try:
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise RuntimeError("Banco desatualizado. Execute initialize_local com o programa fechado.")
    finally:
        connection.close()


class LocalApplication:
    """Own one installation, server and explicit real/simulated transports."""

    def __init__(self, data_dir, port, *, browser=True, server_factory=LocalHTTPServer,
                 adapter_factory=None, browser_open=webbrowser.open, capture_factory=None,
                 print_worker_factory=None, simulate=True, preview_print=True):
        self.data_dir = data_dir
        self.port = port
        self.url = f"http://127.0.0.1:{port}/"
        self.browser = browser
        self.browser_open = browser_open
        self.server_factory = server_factory
        self.simulate, self.preview_print = simulate, preview_print
        self.adapter_factory = adapter_factory or (SimulatedScale if simulate else ConfiguredSerialScale)
        self.capture_factory = capture_factory or (lambda: ScaleCaptureController(CaptureCycle(
            profile="SIMULATION_ONLY" if simulate else "US31_POP_S_PHYSICAL_PENDING_VALIDATION")))
        self.print_worker_factory = print_worker_factory or (lambda event: PrintWorker(
            event, delivery_mode="PREVIEW" if preview_print else "RAW"))
        self.lock = InstanceLock(data_dir)
        self.stop_event = Event()
        self.server = None
        self.server_thread = None
        self.worker = None
        self.print_worker = None
        self.instance_id = uuid.uuid4().hex
        self.owns_lock = False
        self.started = False

    def start(self):
        """Start components, then publish readiness and open the browser.

        Returns:
            bool: False when a verified existing instance already owns the data.
        """
        if self.started or self.owns_lock:
            raise RuntimeError("Aplicação já iniciada.")
        self.owns_lock = self.lock.acquire()
        if not self.owns_lock:
            self._open_existing()
            return False
        try:
            validate_schema(self.data_dir)
            recover_interrupted_jobs()
            connections.close_all()
            from config.wsgi import application

            self.server = self.server_factory(
                application, host="127.0.0.1", port=self.port,
                threads=4, asyncore_loop_timeout=0.1,
            )
            state.update(running=True, paused=False, error="", instance_id=self.instance_id,
                         mode="SIMULATION" if self.simulate and self.preview_print else "HARDWARE",
                         scale_mode="SIMULATION" if self.simulate else "SERIAL",
                         print_mode="PREVIEW" if self.preview_print else "RAW")
            self.server_thread = Thread(target=self.server.run, name="local-http", daemon=True)
            self.server_thread.start()
            probe_instance(self.url, self.instance_id)
            capture_controller = self.capture_factory()
            self.worker = ScaleWorker(self.adapter_factory(), state, self.stop_event,
                                      capture_controller=capture_controller)
            self.worker.start()
            self.print_worker = self.print_worker_factory(self.stop_event)
            if self.print_worker is not None:
                self.print_worker.start()
            record = self.data_dir / "instance.json"
            temporary = record.with_suffix(".tmp")
            temporary.write_text(json.dumps({
                "port": self.port, "instance_id": self.instance_id,
            }), encoding="utf-8")
            temporary.replace(record)
            self.started = True
            if self.browser:
                self.browser_open(self.url)
            logger.info("Inicializador pronto em %s (serial=%s, impressão=%s)",
                        self.url, "simulada" if self.simulate else "real",
                        "simulada" if self.preview_print else "RAW")
            return True
        except BaseException:
            self.stop()
            raise

    def _open_existing(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                data = json.loads((self.data_dir / "instance.json").read_text(encoding="utf-8"))
                port = data["port"]
                identity = data["instance_id"]
                if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(identity, str):
                    raise ValueError("Registro de instância inválido")
                url = f"http://127.0.0.1:{port}/"
                probe_instance(url, identity, timeout=0.5)
                if self.browser:
                    self.browser_open(url)
                return
            except (OSError, ValueError, KeyError, RuntimeError):
                time.sleep(0.1)
        raise RuntimeError("Instância ocupada; não foi possível confirmar o servidor existente.")

    def request_stop(self):
        """Stop accepting actions before requesting component termination."""
        state.update(running=False)
        self.stop_event.set()

    def stop(self):
        """Close components before releasing exclusive installation ownership."""
        if not self.owns_lock:
            return
        self.request_stop()
        if self.worker is not None and self.worker.ident is not None:
            self.worker.join(timeout=3)
            if self.worker.is_alive():
                raise RuntimeError("Leitor não encerrou; mutex mantido até a saída do processo.")
        elif self.worker is not None:
            self.worker.adapter.close()
        if self.print_worker is not None and self.print_worker.ident is not None:
            self.print_worker.join(timeout=3)
            if self.print_worker.is_alive():
                raise RuntimeError("Impressão não encerrou; mutex mantido até a saída do processo.")
        elif self.print_worker is not None:
            self.print_worker.adapter.close()
        if self.server is not None:
            self.server.close()
        if self.server_thread is not None and self.server_thread.ident is not None:
            self.server_thread.join(timeout=3)
            if self.server_thread.is_alive():
                raise RuntimeError("HTTP não encerrou; mutex mantido até a saída do processo.")
        (self.data_dir / "instance.json").unlink(missing_ok=True)
        self.lock.release()
        self.owns_lock = False
        self.started = False
        logger.info("Inicializador encerrado")
