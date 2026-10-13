"""Independent list orders, stale snapshots and serialized SQLite writes."""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.domain import DomainConflict
from apps.core.models import DomainEvent
from apps.orders.services import add_product_item, open_order
from apps.printing.documents import fingerprint
from apps.printing.models import OrderDocument
from apps.printing.selectors import draft_content
from apps.printing.services import claim_next_job, complete_job, print_open_order, request_reprint, save_document_configuration
from apps.products.models import Product
from apps.products.selectors import catalogue_snapshot, ordered_products, product_ordering_lists, quick_access_products
from apps.products.services import reorder_products, save_product, set_product_flag
from runtime.state import state


class OrderingFixture:
    def make_products(self):
        self.products = [save_product(
            description=name, unit="UN", unit_price_cents=500 + index,
            is_quick_access=True, appears_on_order_slip=True,
            quick_access_order=index, slip_order=index,
        ) for index, name in enumerate(("Suco", "Água", "Refrigerante"))]
        self.ids = [product.pk for product in self.products]

    def snapshot(self, kind):
        return next(item for item in product_ordering_lists() if item["kind"] == kind)

    def reorder(self, kind, ids, snapshot=None, **kwargs):
        snapshot = snapshot or self.snapshot(kind)
        return reorder_products(kind=kind, product_ids=ids,
                                expected_fingerprint=snapshot["fingerprint"], **kwargs)


class ProductOrderingTests(OrderingFixture, TestCase):
    def setUp(self):
        self.make_products()
        state.update(running=True)

    def tearDown(self):
        state.update(running=False)

    def post(self, kind="quick", ids=None, snapshot=None, htmx=True, **extra):
        snapshot = snapshot or self.snapshot(kind)
        data = {"kind": kind, "product_ids": json.dumps(self.ids if ids is None else ids),
                "expected_fingerprint": snapshot["fingerprint"], **extra}
        return self.client.post(reverse("update_product_order"), data,
                                **({"HTTP_HX_REQUEST": "true"} if htmx else {}))

    def test_orders_are_independent_and_reach_consumers(self):
        slip = self.snapshot("slip")
        self.reorder("quick", self.ids[::-1])
        self.assertEqual(list(quick_access_products().values_list("pk", flat=True)), self.ids[::-1])
        self.assertEqual(self.snapshot("slip")["fingerprint"], slip["fingerprint"])
        self.reorder("slip", [self.ids[1], self.ids[2], self.ids[0]], slip)
        order = open_order(request_key=uuid4())
        self.assertEqual([row["product_id"] for row in draft_content(order)["manuscript_rows"]],
                         [self.ids[1], self.ids[2], self.ids[0]])
        self.assertEqual(list(quick_access_products().values_list("pk", flat=True)), self.ids[::-1])
        self.assertEqual(Product.objects.get(pk=self.ids[0]).unit_price_cents, 500)

    def test_saved_content_is_frozen_and_new_preview_uses_new_order(self):
        save_document_configuration(header="Teste de ordenação", footer="", expected_revision=0)
        order = open_order(request_key=uuid4())
        add_product_item(order_id=order.pk, product_id=self.ids[0], quantity_units=1, request_key=uuid4())
        frozen = draft_content(order)
        job = print_open_order(order_id=order.pk, request_key=uuid4(), expected_fingerprint=fingerprint(frozen))
        claimed = claim_next_job("PREVIEW")
        complete_job(job_id=job.pk, attempt_key=claimed.attempt_key, status="SIMULATED", message="Teste")
        document = OrderDocument.objects.get(pk=job.document_id)
        saved_content = document.content
        self.reorder("slip", self.ids[::-1])
        document.refresh_from_db()
        self.assertEqual(document.content, saved_content)
        self.assertEqual([row["product_id"] for row in document.content["manuscript_rows"]], self.ids)
        self.assertEqual([row["product_id"] for row in draft_content(order)["manuscript_rows"]], self.ids[::-1])
        with self.assertRaisesMessage(DomainConflict, "Itens ou configuração mudaram"):
            print_open_order(order_id=order.pk, request_key=uuid4(), expected_fingerprint=fingerprint(frozen))
        reprint = request_reprint(document_id=document.pk, request_key=uuid4())
        self.assertEqual(reprint.document_id, document.pk)

    def test_ordering_subsection_is_separate_from_searchable_catalogue(self):
        inactive = save_product(description="Inativo", unit="UN", unit_price_cents=1, active=False,
                                is_quick_access=True, appears_on_order_slip=True)
        context = catalogue_snapshot("Suco")
        self.assertEqual([product.pk for product in context["products"]], self.ids[:1])
        self.assertNotIn("ordering_lists", context)
        for ordering in product_ordering_lists():
            self.assertEqual([product.pk for product in ordering["products"]], self.ids)
            self.assertNotIn(inactive.pk, json.loads(ordering["product_ids"]))
        response = self.client.get(reverse("catalogue"), {"q": "Suco"})
        self.assertNotContains(response, 'id="order-slip-list"')
        self.assertNotContains(response, 'sortable.min.js')
        self.assertContains(response, f'id="product-{self.ids[0]}"', count=1)
        self.assertNotContains(response, "<h3>Refrigerante</h3>", html=True)
        response = self.client.get(reverse("product_ordering"))
        self.assertContains(response, 'id="order-slip-list"', count=1)
        self.assertContains(response, 'id="order-quick-list"', count=1)
        self.assertContains(response, "<h3>Refrigerante</h3>", count=2, html=True)
        self.assertEqual(response.context["main_navigation_area"], "catalogue")
        self.assertContains(response, 'href="/products/ordering/" aria-current="page"')

    def test_catalogue_is_alphabetical_independently_of_both_saved_orders(self):
        extra = save_product(description="café", unit="UN", unit_price_cents=500)
        expected = [self.ids[1], extra.pk, self.ids[2], self.ids[0]]
        self.assertEqual([p.pk for p in catalogue_snapshot()["products"]], expected)
        self.reorder("quick", self.ids[::-1])
        self.reorder("slip", [self.ids[1], self.ids[0], self.ids[2]])
        response = self.client.get(reverse("catalogue"))
        self.assertEqual([p.pk for p in response.context["products"]], expected)

    def test_stale_order_and_changed_membership_return_authoritative_cards(self):
        initial = self.snapshot("quick")
        self.assertEqual(self.post(ids=self.ids[::-1], snapshot=initial).status_code, 200)
        response = self.post(ids=self.ids, snapshot=initial)
        self.assertContains(response, "Esta lista mudou em outra janela", status_code=409)
        self.assertEqual(response["X-Catalogue-Fragment"], "1")
        self.assertEqual([p.pk for p in response.context["ordering_lists"][1]["products"]], self.ids[::-1])
        current = self.snapshot("quick")
        self.products[1].refresh_from_db()
        set_product_flag(product_id=self.ids[1], flag="is_quick_access", enabled=False,
                         expected_revision=self.products[1].revision)
        self.assertEqual(self.post(snapshot=current).status_code, 409)

    def test_invalid_payloads_never_partially_write(self):
        for ids in (self.ids[:2], self.ids + [99999], [self.ids[0]] * 3,
                    [True, *self.ids[1:]], [str(self.ids[0]), *self.ids[1:]], {}, "bad"):
            with self.subTest(ids=ids):
                self.assertEqual(self.post(ids=ids).status_code, 400)
                self.assertEqual(list(ordered_products("quick").values_list("pk", flat=True)), self.ids)
        self.assertFalse(DomainEvent.objects.filter(kind="PRODUCT_LIST_REORDERED").exists())

    def test_write_failure_rolls_back_all_positions_and_revisions(self):
        with patch("apps.products.services.record_event", side_effect=RuntimeError("Injected failure")):
            with self.assertRaises(RuntimeError):
                self.reorder("quick", self.ids[::-1])
        self.assertEqual(list(ordered_products("quick").values_list("pk", flat=True)), self.ids)
        self.assertEqual(set(Product.objects.values_list("revision", flat=True)), {1})

    def test_changed_positions_invalidate_old_editor_revision(self):
        self.reorder("quick", self.ids[::-1])
        with self.assertRaises(DomainConflict):
            set_product_flag(product_id=self.ids[0], flag="is_meal", enabled=True, expected_revision=1)
        self.assertFalse(Product.objects.get(pk=self.ids[0]).is_meal)

    def test_buttons_work_without_javascript_and_return_to_subsection(self):
        response = self.post(move=f"{self.ids[0]}:down", htmx=False)
        self.assertRedirects(response, reverse("product_ordering"))
        self.assertEqual(list(ordered_products("quick").values_list("pk", flat=True)),
                         [self.ids[1], self.ids[0], self.ids[2]])
        response = self.post(ids=[self.ids[1], self.ids[0], self.ids[2]], move=f"{self.ids[0]}:up")
        self.assertContains(response, "Ordem salva.")
        self.assertEqual(list(ordered_products("quick").values_list("pk", flat=True)), self.ids)

    def test_invalid_moves_and_boundary_moves_are_safe(self):
        for move in ("bad", "99999:up", f"{self.ids[0]}:sideways"):
            self.assertEqual(self.post(move=move).status_code, 400)
        self.assertEqual(self.post(move=f"{self.ids[0]}:up").status_code, 200)
        self.assertEqual(list(ordered_products("quick").values_list("pk", flat=True)), self.ids)

    def test_post_csrf_runtime_and_local_assets(self):
        url = reverse("update_product_order")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, {}).status_code, 403)
        state.update(running=False)
        self.assertEqual(self.post().status_code, 503)
        for asset in ("sortable.min.js", "product-order.js"):
            response = self.client.get(reverse("asset", args=[asset]))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b"".join(response.streaming_content))


class ProductOrderingConcurrencyTests(OrderingFixture, TransactionTestCase):
    def test_same_snapshot_cannot_overwrite_a_concurrent_reorder(self):
        self.make_products()
        snapshot = self.snapshot("quick")
        barrier = Barrier(2)

        def attempt(ids):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                self.reorder("quick", ids, snapshot)
                return "saved"
            except DomainConflict:
                return "conflict"
            finally:
                close_old_connections()

        alternatives = [self.ids[::-1], [self.ids[1], self.ids[2], self.ids[0]]]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, alternatives))
        self.assertCountEqual(outcomes, ["saved", "conflict"])
        self.assertIn(list(ordered_products("quick").values_list("pk", flat=True)), alternatives)
        self.assertEqual(DomainEvent.objects.filter(kind="PRODUCT_LIST_REORDERED").count(), 1)
