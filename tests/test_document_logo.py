"""Optional logo uploads, immutable snapshots and raster transport contracts."""

import base64
from copy import deepcopy
from io import BytesIO
from threading import Event
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from PIL import Image

from apps.core.domain import DomainConflict
from apps.printing.documents import document_bold_lines, fingerprint, preview_parts, render_header, render_text
from apps.printing.logos import normalize_logo
from apps.printing.models import DocumentConfiguration
from apps.printing.selectors import draft_content
from apps.printing.services import save_document_configuration
from hardware.printer.escpos import encode_document
from hardware.printer.results import PrintFailure, PrintResult
from hardware.printer.windows_raw import WindowsRawPrinter
from runtime.print_worker import PrintWorker
from runtime.state import state
from tests.test_printing import PrintingFixture
from tests import test_slip_layout


def image_upload(size=(80, 40), color="black", format="PNG"):
    image = Image.new("RGBA" if format == "PNG" else "RGB", size, color)
    data = BytesIO()
    image.save(data, format=format)
    return SimpleUploadedFile("logo.png", data.getvalue(), content_type="image/png")


class LogoNormalizationTests(SimpleTestCase):
    def test_size_proportions_transparency_and_binary_raster(self):
        logo = normalize_logo(image_upload((800, 400)))
        self.assertEqual((logo["width"], logo["height"]), (384, 192))
        self.assertEqual(base64.b64decode(logo["raster_base64"]), b"\xff" * (48 * 192))
        white = normalize_logo(image_upload((7, 2), (0, 0, 0, 0)))
        self.assertEqual(base64.b64decode(white["raster_base64"]), b"\x00\x00")
        narrow = normalize_logo(image_upload((7, 2)))
        self.assertEqual(base64.b64decode(narrow["raster_base64"]), b"\xfe\xfe")
        with Image.open(BytesIO(base64.b64decode(logo["png_base64"]))) as normalized:
            self.assertEqual(normalized.mode, "1")
        self.assertEqual(normalize_logo(image_upload(format="JPEG"))["width"], 80)

    def test_invalid_format_file_size_and_dimensions(self):
        uploads = [SimpleUploadedFile("logo.png", b"not an image"),
                   SimpleUploadedFile("logo.png", b"x" * (2 * 1024 * 1024 + 1)),
                   image_upload(format="GIF"), image_upload((2001, 2000))]
        for upload in uploads:
            with self.assertRaises(ValidationError):
                normalize_logo(upload)

    def test_preview_logo_is_above_header_and_absence_has_no_placeholder(self):
        content = test_slip_layout.SlipLayoutTests().content()
        content["version"] = 7
        without = render_to_string("printing/slip.html", preview_parts(content))
        self.assertNotIn('class="slip-logo"', without)
        original = render_text(content)
        content["logo"] = normalize_logo(image_upload())
        with_logo = render_to_string("printing/slip.html", preview_parts(content))
        self.assertLess(with_logo.index('class="slip-logo"'), with_logo.index('class="slip-header'))
        self.assertEqual(render_text(content), original)

    def test_raster_framing_alignment_restoration_and_absent_payload(self):
        logo = normalize_logo(image_upload((7, 2)))
        payload = encode_document("Nome\nTexto\n", header_lines=1, header_scale=2, bold_lines=(1,), logo=logo)
        prefix = b"\x1b@\x1bt\x03\x1ba\x01\x1dv0\x00\x01\x00\x02\x00\xfe\xfe\x1ba\x00"
        self.assertTrue(payload.startswith(prefix + b"\x1d!\x11Nome\n\x1d!\x00"))
        self.assertIn(b"\x1bE\x01Texto\n\x1bE\x00", payload)
        self.assertEqual(encode_document("Texto\n"), encode_document("Texto\n", logo={}))
        for change in ({"width": 385}, {"height": 193}, {"width": True},
                       {"raster_base64": "!!!"}, {"raster_base64": "AA=="}):
            factory = Mock()
            with self.assertRaises(PrintFailure):
                WindowsRawPrinter(spooler_factory=factory).send("Texto\n", logo=logo | change)
            factory.assert_not_called()


class DocumentLogoTests(PrintingFixture, TestCase):
    def setUp(self):
        self.prepare()
        state.update(running=True)

    def tearDown(self):
        state.update(running=False)

    def save_logo(self, **kwargs):
        return save_document_configuration(header="Restaurante", footer="Obrigado!", expected_revision=1,
                                           logo=image_upload(), **kwargs)

    def test_upload_preserve_remove_and_stale_write(self):
        self.save_logo()
        stored = deepcopy(DocumentConfiguration.objects.get().logo)
        save_document_configuration(header="Novo nome", footer="", expected_revision=2)
        self.assertEqual(DocumentConfiguration.objects.get().logo, stored)
        with self.assertRaises(DomainConflict):
            save_document_configuration(header="Antigo", footer="", expected_revision=2, logo=image_upload(color="white"))
        self.assertEqual(DocumentConfiguration.objects.get().logo, stored)
        save_document_configuration(header="Novo nome", footer="", expected_revision=3, remove_logo=True)
        self.assertEqual(DocumentConfiguration.objects.get().logo, {})

    def test_upload_http_validation_preview_and_removal(self):
        url = reverse("document_configuration")
        self.assertContains(self.client.get(url), 'enctype="multipart/form-data"')
        values = {"header": "Restaurante", "footer": "", "expected_revision": 1}
        self.assertEqual(self.client.post(url, values | {"logo": image_upload()}).status_code, 302)
        self.assertContains(self.client.get(url), 'class="configured-logo"')
        self.assertContains(self.client.get(reverse("print_preview", args=[self.order.pk])), 'class="slip-logo"')
        self.assertEqual(self.client.post(url, values | {"expected_revision": 2, "logo": image_upload(),
                                                        "remove_logo": "on"}).status_code, 400)
        self.assertEqual(self.client.post(url, values | {"expected_revision": 2,
                                                        "logo": SimpleUploadedFile("bad.png", b"bad")}).status_code, 400)
        self.assertEqual(DocumentConfiguration.objects.get().revision, 2)
        self.assertEqual(self.client.post(url, values | {"expected_revision": 2, "remove_logo": "on"}).status_code, 302)
        self.assertNotContains(self.client.get(reverse("print_preview", args=[self.order.pk])), 'class="slip-logo"')

    def test_saved_logo_survives_removal_and_raw_worker_uses_snapshot(self):
        self.save_logo()
        job = self.finalize()
        frozen = deepcopy(job.document.content)
        save_document_configuration(header="Novo nome", footer="", expected_revision=2, remove_logo=True)
        self.assertEqual(job.document.content, frozen)
        self.assertContains(self.client.get(reverse("saved_document", args=[job.document_id])), 'class="slip-logo"')
        # Use a fake RAW delivery only; no Windows spooler is opened.
        job.delivery_mode, job.printer_name = "RAW", "test-only"
        job.save(update_fields=["delivery_mode", "printer_name"])
        adapter = Mock(send=Mock(return_value=PrintResult("SPOOL_ACCEPTED", "Fake", 7)))
        with patch("runtime.print_worker.WindowsRawPrinter", return_value=adapter):
            self.assertTrue(PrintWorker(Event(), delivery_mode="RAW").process_one())
        adapter.send.assert_called_once_with(render_text(frozen),
            header_lines=len(render_header(frozen).splitlines()), header_scale=2,
            bold_lines=document_bold_lines(frozen), logo=frozen["logo"])

    def test_logo_change_invalidates_reviewed_fingerprint(self):
        before = draft_content(self.order)
        self.save_logo()
        self.assertNotEqual(fingerprint(before), fingerprint(draft_content(self.order)))
