"""Individual capture corrections, exact prices, stale dialogs and SQLite races."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.domain import DomainConflict
from apps.core.models import DomainEvent
from apps.measurements.models import Measurement
from apps.measurements.services import capture_measurement, change_measurement_product, discard_measurement
from apps.orders.models import OrderItem
from apps.orders.services import add_measurement_item, open_order, remove_item
from apps.products.models import Product
from apps.products.services import save_product
from runtime.state import state


class MeasurementProductTests(TestCase):
    def setUp(self):
        state.update(running=True)
        self.scale = save_product(description="Comum", unit="KG", unit_price_cents=5000, is_scale_product=True)
        self.special = save_product(description="Especial", unit="KG", unit_price_cents=5990)
        self.drink = save_product(description="Suco", unit="UN", unit_price_cents=500)
        self.inactive = save_product(description="Inativo", unit="KG", unit_price_cents=7000, active=False)
        self.measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=250, tare_grams=300)
        self.other = capture_measurement(capture_key=uuid4(), net_weight_grams=400)
        self.order = open_order(request_key=uuid4())
        self.url = reverse("measurement_product", args=[self.measurement.pk])
        self.data = {"product_id": self.special.pk, "expected_revision": 1, "expected_product_revision": 1}

    def tearDown(self):
        state.update(running=False)

    def change(self, **overrides):
        return change_measurement_product(measurement_id=self.measurement.pk, **(self.data | overrides))

    def test_correction_recalculates_half_up_preserves_physical_capture_and_other_prices(self):
        physical = {field: getattr(self.measurement, field) for field in (
            "net_weight_grams", "tare_grams", "capture_key", "captured_at", "device", "stability_parameters",
        )}
        result = self.change()
        self.assertEqual(result.product_id, self.special.pk)
        self.assertEqual((result.product_description, result.unit_price_cents, result.total_cents), ("Especial", 5990, 1498))
        self.assertEqual({field: getattr(result, field) for field in physical}, physical)
        self.other.refresh_from_db()
        self.assertEqual((self.other.product_id, self.other.total_cents, self.other.revision), (self.scale.pk, 2000, 1))
        self.assertEqual(Product.objects.get(is_scale_product=True).pk, self.scale.pk)
        event = DomainEvent.objects.get(kind="MEASUREMENT_PRODUCT_CHANGED")
        self.assertEqual(event.details["before"]["total_cents"], 1250)
        self.assertEqual(event.details["after"]["total_cents"], 1498)
        self.assertEqual(event.details["after"]["revision"], 2)
        retry = capture_measurement(capture_key=result.capture_key, net_weight_grams=250, tare_grams=300)
        self.assertEqual(retry.product_id, self.special.pk)

    def test_inclusion_uses_corrected_snapshot_and_correction_cannot_change_used_capture(self):
        self.change()
        item = add_measurement_item(order_id=self.order.pk, measurement_id=self.measurement.pk,
                                    expected_revision=2, request_key=uuid4())
        self.assertEqual((item.product_id, item.unit_price_cents, item.total_cents), (self.special.pk, 5990, 1498))
        with self.assertRaises(DomainConflict):
            self.change(expected_revision=3)
        remove_item(order_id=self.order.pk, item_id=item.pk)
        self.change(product_id=self.scale.pk, expected_revision=4)
        item.refresh_from_db()
        self.assertEqual((item.product_id, item.unit_price_cents, item.total_cents), (self.special.pk, 5990, 1498))

    def test_rejects_invalid_products_stale_revisions_and_discarded_capture(self):
        for product_id in (self.drink.pk, self.inactive.pk, 999999):
            with self.assertRaises(ValidationError):
                self.change(product_id=product_id)
        with self.assertRaises(DomainConflict):
            self.change(expected_product_revision=2)
        self.change()
        with self.assertRaises(DomainConflict):
            self.change()
        with self.assertRaises(DomainConflict):
            add_measurement_item(order_id=self.order.pk, measurement_id=self.measurement.pk,
                                 expected_revision=1, request_key=uuid4())
        discard_measurement(self.measurement.pk)
        with self.assertRaises(DomainConflict):
            self.change(expected_revision=3)

    def test_history_failure_rolls_back_commercial_changes(self):
        with patch("apps.measurements.services.record_event", side_effect=RuntimeError("history unavailable")):
            with self.assertRaises(RuntimeError):
                self.change()
        self.measurement.refresh_from_db()
        self.assertEqual((self.measurement.product_id, self.measurement.total_cents, self.measurement.revision),
                         (self.scale.pk, 1250, 1))

    def test_dialog_shows_weight_price_and_recalculated_total_for_eligible_products(self):
        response = self.client.get(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(response, "0,250 kg")
        self.assertContains(response, "Total R$ 14,98")
        self.assertContains(response, 'name="expected_revision" value="1"')
        self.assertNotContains(response, "Suco")
        self.assertNotContains(response, "Inativo")
        for route in ("home", "attendance_alternative"):
            response = self.client.get(reverse(route) + f"?order={self.order.pk}")
            self.assertContains(response, 'id="measurement-product-dialog"', count=1)
            self.assertContains(response, 'class="measurement-product-trigger"', count=2)
            self.assertContains(response, 'name="expected_revision" value="1"', count=2)

    def test_post_refreshes_cards_and_keeps_selection_in_both_layouts(self):
        for suffix in ("", "&layout=alternative"):
            response = self.client.post(self.url + f"?order={self.order.pk}" + suffix, self.data, HTTP_HX_REQUEST="true")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-Selected-Order"], str(self.order.pk))
            self.assertEqual(response["HX-Trigger-After-Swap"], "measurementProductChanged")
            self.assertContains(response, "14,98")
            self.assertNotContains(response, "<!doctype")
            self.data["expected_revision"] += 1

    def test_conflict_refreshes_dialog_and_available_cards(self):
        self.change()
        response = self.client.post(self.url, self.data, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["HX-Retarget"], "#measurement-product-content")
        self.assertContains(response, 'name="expected_revision" value="2"', status_code=409)
        self.assertContains(response, 'hx-swap-oob="outerHTML"', status_code=409)
        discard_measurement(self.measurement.pk)
        response = self.client.post(self.url, self.data, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Pesagem já incluída ou descartada", status_code=409)
        self.assertNotContains(response, 'name="product_id"', status_code=409)
        response = self.client.get(self.url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 409)

    def test_product_change_since_dialog_requires_reviewing_new_price(self):
        Product.objects.filter(pk=self.special.pk).update(unit_price_cents=7000, revision=2)
        response = self.client.post(self.url, self.data, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Confira o preço", status_code=409)
        self.assertContains(response, "Total R$ 17,50", status_code=409)
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.total_cents, 1250)

    def test_no_order_and_normal_navigation_fallback(self):
        response = self.client.post(self.url, self.data, HTTP_HX_REQUEST="true")
        self.assertEqual(response["X-Selected-Order"], "")
        self.assertNotContains(response, 'name="order_id"')
        self.assertContains(self.client.get(self.url), "<!doctype html>")
        response = self.client.post(self.url + f"?order={self.order.pk}&layout=alternative",
                                    self.data | {"expected_revision": 2})
        self.assertEqual(response.url, reverse("attendance_alternative") + f"?order={self.order.pk}")

    def test_invalid_payload_csrf_methods_and_runtime_gate(self):
        self.assertEqual(self.client.post(self.url, {}, HTTP_HX_REQUEST="true").status_code, 400)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, self.data).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        state.update(running=False)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 503)

    def test_large_total_is_disabled_and_rejected_without_changing_capture(self):
        Product.objects.filter(pk=self.special.pk).update(unit_price_cents=9_000_000_000_000)
        Measurement.objects.filter(pk=self.measurement.pk).update(net_weight_grams=2000)
        response = self.client.get(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Total fora do limite")
        self.assertContains(response, "disabled")
        with self.assertRaises(ValidationError):
            self.change()
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.product_id, self.scale.pk)


class MeasurementCorrectionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.product = save_product(description="Comum", unit="KG", unit_price_cents=5000, is_scale_product=True)
        self.other = save_product(description="Especial", unit="KG", unit_price_cents=5990)
        self.measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=250)
        self.order = open_order(request_key=uuid4())

    def correct(self):
        return change_measurement_product(measurement_id=self.measurement.pk, product_id=self.other.pk,
                                          expected_revision=1, expected_product_revision=1)

    def race(self, *actions):
        barrier = Barrier(len(actions))

        def run(action):
            connection = connections["default"]
            connection.ensure_connection()
            identity = id(connection.connection)
            try:
                barrier.wait(timeout=5)
                try:
                    action()
                    return "ok", identity
                except DomainConflict:
                    return "conflict", identity
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=len(actions)) as executor:
            results = list(executor.map(run, actions))
        self.assertEqual(len({result[1] for result in results}), len(actions))
        self.assertEqual(sorted(result[0] for result in results), ["conflict", "ok"])

    def test_two_corrections_of_same_revision_have_one_winner(self):
        self.race(self.correct, self.correct)
        self.assertEqual(DomainEvent.objects.filter(kind="MEASUREMENT_PRODUCT_CHANGED").count(), 1)
        self.measurement.refresh_from_db()
        self.assertEqual((self.measurement.revision, self.measurement.total_cents), (2, 1498))

    def test_correction_and_displayed_inclusion_have_one_winner(self):
        self.race(self.correct, lambda: add_measurement_item(
            order_id=self.order.pk, measurement_id=self.measurement.pk, request_key=uuid4(), expected_revision=1,
        ))
        self.measurement.refresh_from_db()
        if self.measurement.status == "USED":
            self.assertEqual(self.measurement.product_id, self.product.pk)
            self.assertEqual(OrderItem.objects.get().total_cents, 1250)
        else:
            self.assertEqual(self.measurement.product_id, self.other.pk)
            self.assertFalse(OrderItem.objects.exists())
