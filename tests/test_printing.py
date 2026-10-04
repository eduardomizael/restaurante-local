"""Frozen documents, SQLite races and simulated delivery recovery."""

from concurrent.futures import ThreadPoolExecutor
import os
import socket
import subprocess
import sys
import tempfile
from threading import Barrier, Event
from time import monotonic, sleep
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.domain import DomainConflict
from apps.measurements.models import Measurement
from apps.measurements.services import capture_measurement
from apps.orders.models import Order
from apps.orders.services import add_measurement_item, add_product_item, cancel_order, open_order, remove_item
from apps.products.services import save_product
from apps.printing.documents import fingerprint, render_text
from apps.printing.models import DocumentConfiguration, OrderDocument, PrintJob
from apps.printing.selectors import draft_content
from apps.printing.services import (
    claim_next_job, complete_job, finalize_order, recover_interrupted_jobs,
    request_reprint, save_document_configuration, print_open_order,
)
from hardware.printer.simulator import SimulatedPrinter, SimulatedPrintFailure
from runtime.print_worker import PrintWorker
from runtime.state import state


class PrintingFixture:
    def prepare(self):
        self.kg = save_product(description="Refeição por peso", unit="KG", unit_price_cents=5990,
                               is_scale_product=True)
        self.unit = save_product(description="À vontade", unit="UN", unit_price_cents=3590)
        self.marked = save_product(description="Bebida reservada", unit="UN", unit_price_cents=700,
                                  appears_on_order_slip=True, slip_order=10)
        self.order = open_order(request_key=uuid4())
        self.other = open_order(request_key=uuid4())
        self.measurements = [capture_measurement(capture_key=uuid4(), net_weight_grams=weight)
                             for weight in (252, 300, 400)]
        self.item = add_measurement_item(order_id=self.order.pk, measurement_id=self.measurements[0].pk,
                                         request_key=uuid4())
        add_product_item(order_id=self.order.pk, product_id=self.unit.pk, quantity_units=2, request_key=uuid4())
        self.configuration = save_document_configuration(header="Restaurante de teste", footer="Obrigado!",
                                                         expected_revision=0)

    def finalize(self, key=None):
        return finalize_order(order_id=self.order.pk, request_key=key or uuid4(),
                              expected_fingerprint=fingerprint(draft_content(self.order)))


class DocumentTests(PrintingFixture, TestCase):
    def setUp(self):
        self.prepare()

    def test_finalize_is_atomic_isolated_and_idempotent(self):
        reviewed = fingerprint(draft_content(self.order))
        key = uuid4()
        job = finalize_order(order_id=self.order.pk, request_key=key, expected_fingerprint=reviewed)
        self.assertEqual(finalize_order(order_id=self.order.pk, request_key=key,
                                        expected_fingerprint=reviewed).pk, job.pk)
        self.assertEqual(OrderDocument.objects.count(), 1)
        self.assertEqual(PrintJob.objects.count(), 1)
        self.order.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.FINALIZED)
        self.assertEqual(self.other.status, Order.Status.DRAFT)
        self.assertEqual(Measurement.objects.filter(status="AVAILABLE").count(), 2)
        self.assertEqual(Measurement.objects.get(pk=self.measurements[0].pk).status, "USED")
        for operation in (lambda: cancel_order(self.order.pk),
                          lambda: remove_item(order_id=self.order.pk, item_id=self.item.pk),
                          lambda: add_product_item(order_id=self.order.pk, product_id=self.unit.pk,
                                                   quantity_units=1, request_key=uuid4())):
            with self.assertRaises(DomainConflict):
                operation()
        with self.assertRaises(DomainConflict):
            finalize_order(order_id=self.other.pk, request_key=key, expected_fingerprint=reviewed)
        with self.assertRaises(DomainConflict):
            finalize_order(order_id=self.order.pk, request_key=key, expected_fingerprint="0" * 64)

    def test_failure_rolls_back_document_job_and_finalization(self):
        with patch("apps.printing.services.record_event", side_effect=RuntimeError("Falha de gravação")):
            with self.assertRaises(RuntimeError):
                self.finalize()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DRAFT)
        self.assertFalse(OrderDocument.objects.exists())
        self.assertFalse(PrintJob.objects.exists())

    def test_stale_preview_after_item_or_configuration_change(self):
        reviewed = fingerprint(draft_content(self.order))
        add_product_item(order_id=self.order.pk, product_id=self.unit.pk, quantity_units=1, request_key=uuid4())
        with self.assertRaises(DomainConflict):
            finalize_order(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=reviewed)
        reviewed = fingerprint(draft_content(self.order))
        save_document_configuration(header="Novo nome", footer="Novo rodapé", expected_revision=1)
        with self.assertRaises(DomainConflict):
            finalize_order(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=reviewed)
        self.assertFalse(PrintJob.objects.exists())

    def test_no_configuration_empty_order_or_cancelled_order_cannot_finalize(self):
        with self.assertRaises(ValidationError):
            finalize_order(order_id=self.other.pk, request_key=uuid4(),
                           expected_fingerprint=fingerprint(draft_content(self.other)))
        DocumentConfiguration.objects.all().delete()
        with self.assertRaises(ValidationError):
            self.finalize()
        cancel_order(self.order.pk)
        with self.assertRaises(DomainConflict):
            self.finalize()

    def test_union_manuscript_rows_and_historical_price_variants(self):
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=2, request_key=uuid4())
        save_product(product_id=self.marked.pk, expected_revision=1, description="Bebida nova",
                     unit="UN", unit_price_cents=800, appears_on_order_slip=True)
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=1, request_key=uuid4())
        add_measurement_item(order_id=self.order.pk, measurement_id=self.measurements[1].pk, request_key=uuid4())
        content = draft_content(self.order)
        self.assertEqual(len(content["items"]), 5)
        self.assertEqual(len(content["manuscript_rows"]), 1)
        unit_row = content["manuscript_rows"][0]
        self.assertEqual(unit_row["quantity_units"], 3)
        self.assertEqual([row["unit_price_cents"] for row in unit_row["variants"]], [700, 800])
        self.assertEqual([row["quantity_units"] for row in unit_row["variants"]], [2, 1])
        self.assertEqual(content["subtotal_cents"], 1509 + 1797 + 7180 + 1400 + 800)
        text = render_text(content)
        self.assertIn("0,252 kg", text)
        self.assertIn("0,300 kg", text)
        self.assertIn("Bebida reservada", text)
        self.assertNotIn("Já lançado: nenhum", text)
        self.assertIn("TOTAL A PAGAR", text)

    def test_saved_snapshot_survives_catalogue_and_configuration_edits(self):
        job = self.finalize()
        original = render_text(job.document.content)
        original_hash = job.document.fingerprint
        save_product(product_id=self.unit.pk, expected_revision=1, description="Outro produto",
                     unit="UN", unit_price_cents=9999, active=False)
        save_product(product_id=self.marked.pk, expected_revision=1, description="Bebida alterada",
                     unit="UN", unit_price_cents=2000, active=False)
        save_document_configuration(header="Outro estabelecimento", footer="Outro texto", expected_revision=1)
        job.document.refresh_from_db()
        self.assertEqual(render_text(job.document.content), original)
        self.assertEqual(fingerprint(job.document.content), original_hash)

    def test_compact_rows_keep_names_prices_and_marks_in_fixed_columns(self):
        content = draft_content(self.order)
        text = render_text(content)
        rows = [line for line in text.splitlines() if "[ ]" in line and not line.startswith("[X] =")]
        self.assertEqual(len(rows), 1)
        self.assertEqual({line.index("[ ]") for line in rows}, {28})
        self.assertTrue(all(line.count("[ ]") == 6 for line in rows))
        self.assertTrue(all(len(line) <= 48 for line in rows))
        self.assertTrue(any(line[:20].strip() == "Bebida reservada" and line[21:27].strip() == "7,00"
                            for line in rows))
        self.assertNotIn("Já lançado:", text)

    def test_meals_are_exclusive_to_top_section_even_when_marked_in_catalogue(self):
        save_product(product_id=self.unit.pk, expected_revision=1, description="REFEIÇÃO À VONTADE",
                     unit="UN", unit_price_cents=3990, appears_on_order_slip=True)
        add_product_item(order_id=self.order.pk, product_id=self.unit.pk, quantity_units=1, request_key=uuid4())
        content = draft_content(self.order)
        top, manual = render_text(content).split("PRODUTO")
        self.assertIn("Refeição por peso", top)
        self.assertIn("REFEIÇÃO À VONTADE", top)
        self.assertNotIn("Bebida reservada", top)
        self.assertNotIn("REFEIÇÃO À VONTADE", manual)
        self.assertNotIn("À vontade", manual)
        self.assertNotIn("Refeição por peso", manual)
        self.assertEqual(len(content["manuscript_rows"]), 1)

    def test_inserted_units_mark_boxes_and_preserve_total_without_duplicating_top_item(self):
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=2, request_key=uuid4())
        text = render_text(draft_content(self.order))
        top, manual = text.split("PRODUTO")
        self.assertNotIn("Bebida reservada", top)
        row = next(line for line in manual.splitlines() if line.startswith("Bebida reservada"))
        self.assertEqual(row[28:], "[X][X][ ][ ][ ][ ]")
        self.assertNotIn("Lançado:", manual)
        self.assertNotIn("14,00", manual)
        self.assertIn("SUBTOTAL REFEIÇÕES R$ 86,89", top)
        self.assertNotIn("SUBTOTAL PRÉ-INSERIDO", manual)

    def test_quantity_overflow_is_explicit_and_fits_paper_width(self):
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=9, request_key=uuid4())
        text = render_text(draft_content(self.order))
        row = next(line for line in text.splitlines() if line.startswith("Bebida reservada"))
        self.assertEqual(row[28:], "[X]" * 6)
        self.assertIn("Quantidade lançada: 9 UN", text)
        self.assertNotIn("Lançado: 9 UN · R$ 63,00", text)
        self.assertLessEqual(max(map(len, text.splitlines())), 48)

    def test_version_two_retains_separate_inserted_items_and_empty_mark_boxes(self):
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=2, request_key=uuid4())
        content = draft_content(self.order)
        content["version"] = 2
        text = render_text(content)
        top, manual = text.split("ACRÉSCIMOS MANUSCRITOS")
        self.assertIn("Bebida reservada", top)
        self.assertIn("Já lançado: 2 UN", manual)
        self.assertNotIn("[X]", text)

    def test_version_three_retains_values_below_marked_rows(self):
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=2, request_key=uuid4())
        content = draft_content(self.order)
        content["version"] = 3
        self.assertIn("Lançado: 2 UN · R$ 14,00", render_text(content))

    def test_open_print_is_idempotent_editable_and_can_be_followed_by_new_snapshot_and_closing(self):
        key, reviewed = uuid4(), fingerprint(draft_content(self.order))
        job = print_open_order(order_id=self.order.pk, request_key=key, expected_fingerprint=reviewed)
        self.assertEqual(print_open_order(order_id=self.order.pk, request_key=key,
                                         expected_fingerprint=reviewed).pk, job.pk)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "DRAFT")
        self.assertIsNone(self.order.finalized_at)
        self.assertFalse(job.document.is_final)
        original = render_text(job.document.content)
        self.assertNotIn("COMANDA ABERTA", original)
        self.assertIn(f"COMANDA #{self.order.number}", original)
        self.assertEqual(Measurement.objects.filter(status="AVAILABLE").count(), 2)
        PrintWorker(Event()).process_one()
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=2, request_key=uuid4())
        second = print_open_order(order_id=self.order.pk, request_key=uuid4(),
                                  expected_fingerprint=fingerprint(draft_content(self.order)))
        self.assertNotEqual(second.document_id, job.document_id)
        self.assertIn("[X][X]", render_text(second.document.content))
        job.document.refresh_from_db()
        self.assertEqual(render_text(job.document.content), original)
        PrintWorker(Event()).process_one()
        final = self.finalize()
        self.assertTrue(final.document.is_final)
        self.assertEqual(OrderDocument.objects.filter(order=self.order).count(), 3)
        self.assertEqual(OrderDocument.objects.filter(order=self.order, is_final=True).count(), 1)

    def test_open_print_rejects_stale_preview_duplicate_action_and_pending_new_print(self):
        reviewed = fingerprint(draft_content(self.order))
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=1, request_key=uuid4())
        with self.assertRaises(DomainConflict):
            print_open_order(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=reviewed)
        key, reviewed = uuid4(), fingerprint(draft_content(self.order))
        job = print_open_order(order_id=self.order.pk, request_key=key, expected_fingerprint=reviewed)
        for operation in (print_open_order, finalize_order):
            with self.assertRaises(DomainConflict):
                operation(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=reviewed)
        with self.assertRaises(DomainConflict):
            finalize_order(order_id=self.order.pk, request_key=key, expected_fingerprint=reviewed)
        self.assertEqual(PrintJob.objects.count(), 1)
        self.assertEqual(job.document.order.status, "DRAFT")

    def test_failed_open_print_transaction_rolls_back_and_order_can_cancel_after_success(self):
        values = dict(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=fingerprint(draft_content(self.order)))
        with patch("apps.printing.services.record_event", side_effect=RuntimeError("Falha")):
            with self.assertRaises(RuntimeError):
                print_open_order(**values)
        self.assertFalse(OrderDocument.objects.exists())
        self.assertFalse(PrintJob.objects.exists())
        job = print_open_order(**values)
        original = render_text(job.document.content)
        cancel_order(self.order.pk)
        job.document.refresh_from_db()
        self.assertEqual(render_text(job.document.content), original)
        self.assertEqual(Measurement.objects.get(pk=self.measurements[0].pk).status, "AVAILABLE")

    def test_long_name_continues_without_displacing_price_or_losing_text(self):
        save_product(description="SUCO DELL VALE LATA ESPECIAL", unit="UN", unit_price_cents=600,
                     appears_on_order_slip=True)
        content = draft_content(self.order)
        lines = render_text(content).splitlines()
        index = next(index for index, line in enumerate(lines) if line.startswith("SUCO DELL VALE"))
        self.assertEqual(lines[index][:20].strip(), "SUCO DELL VALE LATA")
        self.assertEqual(lines[index][21:27].strip(), "6,00")
        self.assertIn("[ ]", lines[index])
        self.assertEqual(lines[index + 1].strip(), "ESPECIAL")

    def test_legacy_document_retains_original_header_and_separate_mark_lines(self):
        content = draft_content(self.order)
        content["version"] = 1
        content.pop("layout")
        text = render_text(content)
        self.assertEqual(text.splitlines()[0], "Restaurante de teste".center(48))
        self.assertIn("Bebida reservada · R$ 7,00/UN", text)
        self.assertIn("Já lançado: nenhum", text)
        self.assertIn("[   ]", text)

    def test_large_prices_reserve_one_shared_width_without_truncation(self):
        save_product(description="Produto caro", unit="UN", unit_price_cents=123456789,
                     appears_on_order_slip=True)
        content = draft_content(self.order)
        rows = [line for line in render_text(content).splitlines() if "[ ]" in line and not line.startswith("[X] =")]
        self.assertEqual(content["layout"]["price_columns"], 10)
        self.assertEqual({line.index("[ ]") for line in rows}, {32})
        self.assertTrue(any("1234567,89" in line for line in rows))
        self.assertTrue(all(len(line) <= 48 for line in rows))

    def test_long_continuous_document_has_no_truncation(self):
        for index in range(70):
            save_product(description=f"Produto com descrição longa {index:03d} " + "especial " * 8,
                         unit="UN", unit_price_cents=100, appears_on_order_slip=True)
        text = render_text(self.finalize().document.content)
        self.assertGreater(len(text.splitlines()), 300)
        self.assertIn("069", text)
        self.assertIn("TOTAL A PAGAR", text)
        self.assertIn("Obrigado!", text)
        self.assertLessEqual(max(len(line) for line in text.splitlines()), 48)

    def test_configuration_validation_and_stale_revision(self):
        for values in ({"header": "", "footer": ""}, {"header": "Teste", "footer": "x" * 501},
                       {"header": "Teste\x1b", "footer": ""}):
            with self.assertRaises(ValidationError):
                save_document_configuration(**values, expected_revision=1)
        with self.assertRaises(DomainConflict):
            save_document_configuration(header="Teste", footer="", expected_revision=0)
        self.configuration.refresh_from_db()
        self.assertEqual(self.configuration.header, "Restaurante de teste")

    def test_database_rejects_duplicate_initial_and_invalid_status(self):
        job = self.finalize()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrintJob.objects.create(document=job.document, request_key=uuid4(), kind="INITIAL", status="PENDING")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrintJob.objects.filter(pk=job.pk).update(status="SIMULATED")


class PrintHTTPTests(PrintingFixture, TestCase):
    def setUp(self):
        self.prepare()
        state.update(running=True)

    def tearDown(self):
        state.update(running=False)

    def test_preview_get_does_not_finalize_and_post_returns_frozen_document(self):
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(response, "PRÉVIA DE RASCUNHO", html=False)
        self.assertContains(response, "TOTAL A PAGAR")
        self.assertFalse(OrderDocument.objects.exists())
        initial = response.context["form"].initial
        url = reverse("finalize_order", args=[self.order.pk])
        self.assertEqual(self.client.post(url, initial).status_code, 302)
        self.assertEqual(self.client.post(url, initial).status_code, 302)
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(response, "DOCUMENTO CONGELADO")
        self.assertContains(response, "Aguardando envio")
        self.assertContains(self.client.get(reverse("print_history")), "Comanda 1")

    def test_changed_preview_returns_conflict_without_finalizing(self):
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        remove_item(order_id=self.order.pk, item_id=self.item.pk)
        response = self.client.post(reverse("finalize_order", args=[self.order.pk]), response.context["form"].initial)
        self.assertContains(response, "mudaram após a prévia", status_code=409)
        self.assertFalse(PrintJob.objects.exists())

    def test_open_print_post_preserves_draft_and_frozen_history_link(self):
        preview = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(preview, "Simular impressão sem fechar")
        url = reverse("print_open_order", args=[self.order.pk])
        data = preview.context["form"].initial
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, data).status_code, 403)
        response = self.client.post(url, data)
        job = PrintJob.objects.get()
        self.assertRedirects(response, reverse("saved_document", args=[job.document_id]))
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "DRAFT")
        add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=2, request_key=uuid4())
        self.assertNotContains(self.client.get(reverse("saved_document", args=[job.document_id])), "[X][X]")
        fresh = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(fresh, "[X][X]")
        self.assertContains(fresh, "Ver última impressão")
        self.assertContains(self.client.get(reverse("print_history")), reverse("saved_document", args=[job.document_id]))

    def test_configuration_form_parses_and_preserves_stale_values(self):
        url = reverse("document_configuration")
        self.assertEqual(self.client.post(url, {"header": "Café & Restaurante", "footer": "Até breve!",
                                               "expected_revision": 1}).status_code, 302)
        self.assertEqual(self.client.post(url, {"header": "Obsoleto", "footer": "", "expected_revision": 1}).status_code, 409)
        self.assertEqual(self.client.post(url, {"header": "", "footer": "", "expected_revision": 2}).status_code, 400)

    def test_second_copy_requires_confirmation_and_reuses_exact_snapshot(self):
        job = self.finalize()
        PrintWorker(Event()).process_one()
        url = reverse("reprint_document", args=[job.document_id])
        response = self.client.get(url)
        self.assertContains(response, "SEGUNDA VIA")
        data = response.context["form"].initial | {"confirm": "True"}
        self.assertEqual(self.client.post(url, {"request_key": data["request_key"]}).status_code, 400)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(PrintJob.objects.count(), 2)
        response = self.client.get(reverse("print_jobs_fragment", args=[job.document_id]))
        self.assertContains(response, "Segunda via")

    def test_csrf_methods_shutdown_and_html_escaping(self):
        save_document_configuration(header="<script>texto</script>", footer="<b>Rodapé</b>", expected_revision=1)
        response = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(response, "&lt;script&gt;texto&lt;/script&gt;")
        url = reverse("finalize_order", args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, response.context["form"].initial).status_code, 403)
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        state.update(running=False)
        self.assertEqual(self.client.post(url, response.context["form"].initial).status_code, 503)


class QueueTests(PrintingFixture, TransactionTestCase):
    def setUp(self):
        self.prepare()

    def test_transport_receives_frozen_content_outside_transaction(self):
        job = self.finalize()
        def send(text):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(PrintJob.objects.get(pk=job.pk).status, "SUBMITTING")
            self.assertEqual(text, render_text(job.document.content))
            return "Simulado"
        adapter = Mock(send=Mock(side_effect=send))
        worker = PrintWorker(Event(), adapter)
        self.assertTrue(worker.process_one())
        self.assertFalse(worker.process_one())
        job.refresh_from_db()
        self.assertEqual(job.status, "SIMULATED")
        adapter.send.assert_called_once()

    def test_known_failure_and_uncertain_failure_never_auto_retry(self):
        for exception, expected in ((SimulatedPrintFailure("Antes do envio"), "FAILED"),
                                    (OSError("Após possível envio"), "UNKNOWN")):
            job = self.finalize() if not OrderDocument.objects.exists() else request_reprint(
                document_id=OrderDocument.objects.get().pk, request_key=uuid4())
            adapter = Mock(send=Mock(side_effect=exception))
            worker = PrintWorker(Event(), adapter)
            with patch("runtime.print_worker.logger"):
                self.assertTrue(worker.process_one())
            self.assertFalse(worker.process_one())
            job.refresh_from_db()
            self.assertEqual(job.status, expected)
            adapter.send.assert_called_once()

    def test_interrupted_claim_becomes_unknown_pending_continues(self):
        original = self.finalize()
        claimed = claim_next_job()
        self.assertEqual(claimed.pk, original.pk)
        # Reopen the SQLite connection as a restarted runtime would.
        connections.close_all()
        self.assertEqual(recover_interrupted_jobs(), 1)
        self.assertEqual(recover_interrupted_jobs(), 0)
        original.refresh_from_db()
        self.assertEqual(original.status, "UNKNOWN")
        worker = PrintWorker(Event())
        self.assertFalse(worker.process_one())
        key = uuid4()
        copy = request_reprint(document_id=original.document_id, request_key=key)
        self.assertEqual(request_reprint(document_id=original.document_id, request_key=key).pk, copy.pk)
        with self.assertRaises(DomainConflict):
            request_reprint(document_id=original.document_id, request_key=uuid4())
        connections.close_all()
        self.assertEqual(recover_interrupted_jobs(), 0)
        self.assertTrue(worker.process_one())
        copy.refresh_from_db()
        self.assertEqual(copy.status, "SIMULATED")

    def test_result_recording_failure_preserves_uncertainty_without_resend(self):
        job = self.finalize()
        adapter = Mock(send=Mock(return_value="Aceito em simulação"))
        worker = PrintWorker(Event(), adapter)
        with patch("runtime.print_worker.complete_job", side_effect=DomainConflict("Banco ocupado")):
            with self.assertRaises(DomainConflict):
                worker.process_one()
        self.assertFalse(worker.process_one())
        adapter.send.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, "SUBMITTING")
        recover_interrupted_jobs()
        job.refresh_from_db()
        self.assertEqual(job.status, "UNKNOWN")

    def test_completion_attempt_identity_and_second_copy_marker(self):
        original = self.finalize()
        claimed = claim_next_job()
        with self.assertRaises(DomainConflict):
            complete_job(job_id=claimed.pk, attempt_key=uuid4(), status="SIMULATED", message="")
        complete_job(job_id=claimed.pk, attempt_key=claimed.attempt_key, status="SIMULATED", message="")
        complete_job(job_id=claimed.pk, attempt_key=claimed.attempt_key, status="SIMULATED", message="")
        with self.assertRaises(DomainConflict):
            complete_job(job_id=claimed.pk, attempt_key=claimed.attempt_key, status="FAILED", message="")
        request_reprint(document_id=original.document_id, request_key=uuid4())
        adapter = Mock(send=Mock(return_value="Simulado"))
        PrintWorker(Event(), adapter).process_one()
        self.assertIn("SEGUNDA VIA", adapter.send.call_args.args[0])
        original.document.refresh_from_db()
        self.assertNotIn("SEGUNDA VIA", render_text(original.document.content))

    def test_real_worker_stops_closes_adapter_and_leaves_new_jobs_pending(self):
        job = self.finalize()
        stop = Event()
        adapter = SimulatedPrinter()
        worker = PrintWorker(stop, adapter, interval=0.01)
        with patch("threading.excepthook") as hook:
            worker.start()
            try:
                deadline = monotonic() + 3
                while monotonic() < deadline:
                    job.refresh_from_db()
                    if job.status == "SIMULATED":
                        break
                    sleep(0.01)
            finally:
                stop.set()
                worker.join(timeout=3)
            hook.assert_not_called()
        self.assertFalse(worker.is_alive())
        self.assertTrue(adapter.closed)
        self.assertEqual(job.status, "SIMULATED")
        copy = request_reprint(document_id=job.document_id, request_key=uuid4())
        self.assertFalse(worker.process_one())
        copy.refresh_from_db()
        self.assertEqual(copy.status, "PENDING")

    def race(self, *actions):
        barrier = Barrier(len(actions))
        def run(action):
            connections.close_all()
            try:
                barrier.wait(timeout=3)
                return action()
            except ValidationError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(actions)) as executor:
            return list(executor.map(run, actions))

    def test_two_finalizations_create_one_document_and_one_initial_job(self):
        reviewed = fingerprint(draft_content(self.order))
        results = self.race(*[lambda key=uuid4(): finalize_order(order_id=self.order.pk,
                             request_key=key, expected_fingerprint=reviewed) for _ in range(2)])
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(OrderDocument.objects.count(), 1)
        self.assertEqual(PrintJob.objects.count(), 1)

    def test_open_print_racing_closing_creates_only_one_pending_snapshot(self):
        reviewed = fingerprint(draft_content(self.order))
        results = self.race(lambda: print_open_order(order_id=self.order.pk, request_key=uuid4(),
                                                    expected_fingerprint=reviewed),
                            lambda: finalize_order(order_id=self.order.pk, request_key=uuid4(),
                                                    expected_fingerprint=reviewed))
        self.assertEqual(sum(result is not None for result in results), 1)
        document = OrderDocument.objects.get()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "FINALIZED" if document.is_final else "DRAFT")
        self.assertEqual(PrintJob.objects.count(), 1)

    def test_finalization_racing_cancellation_never_splits_document_and_order(self):
        reviewed = fingerprint(draft_content(self.order))
        self.race(lambda: finalize_order(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=reviewed),
                  lambda: cancel_order(self.order.pk))
        self.order.refresh_from_db()
        if self.order.status == "FINALIZED":
            self.assertEqual(OrderDocument.objects.count(), 1)
            self.assertEqual(Measurement.objects.get(pk=self.measurements[0].pk).status, "USED")
        else:
            self.assertEqual(self.order.status, "CANCELLED")
            self.assertFalse(OrderDocument.objects.exists())
            self.assertEqual(Measurement.objects.get(pk=self.measurements[0].pk).status, "AVAILABLE")

    def test_concurrent_claims_do_not_submit_same_job_twice(self):
        job = self.finalize()
        results = self.race(claim_next_job, claim_next_job)
        self.assertEqual(sum(result is not None for result in results), 1)
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)


class PrintRecoveryProcessTests(SimpleTestCase):
    def test_restart_recovers_interrupted_job_without_resubmitting(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=directory,
                               DJANGO_SETTINGS_MODULE="config.settings")
            install = subprocess.run([sys.executable, "manage.py", "initialize_local", "--port", str(port)],
                                     cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True, timeout=15)
            self.assertEqual(install.returncode, 0, install.stderr)
            prepare = '''
import django
django.setup()
from uuid import uuid4
from apps.products.services import save_product
from apps.orders.services import open_order, add_product_item
from apps.printing.services import save_document_configuration, finalize_order, claim_next_job
from apps.printing.documents import fingerprint
from apps.printing.selectors import draft_content
product = save_product(description='À vontade', unit='UN', unit_price_cents=3590)
order = open_order(request_key=uuid4())
add_product_item(order_id=order.pk, product_id=product.pk, quantity_units=1, request_key=uuid4())
save_document_configuration(header='Teste', footer='Fim', expected_revision=0)
finalize_order(order_id=order.pk, request_key=uuid4(), expected_fingerprint=fingerprint(draft_content(order)))
assert claim_next_job().status == 'SUBMITTING'
'''
            recover = '''
import django
django.setup()
from django.conf import settings
from django.db import connections
from apps.printing.models import PrintJob, OrderDocument
from apps.orders.models import Order
from runtime.application import LocalApplication
from hardware.printer.simulator import SimulatedPrinter
from runtime.print_worker import PrintWorker
from unittest.mock import Mock
from time import sleep
adapter = Mock(spec=SimulatedPrinter)
app = LocalApplication(settings.DATA_DIR, settings.INSTALLATION['port'], browser=False,
                       print_worker_factory=lambda event: PrintWorker(event, adapter, interval=0.01))
try:
    assert app.start()
    sleep(0.1)
    assert PrintJob.objects.get().status == 'UNKNOWN'
    assert Order.objects.get().status == 'FINALIZED'
    assert OrderDocument.objects.get().content['subtotal_cents'] == 3590
    adapter.send.assert_not_called()
finally:
    app.stop()
    connections.close_all()
assert not app.print_worker.is_alive()
adapter.close.assert_called_once()
'''
            for script in (prepare, recover):
                result = subprocess.run([sys.executable, "-c", script], cwd=settings.BASE_DIR,
                                        env=environment, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


class PrintingMigrationTests(PrintingFixture, TransactionTestCase):
    def test_existing_final_document_and_jobs_survive_schema_update(self):
        self.prepare()
        job = self.finalize()
        original = job.document.content
        previous = [("printing", "0002_remove_printjob_print_job_state_consistent_and_more")]
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(previous)
            legacy = executor.loader.project_state(previous).apps.get_model("printing", "OrderDocument")
            self.assertEqual(legacy.objects.get(pk=job.document_id).content, original)
        finally:
            MigrationExecutor(connection).migrate(latest)
        document = OrderDocument.objects.get(pk=job.document_id)
        self.assertTrue(document.is_final)
        self.assertEqual(document.content, original)
        self.assertEqual(document.fingerprint, fingerprint(original))
        self.assertEqual(PrintJob.objects.get(pk=job.pk).document_id, document.pk)
        configuration = DocumentConfiguration.objects.get(pk=1)
        self.assertEqual(configuration.logo, {})
        self.assertEqual((configuration.header, configuration.footer, configuration.revision),
                         ("Restaurante de teste", "Obrigado!", 1))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "FINALIZED")
