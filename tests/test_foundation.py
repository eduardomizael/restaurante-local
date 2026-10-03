"""Runtime invariants without hardware, spooler or a visible browser."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import Mock, patch
from urllib.request import ProxyHandler, build_opener

from django.conf import settings
from django.test import Client, SimpleTestCase

from hardware.scale.simulator import SimulatedScale
from runtime.application import LocalApplication, validate_schema
from runtime.installation import read_installation
from runtime.instance_lock import InstanceLock
from runtime.scale_worker import ScaleWorker
from runtime.state import RuntimeState, state
from runtime.tray import run_tray


def free_port():
    """Choose a free loopback port for a short-lived test."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class StateAndWorkerTests(SimpleTestCase):
    def test_snapshots_do_not_mutate_shared_state(self):
        runtime_state = RuntimeState()
        snapshot = runtime_state.snapshot()
        snapshot["paused"] = True
        self.assertFalse(runtime_state.snapshot()["paused"])

    def test_pausing_rejects_stopped_runtime(self):
        with self.assertRaises(RuntimeError):
            RuntimeState().toggle_pause()

    def test_worker_continues_without_browser_and_closes_adapter(self):
        runtime_state = RuntimeState()
        runtime_state.update(running=True)
        adapter = SimulatedScale()
        stop = threading.Event()
        worker = ScaleWorker(adapter, runtime_state, stop, interval=0.005)
        worker.start()
        try:
            deadline = time.monotonic() + 1
            while adapter.index < 4 and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertGreaterEqual(adapter.index, 4)
            runtime_state.toggle_pause()
            time.sleep(0.02)
            index = adapter.index
            time.sleep(0.02)
            self.assertEqual(adapter.index, index)
        finally:
            stop.set()
            worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(adapter.closed)
        self.assertEqual(runtime_state.snapshot()["scale_status"], "STOPPED")

    def test_failure_is_visible_and_adapter_is_closed(self):
        adapter = Mock()
        adapter.read.side_effect = OSError("Desconectado")
        runtime_state = RuntimeState()
        stop = threading.Event()
        worker = ScaleWorker(adapter, runtime_state, stop, interval=1)
        with self.assertLogs("runtime.scale_worker", level="ERROR"):
            worker.start()
            deadline = time.monotonic() + 1
            while runtime_state.snapshot()["scale_status"] != "ERROR" and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(runtime_state.snapshot()["error"], "Desconectado")
            stop.set()
            worker.join(timeout=1)
        adapter.close.assert_called_once()


class HTTPTests(SimpleTestCase):
    def setUp(self):
        state.update(running=False, paused=False, scale_status="STOPPED", error="")

    def test_home_and_local_assets(self):
        response = self.client.get("/")
        self.assertContains(response, "ainda não criam medições comerciais")
        for name in ("app.css", "app.js", "htmx.min.js"):
            response = self.client.get(f"/assets/{name}")
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertEqual(self.client.get("/assets/installation.json").status_code, 404)

    def test_health_has_no_side_effect_and_reports_not_ready(self):
        revision = state.snapshot()["revision"]
        self.assertEqual(self.client.get("/health/").status_code, 503)
        self.assertEqual(state.snapshot()["revision"], revision)

    def test_mutation_requires_post_and_csrf(self):
        state.update(running=True)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get("/runtime/pause/").status_code, 405)
        self.assertEqual(client.post("/runtime/pause/").status_code, 403)
        client.get("/")
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post("/runtime/pause/", HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertTrue(state.snapshot()["paused"])
        state.update(running=False)
        self.assertEqual(client.post("/runtime/pause/", HTTP_X_CSRFTOKEN=token).status_code, 409)


class TrayTests(SimpleTestCase):
    def test_menu_controls_runtime_without_native_tray(self):
        state.update(running=True, paused=False)
        application = Mock(url="http://127.0.0.1:8765/")
        icon = Mock()
        pystray = Mock()
        pystray.Icon.return_value = icon
        pystray.Menu.side_effect = lambda *items: items
        pystray.MenuItem.side_effect = lambda label, action, **options: (label, action)

        def interact():
            menu = pystray.Icon.call_args.args[3]
            menu[0][1](icon, None)
            menu[1][1](icon, None)
            menu[2][1](icon, None)
            self.assertTrue(state.snapshot()["paused"])
            self.assertEqual(menu[2][0](None), "Retomar leitura")
            menu[3][1](icon, None)

        icon.run.side_effect = interact
        with patch.dict(sys.modules, {"pystray": pystray}):
            run_tray(application)
        application.request_stop.assert_called_once()
        application.browser_open.assert_any_call(application.url)
        application.browser_open.assert_any_call(application.url + "status/")
        self.assertTrue(icon.stop.called)

    def test_tray_failure_still_closes_icon(self):
        pystray = Mock()
        pystray.Icon.return_value.run.side_effect = RuntimeError("Bandeja indisponível")
        with patch.dict(sys.modules, {"pystray": pystray}):
            with self.assertRaises(RuntimeError):
                run_tray(Mock())
        pystray.Icon.return_value.stop.assert_called_once()


class RuntimeTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name)
        self.schema_patch = patch("runtime.application.validate_schema")
        self.schema_patch.start()
        self.thread_errors = patch("threading.excepthook")
        self.exception_hook = self.thread_errors.start()

    def tearDown(self):
        try:
            self.exception_hook.assert_not_called()
        finally:
            self.thread_errors.stop()
            self.schema_patch.stop()
            self.temporary.cleanup()

    def test_mutex_exclusion_and_release(self):
        first = InstanceLock(self.data_dir)
        second = InstanceLock(self.data_dir)
        self.assertTrue(first.acquire())
        try:
            self.assertFalse(second.acquire())
        finally:
            first.release()
        self.assertTrue(second.acquire())
        second.release()

    def test_server_readiness_duplicate_start_and_full_shutdown(self):
        browser = Mock()
        adapter = SimulatedScale()
        application = LocalApplication(
            self.data_dir, free_port(), browser_open=browser, adapter_factory=lambda: adapter,
        )
        try:
            self.assertTrue(application.start())
            browser.assert_called_once_with(application.url)
            opener = build_opener(ProxyHandler({}))
            with opener.open(application.url + "health/", timeout=1) as response:
                self.assertTrue(json.load(response)["ready"])
            duplicate = LocalApplication(self.data_dir, application.port, browser=False)
            self.assertFalse(duplicate.start())
            self.assertIsNone(duplicate.worker)
            duplicate.stop()
            self.assertTrue(state.snapshot()["running"])
            # Leave a keep-alive connection open to verify complete socket cleanup.
            import http.client

            connection = http.client.HTTPConnection("127.0.0.1", application.port, timeout=1)
            connection.request("GET", "/health/")
            connection.getresponse().read()
        finally:
            application.stop()
        connection.close()
        self.assertTrue(adapter.closed)
        self.assertFalse(application.worker.is_alive())
        self.assertFalse(application.server_thread.is_alive())
        self.assertFalse(application.server.dispatcher.threads)
        self.assertFalse((self.data_dir / "instance.json").exists())
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", application.port))

    def test_port_collision_releases_mutex_and_does_not_start_adapter(self):
        adapter_factory = Mock()
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            application = LocalApplication(
                self.data_dir, occupied.getsockname()[1], browser=False,
                adapter_factory=adapter_factory,
            )
            with self.assertRaises(OSError):
                application.start()
        adapter_factory.assert_not_called()
        self.assertFalse(application.owns_lock)
        lock = InstanceLock(self.data_dir)
        self.assertTrue(lock.acquire())
        lock.release()

    def test_partial_start_closes_http_and_releases_mutex(self):
        application = LocalApplication(self.data_dir, free_port(), browser=False,
                                       adapter_factory=Mock(side_effect=RuntimeError("Falha simulada")))
        with self.assertRaisesRegex(RuntimeError, "Falha simulada"):
            application.start()
        self.assertFalse(application.server_thread.is_alive())
        self.assertFalse(application.owns_lock)
        self.assertFalse(state.snapshot()["running"])

    def test_worker_start_failure_closes_unused_adapter(self):
        adapter = SimulatedScale()
        application = LocalApplication(self.data_dir, free_port(), browser=False,
                                       adapter_factory=lambda: adapter)
        with patch("runtime.application.ScaleWorker.start", side_effect=RuntimeError("Falha de thread")):
            with self.assertRaisesRegex(RuntimeError, "Falha de thread"):
                application.start()
        self.assertTrue(adapter.closed)
        self.assertFalse(application.server_thread.is_alive())
        self.assertFalse(application.owns_lock)

    def test_browser_opens_only_after_verified_readiness(self):
        browser = Mock()
        application = LocalApplication(self.data_dir, free_port(), browser_open=browser)
        with patch("runtime.application.probe_instance", side_effect=RuntimeError("Identidade incorreta")):
            with self.assertRaises(RuntimeError):
                application.start()
        browser.assert_not_called()
        self.assertIsNone(application.worker)
        self.assertFalse(application.owns_lock)

    def test_missing_database_is_not_created_at_startup(self):
        with self.assertRaisesRegex(RuntimeError, "Banco ausente"):
            validate_schema(self.data_dir)
        self.assertFalse((self.data_dir / "db.sqlite3").exists())

    def test_stuck_worker_keeps_mutex_until_it_can_stop(self):
        application = LocalApplication(self.data_dir, free_port(), browser=False)
        application.owns_lock = application.lock.acquire()
        application.worker = Mock(ident=1)
        application.worker.is_alive.return_value = True
        try:
            with self.assertRaisesRegex(RuntimeError, "Leitor não encerrou"):
                application.stop()
            self.assertTrue(application.owns_lock)
            self.assertFalse(InstanceLock(self.data_dir).acquire())
            self.assertTrue(application.stop_event.is_set())
        finally:
            application.worker.is_alive.return_value = False
            application.stop()


class InstallationTests(SimpleTestCase):
    def test_read_does_not_create_files_and_rejects_invalid_port(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.assertEqual(read_installation(path), {})
            self.assertEqual(list(path.iterdir()), [])
            (path / "installation.json").write_text(json.dumps({"port": True, "secret_key": "x" * 64}))
            with self.assertRaises(ValueError):
                read_installation(path)

    def test_explicit_installation_backup_schema_gate_and_process_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=directory,
                               DJANGO_SETTINGS_MODULE="config.settings")
            command = [sys.executable, "manage.py", "initialize_local", "--port", str(free_port())]
            for _ in range(2):
                result = subprocess.run(command, cwd=settings.BASE_DIR, env=environment,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            backups = list((Path(directory) / "backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "db.sqlite3").is_file())
            self.assertTrue((backups[0] / "installation.json").is_file())
            script = '''
import os, subprocess, sys
import django
django.setup()
from django.conf import settings
from django.db import connection
from runtime.application import LocalApplication, validate_schema
app = LocalApplication(settings.DATA_DIR, settings.INSTALLATION['port'], browser=False)
try:
    assert app.start()
    result = subprocess.run([sys.executable, 'manage.py', 'run_local', '--simulate', '--preview-print', '--no-tray', '--no-browser'], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([sys.executable, 'manage.py', 'initialize_local'], capture_output=True, timeout=10)
    assert result.returncode != 0
finally:
    app.stop()
with connection.cursor() as cursor:
    cursor.execute("DELETE FROM django_migrations WHERE app = 'contenttypes'")
try:
    validate_schema(settings.DATA_DIR)
except RuntimeError:
    pass
else:
    raise AssertionError('Missing migrations were accepted')
connection.close()
'''
            result = subprocess.run([sys.executable, "-c", script], cwd=settings.BASE_DIR,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
