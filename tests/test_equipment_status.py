"""Equipment monitoring with injected transports; never touch real devices."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.selectors import equipment_status
from hardware.printer.availability import printer_availability
from hardware.printer.windows_raw import WindowsSpooler
from hardware.scale.protocol import ScaleNoResponseError
from hardware.scale.simulator import SimulatedScale
from runtime.application import LocalApplication
from runtime.printer_monitor import PrinterMonitor
from runtime.scale_worker import ScaleWorker
from runtime.state import RuntimeState, state


class PrinterAvailabilityTests(SimpleTestCase):
    def test_queue_conditions_and_read_only_probe(self):
        for flags, access, message in [
            (0, "AVAILABLE", "Fila acessível"),
            (0x200, "AVAILABLE", "Fila acessível"),  # Printing is not failure.
            (0x80, "UNAVAILABLE", "Offline"),
            (0x10 | 1, "UNAVAILABLE", "Sem papel"),
            (0x800000, "UNKNOWN", "não informou"),
        ]:
            spooler = Mock()
            spooler.status.return_value = flags
            result, detail = printer_availability("Comandas", spooler_factory=lambda: spooler)
            self.assertEqual(result, access)
            self.assertIn(message, detail)
            spooler.open.assert_called_once_with("Comandas")
            spooler.close.assert_called_once_with(spooler.open.return_value)
            spooler.start.assert_not_called()
            spooler.write.assert_not_called()

    def test_failed_status_query_still_closes_handle(self):
        spooler = Mock()
        spooler.status.side_effect = OSError("Falha")
        with self.assertRaises(OSError):
            printer_availability("Comandas", spooler_factory=lambda: spooler)
        spooler.close.assert_called_once()

    def test_native_status_uses_fixed_size_info_6(self):
        spooler = object.__new__(WindowsSpooler)
        spooler.api = Mock()
        def query(handle, level, buffer, size, needed):
            self.assertEqual(level, 6)
            self.assertEqual(size, 4)
            buffer._obj.value = 0x80
            return True
        spooler.api.GetPrinterW.side_effect = query
        self.assertEqual(spooler.status("handle"), 0x80)

    def test_monitor_waits_ten_seconds_and_tracks_configuration_changes(self):
        runtime = RuntimeState()
        stop = Mock()
        stop.is_set.side_effect = [False, False, False, False, True]
        probe = Mock(return_value=("AVAILABLE", "Fila acessível"))
        configuration = Mock(side_effect=[SimpleNamespace(printer_name="A"), SimpleNamespace(printer_name="B")])
        monitor = PrinterMonitor(runtime, stop, probe=probe, configuration=configuration)
        monitor.run()
        self.assertEqual(probe.call_args_list, [(("A",),), (("B",),)])
        self.assertEqual([call.args for call in stop.wait.call_args_list], [(10,), (10,)])
        self.assertEqual(runtime.snapshot()["printer_device"], "B")
        self.assertIsNotNone(runtime.snapshot()["printer_checked_at"])

    def test_probe_failure_can_recover_without_printing(self):
        runtime = RuntimeState()
        probe = Mock(side_effect=[OSError("Offline"), ("AVAILABLE", "Fila acessível")])
        monitor = PrinterMonitor(runtime, Event(), probe=probe,
                                 configuration=lambda: SimpleNamespace(printer_name="Comandas"))
        monitor.check_once()
        self.assertEqual(runtime.snapshot()["printer_access"], "UNAVAILABLE")
        monitor.check_once()
        self.assertEqual(runtime.snapshot()["printer_access"], "AVAILABLE")

    def test_shutdown_wakes_wait_without_waiting_for_next_check(self):
        stop = Event()
        probe = Mock(return_value=("AVAILABLE", "Fila acessível"))
        monitor = PrinterMonitor(RuntimeState(), stop, probe=probe,
                                 configuration=lambda: SimpleNamespace(printer_name="Comandas"))
        monitor.start()
        stop.set()
        monitor.join(timeout=1)
        self.assertFalse(monitor.is_alive())
        self.assertLessEqual(probe.call_count, 1)


class ScaleAvailabilityTests(SimpleTestCase):
    def run_read(self, *, failure=None, capture_failure=None):
        runtime = RuntimeState()
        adapter = SimulatedScale([0])
        adapter.port = "COM3"
        if failure:
            adapter.read = Mock(side_effect=failure)
        controller = Mock() if capture_failure else None
        if controller:
            controller.observe.side_effect = capture_failure
        stop = Mock()
        stop.is_set.side_effect = [False, False, True] if not failure else [False, True]
        with patch("runtime.scale_worker.logger"):
            ScaleWorker(adapter, runtime, stop, capture_controller=controller).run()
        return runtime.snapshot()

    def test_valid_response_is_independent_of_commercial_save_failure(self):
        for error in [ValidationError("Produto mudou"), OSError("Banco ocupado")]:
            snapshot = self.run_read(capture_failure=error)
            self.assertEqual(snapshot["scale_access"], "AVAILABLE")
            self.assertEqual(snapshot["scale_device"], "COM3")
            self.assertIsNotNone(snapshot["scale_last_response"])

    def test_silence_and_read_failure_do_not_show_connected(self):
        for error, expected in [(ScaleNoResponseError("Silêncio"), "NO_RESPONSE"),
                                (OSError("Porta ausente"), "UNAVAILABLE")]:
            snapshot = self.run_read(failure=error)
            self.assertEqual(snapshot["scale_access"], expected)
            self.assertIsNone(snapshot["scale_last_response"])

    def test_stale_paused_simulated_and_stopped_states(self):
        snapshot = RuntimeState().snapshot()
        snapshot.update(running=True, scale_mode="SERIAL", scale_access="AVAILABLE",
                        scale_last_response_tick=monotonic() - 20)
        self.assertEqual(equipment_status(snapshot, "scale")["label"], "Aguardando confirmação")
        snapshot["paused"] = True
        self.assertEqual(equipment_status(snapshot, "scale")["label"], "Leitura pausada")
        snapshot["paused"], snapshot["scale_mode"] = False, "SIMULATION"
        self.assertEqual(equipment_status(snapshot, "scale")["label"], "Modo simulado")
        snapshot["running"] = False
        self.assertEqual(equipment_status(snapshot, "scale")["label"], "Não verificado")

    def test_runtime_creates_no_printer_monitor_in_preview_mode(self):
        with TemporaryDirectory() as directory:
            application = LocalApplication(Path(directory), 8777, browser=False)
            self.assertIsNone(application.printer_monitor_factory(Event()))

    def test_stuck_monitor_keeps_installation_lock(self):
        with TemporaryDirectory() as directory:
            application = LocalApplication(Path(directory), 8777, browser=False)
            application.owns_lock = True
            application.printer_monitor = Mock(ident=1)
            application.printer_monitor.is_alive.return_value = True
            with patch.object(application.lock, "release") as release:
                with self.assertRaisesRegex(RuntimeError, "Consulta da impressora não encerrou"):
                    application.stop()
                release.assert_not_called()


class EquipmentStatusHTTPTests(TestCase):
    def setUp(self):
        self.original = state.snapshot()
        self.addCleanup(lambda: state.update(**self.original))
        state.update(running=True, scale_mode="SERIAL", print_mode="RAW", paused=False,
                     scale_access="AVAILABLE", scale_last_response_tick=monotonic(),
                     scale_last_response=datetime.now(timezone.utc), scale_device="COM3",
                     printer_access="UNAVAILABLE", printer_access_message="Sem papel",
                     printer_device="Comandas", printer_checked_tick=monotonic(),
                     printer_checked_at=datetime.now(timezone.utc))

    def test_repeated_http_requests_only_read_cached_equipment_results(self):
        with patch("hardware.printer.windows_raw.WindowsSpooler") as spooler, \
                patch("hardware.scale.serial_adapter.SerialScale.read") as serial, \
                patch("runtime.printer_monitor.PrinterMonitor.check_once") as probe:
            for _ in range(3):
                response = self.client.get(reverse("status_fragment"))
                self.assertContains(response, "Respondendo")
                self.assertContains(response, "COM3")
                self.assertContains(response, "Comandas")
                self.assertContains(response, "Sem papel")
            spooler.assert_not_called()
            serial.assert_not_called()
            probe.assert_not_called()
