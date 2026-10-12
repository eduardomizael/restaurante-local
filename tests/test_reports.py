"""Opening-date totals, document versions and durable report delivery."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import add_product_item, cancel_order, open_order, remove_item
from apps.printing.documents import fingerprint
from apps.printing.models import PrintJob
from apps.printing.report_documents import render_report
from apps.printing.report_forms import PeriodForm
from apps.printing.report_selectors import order_report, totals_report
from apps.printing.report_services import request_report_print
from apps.printing.report_views import SNAPSHOT_SALT
from apps.printing.selectors import draft_content
from apps.printing.services import finalize_order, print_open_order, recover_interrupted_jobs, claim_next_job
from apps.products.services import save_product
from hardware.printer.escpos import encode_document
from hardware.printer.results import PrintFailure, PrintResult
from runtime.print_worker import PrintWorker
from runtime.state import state
from tests.test_printing import PrintingFixture


@override_settings(TIME_ZONE="America/Sao_Paulo")
class ReportTests(PrintingFixture, TestCase):
    def setUp(self):
        self.prepare()
        state.update(running=True, print_mode="PREVIEW")
        self.first, self.last = date(2026, 10, 1), date(2026, 10, 30)
        self.opened_at(self.order, "2026-10-01T00:00:00")
        self.opened_at(self.other, "2026-10-30T23:59:59")

    def tearDown(self):
        state.update(running=False, print_mode="PREVIEW")

    def opened_at(self, order, value):
        Order.objects.filter(pk=order.pk).update(created_at=timezone.make_aware(datetime.fromisoformat(value)))
        order.refresh_from_db()

    def reports(self, mode="period"):
        return totals_report(self.first, self.last, mode, "Restaurante de teste")

    def print_reports(self, reports=None, selection="all", key=None):
        return request_report_print(reports=reports or self.reports(), selection=selection,
                                    request_key=key or uuid4(), delivery_mode="PREVIEW", expected_printer_revision=0)

    def test_inclusive_local_opening_dates_and_all_statuses(self):
        self.finalize()
        cancelled = open_order(request_key=uuid4())
        self.opened_at(cancelled, "2026-10-15T12:00:00")
        cancel_order(order_id=cancelled.pk)
        for value in ("2026-09-30T23:59:59", "2026-10-31T00:00:00"):
            self.opened_at(open_order(request_key=uuid4()), value)
        report = self.reports()[0]
        self.assertEqual((report["opened"], report["closed"], report["cancelled"]), (1, 1, 1))
        self.assertEqual(order_report(self.first, self.last).count(), 3)
        # Date of finalization can lie outside the interval: opening is the criterion.
        self.assertEqual(report["total_cents"], 1509 + 7180)

    def test_items_use_historical_descriptions_quantities_and_amounts(self):
        removed = add_product_item(order_id=self.order.pk, product_id=self.marked.pk, quantity_units=5, request_key=uuid4())
        remove_item(order_id=self.order.pk, item_id=removed.pk)
        self.finalize()
        add_product_item(order_id=self.other.pk, product_id=self.unit.pk, quantity_units=20, request_key=uuid4())
        save_product(product_id=self.unit.pk, expected_revision=1, description="Nome novo", unit="UN", unit_price_cents=1, active=True)
        report = self.reports()[0]
        items = {item["description"]: item for item in report["items"]}
        self.assertEqual(items["À vontade"]["quantity"], 2)
        self.assertEqual(items["À vontade"]["total_cents"], 7180)
        self.assertEqual(items["Refeição por peso"]["weight"], 252)
        self.assertNotIn("Bebida reservada", items)
        self.assertNotIn("Nome novo", items)

    def test_daily_returns_thirty_reports_with_empty_days_and_matching_total(self):
        self.finalize()
        reports = self.reports("daily")
        self.assertEqual(len(reports), 30)
        self.assertEqual(reports[0]["closed"], 1)
        self.assertEqual(reports[-1]["opened"], 1)
        self.assertEqual(reports[1]["total_cents"], 0)
        self.assertEqual(reports[1]["items"], [])
        self.assertEqual(sum(row["total_cents"] for row in reports), self.reports()[0]["total_cents"])

    def test_versions_are_nested_once_and_never_duplicate_totals(self):
        job = print_open_order(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=fingerprint(draft_content(self.order)))
        PrintWorker(Event()).process_one()
        final = self.finalize()
        response = self.client.get(reverse("report_orders"), {"start": self.first, "end": self.last})
        self.assertEqual(response.context["page"].paginator.count, 2)
        self.assertContains(response, "Versão 1")
        self.assertContains(response, "Versão 2")
        for document_id in (job.document_id, final.document_id):
            self.assertContains(response, reverse("reprint_document", args=[document_id]))
            reprint = self.client.get(reverse("reprint_document", args=[document_id]))
            self.assertContains(reprint, reverse("saved_document", args=[document_id]))
        self.assertContains(response, "ainda não possui uma versão")
        self.assertEqual(self.reports()[0]["total_cents"], 8689)

    def test_period_validation_and_pagination(self):
        for data in ({"start": "2026-10-30", "end": "2026-10-01"}, {"start": "oops", "end": "2026-10-01"},
                     {"start": "2025-01-01", "end": "2026-10-30"}):
            self.assertFalse(PeriodForm(data).is_valid())
            response = self.client.get(reverse("report_totals"), data | {"mode": "daily"})
            self.assertEqual(response.context["reports"], [])
        for _ in range(25):
            self.opened_at(open_order(request_key=uuid4()), "2026-10-01T12:00:00")
        response = self.client.get(reverse("report_orders"), {"start": self.first, "end": self.last, "page": 2})
        self.assertEqual(len(response.context["page"]), 2)
        self.assertIn("start=2026-10-01", response.context["period_query"])
        self.assertRedirects(self.client.get(reverse("print_history")), reverse("report_orders"))

    def test_signed_preview_prints_exact_snapshot_after_orders_change(self):
        response = self.client.get(reverse("report_totals"), {"start": self.first, "end": self.last, "mode": "period"})
        data = response.context["print_form"].initial | {"confirm": True}
        self.finalize()
        result = self.client.post(reverse("report_print"), data)
        self.assertEqual(result.status_code, 302)
        job = PrintJob.objects.get(report_content__isnull=False)
        self.assertEqual(job.report_content["total_cents"], 0)
        self.assertEqual(job.report_content["opened"], 2)
        self.assertEqual(self.client.get(result.url).status_code, 200)
        self.assertContains(self.client.get(result.url), "01/10/2026 a 30/10/2026")
        self.assertEqual(self.client.post(reverse("report_print"), data).status_code, 302)
        self.assertEqual(PrintJob.objects.filter(report_content__isnull=False).count(), 1)

    def test_post_rejects_bad_expired_preview_csrf_shutdown_and_changed_mode(self):
        response = self.client.get(reverse("report_totals"))
        data = response.context["print_form"].initial | {"confirm": True}
        url = reverse("report_print")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, data).status_code, 403)
        self.assertEqual(self.client.post(url, data | {"snapshot": "tampered"}).status_code, 400)
        with patch("apps.printing.report_views.signing.loads", side_effect=signing.SignatureExpired):
            self.assertEqual(self.client.post(url, data).status_code, 400)
        self.assertEqual(self.client.post(url, data | {"selection": "-1"}).status_code, 409)
        state.update(print_mode="RAW")
        self.assertEqual(self.client.post(url, data).status_code, 409)
        state.update(running=False)
        self.assertEqual(self.client.post(url, data).status_code, 503)
        self.assertFalse(PrintJob.objects.exists())

    def test_single_day_then_all_is_idempotent_and_retry_conflicts(self):
        reports, key = self.reports("daily"), uuid4()
        self.print_reports(reports, "5", key)
        self.assertEqual(PrintJob.objects.get().report_content["start"], "2026-10-06")
        self.print_reports(reports, key=key)
        self.print_reports(reports, key=key)
        self.assertEqual(PrintJob.objects.count(), 30)
        reports[0]["total_cents"] = 1
        with self.assertRaises(ValidationError):
            self.print_reports(reports, key=key)
        self.assertEqual(PrintJob.objects.count(), 30)

    def test_worker_uses_shared_thermal_text_and_simulator(self):
        self.finalize()
        PrintWorker(Event()).process_one()
        reports = self.reports()
        text = render_report(reports[0])
        self.assertLessEqual(max(map(len, text.splitlines())), 48)
        self.assertIn("86,89", text)
        self.assertIn("0,252 kg", text)
        self.assertTrue(encode_document(text).endswith(b"\x1dV\x00"))
        self.print_reports(reports)
        with patch("runtime.print_worker.SimulatedPrinter") as adapter:
            adapter.return_value.send.return_value = "Simulado"
            self.assertTrue(PrintWorker(Event()).process_one())
            adapter.return_value.send.assert_called_once_with(text)
        self.assertEqual(PrintJob.objects.get(report_content__isnull=False).status, "SIMULATED")

    def test_raw_delivery_uses_configured_queue_and_rejects_stale_revision(self):
        from apps.configuration.selectors import hardware_configuration
        target = hardware_configuration()
        with self.assertRaises(ValidationError):
            request_report_print(reports=self.reports(), selection="all", request_key=uuid4(),
                                 delivery_mode="RAW", expected_printer_revision=target.revision + 1)
        request_report_print(reports=self.reports(), selection="all", request_key=uuid4(),
                             delivery_mode="RAW", expected_printer_revision=target.revision)
        with patch("runtime.print_worker.WindowsRawPrinter") as printer:
            printer.return_value.send.return_value = PrintResult("SPOOL_ACCEPTED", "Aceito", 42)
            self.assertTrue(PrintWorker(Event(), delivery_mode="RAW").process_one())
            printer.assert_called_once_with(target.printer_name)
            printer.return_value.close.assert_called_once()
        self.assertEqual(PrintJob.objects.get().spooler_job_id, 42)

    def test_failures_uncertainty_and_recovery_never_resend_automatically(self):
        key = self.print_reports()
        with patch("runtime.print_worker.SimulatedPrinter") as adapter:
            adapter.return_value.send.side_effect = PrintFailure("Falha confirmada")
            worker = PrintWorker(Event())
            worker.process_one()
            self.assertFalse(worker.process_one())
        self.assertEqual(PrintJob.objects.get().status, "FAILED")
        self.print_reports()
        job = claim_next_job()
        self.assertEqual(recover_interrupted_jobs(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "UNKNOWN")
        self.assertFalse(PrintWorker(Event()).process_one())
        response = self.client.get(reverse("report_print_result", args=[key]) + "?fragment=1")
        self.assertContains(response, "Falha confirmada")
        self.assertNotContains(response, 'hx-trigger=')

    def test_queue_constraint_requires_exactly_one_source(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrintJob.objects.create(request_key=uuid4(), kind="INITIAL")
        self.print_reports()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrintJob.objects.filter(report_content__isnull=False).update(report_batch_key=None)


class ReportQueueConcurrencyTests(TransactionTestCase):
    def test_sqlite_concurrent_batch_requests_and_claims_are_unique(self):
        reports = totals_report(date(2026, 10, 1), date(2026, 10, 2), "daily", "Teste")
        key = uuid4()

        def race(action):
            barrier = Barrier(2)

            def run(_):
                connections.close_all()
                try:
                    barrier.wait(timeout=5)
                    return action()
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(run, range(2)))

        results = race(lambda: request_report_print(reports=reports, selection="all", request_key=key,
                                                    delivery_mode="PREVIEW", expected_printer_revision=0))
        self.assertEqual(results, [key, key])
        self.assertEqual(PrintJob.objects.count(), 2)
        claimed = race(claim_next_job)
        self.assertEqual(len({job.pk for job in claimed}), 2)
        self.assertEqual(list(PrintJob.objects.values_list("attempts", flat=True)), [1, 1])
