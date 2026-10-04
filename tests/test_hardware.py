"""Real-protocol fixtures and fault-injected transports; never physical I/O."""

from threading import Event
from dataclasses import replace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.configuration.models import HardwareConfiguration
from apps.configuration.services import save_hardware_configuration
from apps.configuration.selectors import hardware_configuration
from apps.printing.documents import fingerprint, render_text, render_header
from apps.printing.models import PrintJob
from apps.printing.selectors import draft_content
from apps.printing.services import finalize_order, complete_job, claim_next_job
from apps.orders.services import open_order, add_product_item
from apps.products.services import save_product
from apps.core.domain import DomainConflict
from hardware.scale.protocol import FRAME_PREFIX, FRAME_SUFFIX, ScaleProtocolError, parse_frame
from hardware.scale.serial_adapter import SerialScale
from hardware.scale.sample import ScaleSample
from hardware.scale.cycle import CaptureCycle
from hardware.printer.escpos import encode_document
from hardware.printer.results import PrintFailure, PrintResult
from hardware.printer.windows_raw import WindowsRawPrinter
from runtime.configured_scale import ConfiguredSerialScale
from runtime.print_worker import PrintWorker
from runtime.state import state
from runtime.scale_capture import ScaleCaptureController
from apps.measurements.models import Measurement

# Complete frame observed from this installation on COM3, 03/10/2026.
ZERO_FRAME = bytes.fromhex(
    "08020303020301020014444154413a202030302f30302f30302056414c49442e3a2030302f30302f3030202020202020"
    "544152413a202020302e3030306b67202020202020205045534f204c3a2020302e3030306b6720202020202052242f6b"
    "673a202020202020302e3030202020202020544f54414c2052243a202020202020302e3030323030303030303030303030"
    "0309020103"
)


class ProtocolTests(SimpleTestCase):
    def test_real_complete_zero_frame_and_informative_tare(self):
        self.assertEqual(len(ZERO_FRAME), 150)
        sample = parse_frame(ZERO_FRAME, 10)
        self.assertEqual((sample.net_weight_grams, sample.tare_grams), (0, 0))
        frame = ZERO_FRAME.replace(b"TARA:   0.000", b"TARA:   0.100").replace(b"PESO L:  0.000", b"PESO L:  0.252")
        sample = parse_frame(frame, 10)
        self.assertEqual((sample.net_weight_grams, sample.tare_grams), (252, 100))

    def test_incomplete_extra_corrupt_and_ambiguous_frames_are_rejected(self):
        bad = [ZERO_FRAME[:-1], ZERO_FRAME + b"x", b"x" + ZERO_FRAME[1:],
               ZERO_FRAME.replace(b"TARA:", b"PESO:"), ZERO_FRAME.replace(b"PESO L:", b"TARA:  "),
               ZERO_FRAME.replace(b"PESO L:  0.000", b"PESO L: -0.100"),
               ZERO_FRAME.replace(b"PESO L:  0.000", b"PESO L:  0.xxx"),
               ZERO_FRAME.replace(b"TARA:   0.000", b"TARA:   ERROR")]
        for frame in bad:
            with self.subTest(frame=frame):
                with self.assertRaises(ScaleProtocolError):
                    parse_frame(frame, 10)

    def test_comma_precision_and_motion_are_not_false_stability(self):
        sample = parse_frame(ZERO_FRAME.replace(b"PESO L:  0.000", b"PESO L:  0,252"), 10)
        self.assertEqual(sample.net_weight_grams, 252)
        frame = ZERO_FRAME[:-17] + b"MOTION      " + FRAME_SUFFIX
        self.assertTrue(parse_frame(frame, 10).moving)


class SerialAdapterTests(SimpleTestCase):
    def connection(self, blocks):
        connection = Mock()
        connection.read.side_effect = blocks
        connection.write.return_value = 1
        connection.in_waiting = 0
        return connection

    def test_lazy_open_fragmented_frame_and_transport_profile(self):
        connection = self.connection([ZERO_FRAME[:20], ZERO_FRAME[20:90], ZERO_FRAME[90:]])
        factory = Mock(return_value=connection)
        adapter = SerialScale("com3", serial_factory=factory, clock=lambda: 10)
        factory.assert_not_called()
        sample = adapter.read()
        self.assertEqual(sample.device, "SERIAL:COM3")
        self.assertEqual(sample.sampled_at, 10)
        self.assertFalse(connection.rts)
        self.assertFalse(connection.dtr)
        self.assertEqual(connection.port, "COM3")
        factory.assert_called_once_with(port=None, baudrate=9600, bytesize=8, parity="N", stopbits=2,
                                        timeout=1, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False)
        connection.reset_input_buffer.assert_called_once()
        connection.write.assert_called_once_with(b"\x04")
        adapter.close()
        connection.close.assert_called_once()

    def test_timeout_disconnect_and_reconnect_close_old_handle(self):
        first = self.connection([ZERO_FRAME[:30], b""])
        second = self.connection([ZERO_FRAME])
        adapter = SerialScale(serial_factory=Mock(side_effect=[first, second]), clock=lambda: 10)
        with self.assertRaises(ScaleProtocolError):
            adapter.read()
        first.close.assert_called_once()
        self.assertEqual(adapter.read().net_weight_grams, 0)
        adapter.close()
        second.close.assert_called_once()
        with self.assertRaises(RuntimeError):
            adapter.read()

    def test_serial_open_write_and_extra_data_fail_cleanly(self):
        for operation in ("open", "write", "extra"):
            connection = self.connection([ZERO_FRAME])
            if operation == "extra":
                connection.in_waiting = 1
            else:
                getattr(connection, operation).side_effect = OSError("Falha serial")
            adapter = SerialScale(serial_factory=lambda **kwargs: connection, clock=lambda: 10)
            with self.assertRaises((OSError, ScaleProtocolError)):
                adapter.read()
            connection.close.assert_called_once()

    def test_deadline_bounds_fragmented_reads(self):
        connection = self.connection([ZERO_FRAME[:30]])
        clock = Mock(side_effect=[10, 10.1, 11.1])
        adapter = SerialScale(serial_factory=lambda **kwargs: connection, clock=clock)
        with self.assertRaises(ScaleProtocolError):
            adapter.read()
        self.assertEqual(connection.read.call_count, 1)

    def test_empty_reply_retries_once_without_reopening_or_refreshing_timestamp(self):
        connection = self.connection([b"", ZERO_FRAME])
        factory = Mock(return_value=connection)
        clock = Mock(side_effect=[10, 10.1, 11.1])
        adapter = SerialScale(serial_factory=factory, clock=clock)
        self.assertEqual(adapter.read().sampled_at, 10)
        self.assertEqual(connection.write.call_count, 2)
        factory.assert_called_once()
        connection.close.assert_not_called()
        adapter.close()

    def test_two_empty_replies_close_connection_and_do_not_retry_forever(self):
        connection = self.connection([b"", b""])
        adapter = SerialScale(serial_factory=lambda **kwargs: connection, clock=lambda: 10)
        with self.assertRaises(ScaleProtocolError):
            adapter.read()
        self.assertEqual(connection.write.call_count, 2)
        connection.close.assert_called_once()
        self.assertEqual(adapter.last_frame, b"")


class RawAdapterTests(SimpleTestCase):
    def spooler(self):
        spooler = Mock()
        spooler.open.return_value = "handle"
        spooler.start.return_value = 7
        spooler.write.side_effect = lambda handle, data: len(data)
        return spooler

    def test_cp860_payload_complete_text_feed_and_cut(self):
        text = "Refeição, açúcar, café\n" + ("Linha\n" * 80) + "FIM\n"
        payload = encode_document(text)
        self.assertTrue(payload.startswith(b"\x1b@\x1bt\x03"))
        self.assertIn(text.encode("cp860"), payload)
        self.assertTrue(payload.endswith(b"\n\n\n\x1dV\x00"))
        for value in ("emoji 😀", "Texto\x1b@", "Texto\x00"):
            with self.assertRaises(PrintFailure):
                encode_document(value)

    def test_lazy_spooler_partial_writes_and_acceptance(self):
        spooler = self.spooler()
        spooler.write.side_effect = lambda handle, data: min(10, len(data))
        factory = Mock(return_value=spooler)
        printer = WindowsRawPrinter("balanca", spooler_factory=factory)
        factory.assert_not_called()
        result = printer.send("Café\n")
        self.assertEqual(result.status, "SPOOL_ACCEPTED")
        self.assertEqual(result.spooler_job_id, 7)
        self.assertGreater(spooler.write.call_count, 1)
        spooler.open.assert_called_once_with("balanca")
        spooler.finish.assert_called_once_with("handle")
        spooler.close.assert_called_once_with("handle")

    def test_header_size_is_reset_before_body_and_legacy_payload_is_unchanged(self):
        payload = encode_document("Nome\nCabeçalho\nCOCA 7,00 [ ]\n", header_lines=2, header_scale=2)
        self.assertIn(b"\x1d!\x11" + "Nome\nCabeçalho\n".encode("cp860")
                      + b"\x1d!\x00COCA 7,00 [ ]\n", payload)
        self.assertNotIn(b"\x1d!", encode_document("Nome\nCOCA\n"))
        factory = Mock()
        with self.assertRaises(PrintFailure):
            WindowsRawPrinter(spooler_factory=factory).send("Nome\n", header_lines=3, header_scale=2)
        factory.assert_not_called()

    def test_failures_before_and_after_start_are_distinct(self):
        for stage in ("open", "start", "page", "write", "finish"):
            spooler = self.spooler()
            getattr(spooler, stage).side_effect = OSError("Falha RAW")
            printer = WindowsRawPrinter(spooler_factory=lambda: spooler)
            with self.assertRaises(PrintFailure if stage in ("open", "start") else OSError):
                printer.send("Documento\n")
            if stage != "open":
                spooler.close.assert_called_once_with("handle")
            if stage not in ("open", "start"):
                spooler.abort.assert_called_once_with("handle")

    def test_zero_write_and_close_failure_are_uncertain(self):
        spooler = self.spooler()
        spooler.write.side_effect = None
        spooler.write.return_value = 0
        with self.assertRaises(OSError):
            WindowsRawPrinter(spooler_factory=lambda: spooler).send("Documento\n")
        spooler = self.spooler()
        spooler.close.side_effect = OSError("Falha ao fechar")
        with self.assertRaises(OSError):
            WindowsRawPrinter(spooler_factory=lambda: spooler).send("Documento\n")

    def test_encoding_failure_never_opens_printer(self):
        factory = Mock()
        with self.assertRaises(PrintFailure):
            WindowsRawPrinter(spooler_factory=factory).send("😀")
        factory.assert_not_called()

    def test_diagnostic_without_flags_never_opens_hardware(self):
        with patch("apps.core.management.commands.diagnose_hardware.SerialScale") as scale:
            with patch("apps.core.management.commands.diagnose_hardware.WindowsRawPrinter") as printer:
                with self.assertRaises(CommandError):
                    call_command("diagnose_hardware")
                scale.assert_not_called()
                printer.assert_not_called()


class EquipmentAndDeliveryTests(TestCase):
    def setUp(self):
        state.update(running=True, print_mode="PREVIEW", scale_mode="SIMULATION")
        self.product = save_product(description="À vontade", unit="UN", unit_price_cents=3590)
        self.order = open_order(request_key=uuid4())
        add_product_item(order_id=self.order.pk, product_id=self.product.pk, quantity_units=1, request_key=uuid4())
        from apps.printing.services import save_document_configuration
        save_document_configuration(header="Teste", footer="Obrigado", expected_revision=0)

    def tearDown(self):
        state.update(running=False, print_mode="PREVIEW", scale_mode="SIMULATION")

    def finalize(self, mode):
        return finalize_order(order_id=self.order.pk, request_key=uuid4(), delivery_mode=mode,
                              expected_fingerprint=fingerprint(draft_content(self.order)))

    def test_parsed_physical_cycle_persists_once_and_preserves_capture_after_reset(self):
        save_product(description="Refeição", unit="KG", unit_price_cents=10000,
                     is_scale_product=True)
        controller = ScaleCaptureController(CaptureCycle(profile="US31_POP_S_PHYSICAL_PENDING_VALIDATION"))

        def observe(weight, moment):
            frame = ZERO_FRAME.replace(b"PESO L:  0.000", f"PESO L:  0.{weight:03d}".encode("ascii"))
            sample = replace(parse_frame(frame, moment), device="SERIAL:COM3")
            with patch("runtime.scale_capture.monotonic", return_value=moment):
                return controller.observe(sample)

        self.assertEqual(observe(0, 10), "MEASURING")
        for weight, moment in [(234, 11), (236, 12), (234, 13)]:
            observe(weight, moment)
        measurement = Measurement.objects.get()
        self.assertEqual((measurement.net_weight_grams, measurement.total_cents, measurement.device),
                         (234, 2340, "SERIAL:COM3"))
        self.assertEqual(measurement.stability_parameters["tolerance_grams"], 2)
        self.assertEqual(observe(236, 14), "WAITING_REMOVAL")
        self.assertEqual(Measurement.objects.count(), 1)
        controller.reset()
        self.assertEqual(observe(234, 15), "WAITING_ZERO")
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, "AVAILABLE")
        self.assertEqual(observe(0, 16), "MEASURING")
        for moment in (17, 18, 19):
            observe(236, moment)
        self.assertEqual(Measurement.objects.count(), 2)

    def test_configuration_get_is_read_only_validation_and_stale_edit(self):
        self.assertEqual(hardware_configuration().scale_port, "COM3")
        self.assertFalse(HardwareConfiguration.objects.exists())
        response = self.client.get(reverse("equipment_configuration"))
        self.assertContains(response, "Nome da fila")
        self.assertFalse(HardwareConfiguration.objects.exists())
        save_hardware_configuration(scale_port="com4", printer_name="Outra fila", expected_revision=0)
        with self.assertRaises(DomainConflict):
            save_hardware_configuration(scale_port="COM3", printer_name="balanca", expected_revision=0)
        for port in ("COM0", "../COM3", "COM3:123"):
            with self.assertRaises(ValidationError):
                save_hardware_configuration(scale_port=port, printer_name="balanca", expected_revision=1)

    def test_configuration_reload_closes_old_serial_adapter(self):
        factory = Mock(side_effect=[Mock(), Mock()])
        adapter = ConfiguredSerialScale(factory)
        adapter.read()
        first = adapter.adapter
        save_hardware_configuration(scale_port="COM4", printer_name="balanca", expected_revision=0)
        adapter.read()
        first.close.assert_called_once()
        self.assertEqual(factory.call_args.args, ("COM4",))
        adapter.close()

    def test_preview_jobs_are_never_claimed_by_raw_worker(self):
        job = self.finalize("PREVIEW")
        with patch("runtime.print_worker.WindowsRawPrinter") as factory:
            self.assertFalse(PrintWorker(Event(), delivery_mode="RAW").process_one())
            factory.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "PENDING")

    def test_raw_target_frozen_and_simulated_worker_cannot_claim_it(self):
        job = self.finalize("RAW")
        self.assertEqual(job.printer_name, "balanca")
        save_hardware_configuration(scale_port="COM3", printer_name="Outra fila", expected_revision=0)
        self.assertFalse(PrintWorker(Event()).process_one())
        raw = Mock(send=Mock(return_value=PrintResult("SPOOL_ACCEPTED", "Aceito", 7)))
        with patch("runtime.print_worker.WindowsRawPrinter", return_value=raw) as factory:
            self.assertTrue(PrintWorker(Event(), delivery_mode="RAW").process_one())
        factory.assert_called_once_with("balanca")
        raw.send.assert_called_once_with(render_text(job.document.content),
                                         header_lines=len(render_header(job.document.content).splitlines()),
                                         header_scale=2)
        job.refresh_from_db()
        self.assertEqual((job.status, job.spooler_job_id), ("SPOOL_ACCEPTED", 7))

    def test_raw_failure_is_persisted_without_resend(self):
        job = self.finalize("RAW")
        adapter = Mock(send=Mock(side_effect=OSError("Resultado incerto #7")))
        with patch("runtime.print_worker.WindowsRawPrinter", return_value=adapter):
            with patch("runtime.print_worker.logger"):
                worker = PrintWorker(Event(), delivery_mode="RAW")
                self.assertTrue(worker.process_one())
                self.assertFalse(worker.process_one())
        job.refresh_from_db()
        self.assertEqual(job.status, "UNKNOWN")
        adapter.send.assert_called_once()

    def test_simulated_job_cannot_record_spooler_acceptance(self):
        job = self.finalize("PREVIEW")
        claimed = claim_next_job()
        with self.assertRaises(ValidationError):
            complete_job(job_id=job.pk, attempt_key=claimed.attempt_key, status="SPOOL_ACCEPTED", message="", spooler_job_id=7)
        job.refresh_from_db()
        self.assertEqual(job.status, "SUBMITTING")

    def test_stale_print_mode_or_equipment_revision_requires_review(self):
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        data = response.context["form"].initial
        state.update(print_mode="RAW")
        self.assertEqual(self.client.post(reverse("finalize_order", args=[self.order.pk]), data).status_code, 409)
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        data = response.context["form"].initial
        save_hardware_configuration(scale_port="COM3", printer_name="Outra fila", expected_revision=0)
        self.assertEqual(self.client.post(reverse("finalize_order", args=[self.order.pk]), data).status_code, 409)
        self.assertFalse(PrintJob.objects.exists())

    def test_physical_ui_mode_is_explicit(self):
        state.update(scale_mode="SERIAL", print_mode="RAW")
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(response, "Balança real")
        self.assertContains(response, "Finalizar e imprimir comanda")
        self.assertNotContains(response, "Finalizar e simular impressão")
