"""Protocol selection and signed physical capture without real serial I/O."""

from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.configuration.selectors import hardware_configuration
from apps.configuration.services import save_hardware_configuration
from apps.core.domain import DomainConflict
from apps.measurements.models import Measurement
from apps.products.services import save_product
from hardware.scale.cycle import CaptureCycle
from hardware.scale.protocol import ScaleProtocolError, parse_prot_f_frame
from hardware.scale.serial_adapter import ProtFScale, SerialScale, create_scale_adapter
from runtime.configured_scale import ConfiguredSerialScale
from runtime.scale_capture import ScaleCaptureController
from runtime.state import state


class ProtFProtocolTests(SimpleTestCase):
    def test_observed_signed_frames_and_instability(self):
        for frame, weight in ((b"\x02 00.396\x03", 396), (b"\x02-00.494\x03", -494),
                              (b"\x02+00.002\x03", 2)):
            sample = parse_prot_f_frame(frame, 10)
            self.assertEqual(sample.net_weight_grams, weight)
            self.assertIsNone(sample.tare_grams)
            self.assertFalse(sample.moving)
            self.assertEqual(sample.protocol, "PROT_F")
        self.assertTrue(parse_prot_f_frame(b"\x02IIIIII\x03", 10).moving)

    def test_unknown_fault_overload_precision_and_extra_bytes_are_rejected(self):
        for frame in (b"\x02SSSSSS\x03", b"\x02 00.396", b"\x02 0.396\x03",
                      b"\x02 00,396\x03", b"\x02 00.396\x03extra", b"garbage"):
            with self.subTest(frame=frame), self.assertRaises(ScaleProtocolError):
                parse_prot_f_frame(frame, 10)

    def test_readers_are_lazy_and_protocol_specific(self):
        self.assertIsInstance(create_scale_adapter("COM3", protocol="USECB2"), SerialScale)
        reader = create_scale_adapter("COM3", protocol="PROT_F")
        self.assertIsInstance(reader, ProtFScale)
        self.assertIsNone(reader.connection)
        with self.assertRaises(ValueError):
            create_scale_adapter("COM3", protocol="UNKNOWN")

    def test_fragmented_weights_and_short_motion_frame_do_not_wait_for_nine_bytes(self):
        for frame in (b"\x02-00.494\x03", b"\x02IIIIII\x03"):
            connection = Mock(in_waiting=0)
            connection.write.return_value = 1
            connection.read.side_effect = [bytes([value]) for value in frame]
            adapter = ProtFScale(serial_factory=Mock(return_value=connection), clock=lambda: 10)
            sample = adapter.read()
            self.assertEqual(sample.protocol, "PROT_F")
            self.assertEqual(connection.read.call_count, len(frame))
            self.assertEqual(sample.device, "SERIAL:COM3:PROT_F")
            connection.write.assert_called_once_with(b"\x04")
            adapter.close()
            connection.close.assert_called_once()


class ProtocolConfigurationTests(TestCase):
    def setUp(self):
        state.update(running=True)

    def tearDown(self):
        state.update(running=False)

    def test_selection_is_saved_by_http_and_preserved_by_other_equipment_edits(self):
        self.assertEqual(hardware_configuration().scale_protocol, "USECB2")
        page = self.client.get(reverse("equipment_configuration"))
        self.assertContains(page, 'name="scale_protocol"')
        self.assertContains(page, 'value="PROT_F"')
        response = self.client.post(reverse("equipment_configuration"), {
            "scale_port": "COM3", "scale_protocol": "PROT_F", "printer_name": "balanca", "expected_revision": 0,
        })
        self.assertEqual(response.status_code, 302)
        save_hardware_configuration(scale_port="COM4", printer_name="balanca", expected_revision=1)
        self.assertEqual(hardware_configuration().scale_protocol, "PROT_F")
        with self.assertRaises(DomainConflict):
            save_hardware_configuration(scale_port="COM3", printer_name="balanca", expected_revision=1,
                                        scale_protocol="USECB2")
        with self.assertRaises(ValidationError):
            save_hardware_configuration(scale_port="COM3", printer_name="balanca", expected_revision=2,
                                        scale_protocol="UNKNOWN")
        self.assertEqual(hardware_configuration().scale_protocol, "PROT_F")

    def test_protocol_switch_replaces_reader_on_next_query_and_closes_previous(self):
        factory = Mock(side_effect=[Mock(), Mock()])
        adapter = ConfiguredSerialScale(factory)
        adapter.read()
        old = adapter.adapter
        factory.assert_called_with("COM3", protocol="USECB2")
        save_hardware_configuration(scale_port="COM3", printer_name="balanca", expected_revision=0,
                                    scale_protocol="PROT_F")
        old.close.assert_not_called()
        adapter.read()
        old.close.assert_called_once()
        factory.assert_called_with("COM3", protocol="PROT_F")
        adapter.close()


class ProtFCaptureTests(TestCase):
    def setUp(self):
        save_product(description="Refeição", unit="KG", unit_price_cents=5000, is_scale_product=True)
        self.controller = ScaleCaptureController(CaptureCycle(
            zero_grams=2, zero_sample_count=3, minimum_grams=40, maximum_silence_seconds=5))
        self.moment = 0

    def observe(self, frame):
        self.moment += .5
        sample = parse_prot_f_frame(frame, self.moment)
        with patch("runtime.scale_capture.monotonic", return_value=self.moment):
            return self.controller.observe(sample)

    def test_negative_removal_positive_capture_and_unknown_tare_without_duplication(self):
        for frame in (b"\x02-00.494\x03", b"\x02-00.496\x03", b"\x02-00.494\x03"):
            result = self.observe(frame)
        self.assertEqual(result, "MEASURING")
        for _ in range(3):
            result = self.observe(b"\x02 00.396\x03")
        self.assertEqual(result, "WAITING_REMOVAL")
        measurement = Measurement.objects.get()
        self.assertEqual((measurement.net_weight_grams, measurement.total_cents), (396, 1980))
        self.assertIsNone(measurement.tare_grams)
        self.assertEqual(measurement.stability_parameters["protocol"], "PROT_F")
        for _ in range(3):
            self.observe(b"\x02 00.500\x03")
        self.assertEqual(Measurement.objects.count(), 1)
        for _ in range(3):
            self.observe(b"\x02-00.494\x03")
        for _ in range(3):
            self.observe(b"\x02 00.350\x03")
        self.assertEqual(Measurement.objects.count(), 2)

    def test_changing_negative_weights_and_motion_do_not_arm(self):
        for frame in (b"\x02-00.100\x03", b"\x02-00.200\x03", b"\x02-00.300\x03",
                      b"\x02IIIIII\x03", b"\x02 00.396\x03", b"\x02 00.396\x03",
                      b"\x02 00.396\x03"):
            self.assertEqual(self.observe(frame), "WAITING_ZERO")
        self.assertFalse(Measurement.objects.exists())

    def test_motion_discards_commercial_stability_samples(self):
        for _ in range(3):
            self.observe(b"\x02-00.494\x03")
        for _ in range(2):
            self.observe(b"\x02 00.396\x03")
        self.observe(b"\x02IIIIII\x03")
        for _ in range(2):
            self.observe(b"\x02 00.396\x03")
        self.assertFalse(Measurement.objects.exists())
        self.observe(b"\x02 00.396\x03")
        self.assertEqual(Measurement.objects.count(), 1)
