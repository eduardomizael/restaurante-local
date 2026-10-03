"""Touch HTTP flows and independent, deterministic scale capture tests."""

from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from apps.core.domain import DomainConflict
from apps.measurements.models import Measurement
from apps.measurements.services import capture_measurement
from apps.orders.models import Order, OrderItem
from apps.orders.selectors import subtotal_cents
from apps.orders.services import open_order
from apps.products.models import Product
from apps.products.services import save_product
from runtime.state import state


class TouchFlowTests(TestCase):
    def setUp(self):
        state.update(running=True, paused=False, scale_status="MEASURING", error="")
        self.kg = save_product(description="Refeição por peso", unit="KG", unit_price_cents=5000,
                               is_scale_product=True, is_quick_access=True)
        self.unit = save_product(description="À vontade", unit="UN", unit_price_cents=3590,
                                 is_quick_access=True)

    def tearDown(self):
        state.update(running=False)

    def open_via_http(self):
        response = self.client.post(reverse("create_order"), {"request_key": uuid4()})
        self.assertEqual(response.status_code, 302)
        order_id = int(response.url.split("order=")[1])
        return Order.objects.get(pk=order_id)

    def test_catalogue_create_edit_and_stale_revision(self):
        response = self.client.get(reverse("new_product"))
        self.assertContains(response, 'data-keypad="2"')
        self.assertContains(response, 'id="numeric-keypad"')
        data = {"description": "Suco", "unit": "UN", "unit_price_cents": "8,50", "active": "on",
                "is_quick_access": "on", "appears_on_order_slip": "on", "quick_access_order": 0, "slip_order": 0}
        self.assertEqual(self.client.post(reverse("new_product"), data).status_code, 302)
        product = Product.objects.get(description="Suco")
        self.assertEqual(product.unit_price_cents, 850)
        self.assertTrue(product.appears_on_order_slip)
        edit = reverse("edit_product", args=[product.pk])
        self.assertContains(self.client.get(edit), 'value="8,50"')
        data.update(unit_price_cents="9,00", expected_revision=1)
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        self.assertEqual(self.client.post(edit, data).status_code, 409)
        self.assertEqual(Product.objects.get(pk=product.pk).unit_price_cents, 900)

    def test_catalogue_validation_shows_error_without_saving(self):
        data = {"description": "Inválido", "unit": "UN", "unit_price_cents": "1,00", "active": "on",
                "is_scale_product": "on", "quick_access_order": 0, "slip_order": 0}
        response = self.client.post(reverse("new_product"), data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Produto da balança deve estar ativo e usar KG", status_code=400)
        self.assertFalse(Product.objects.filter(description="Inválido").exists())

    def test_open_order_retry_uses_same_number_and_selection(self):
        key = uuid4()
        first = self.client.post(reverse("create_order"), {"request_key": key})
        repeated = self.client.post(reverse("create_order"), {"request_key": key})
        self.assertEqual(first.url, repeated.url)
        self.assertEqual(Order.objects.count(), 1)
        self.assertContains(self.client.get(first.url), "Comanda 1")

    def test_two_orders_three_captures_manual_items_and_destination_binding(self):
        first, second = self.open_via_http(), self.open_via_http()
        measurements = [capture_measurement(capture_key=uuid4(), net_weight_grams=grams) for grams in (252, 300, 400)]
        key = uuid4()
        data = {"order_id": first.pk, "measurement_id": measurements[0].pk, "request_key": key}
        # Current selection/referrer is deliberately different from the submitted destination.
        response = self.client.post(reverse("consume_measurement"), data, HTTP_REFERER=f"http://testserver/?order={second.pk}")
        self.assertEqual(response.url, f"/?order={first.pk}")
        self.assertEqual(self.client.post(reverse("consume_measurement"), data).status_code, 302)
        self.assertEqual(self.client.post(reverse("consume_measurement"), dict(data, order_id=second.pk)).status_code, 409)
        second_data = {"order_id": second.pk, "measurement_id": measurements[1].pk, "request_key": uuid4()}
        self.assertEqual(self.client.post(reverse("consume_measurement"), second_data).status_code, 302)
        for product, quantities in ((self.unit, {"quantity_units": "1"}), (self.kg, {"weight_grams": "0,100"})):
            url = reverse("manual_item", args=[first.pk, product.pk])
            data = {"order_id": first.pk, "product_id": product.pk, "request_key": uuid4(), **quantities}
            self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(subtotal_cents(first.pk), 5350)
        self.assertEqual(subtotal_cents(second.pk), 1500)
        self.assertEqual(Measurement.objects.filter(status="AVAILABLE").get().pk, measurements[2].pk)
        page = self.client.get(f"/?order={first.pk}")
        self.assertContains(page, "R$ 53,50")
        self.assertContains(page, "Impressão indisponível")
        self.assertEqual(OrderItem.objects.filter(order=first).count(), 3)

    def test_manual_form_has_only_unit_relevant_quantity_and_rejects_route_tampering(self):
        first, second = self.open_via_http(), self.open_via_http()
        url = reverse("manual_item", args=[first.pk, self.kg.pk])
        response = self.client.get(url)
        self.assertContains(response, 'data-keypad="3"')
        self.assertNotContains(response, 'name="quantity_units"')
        data = {"order_id": second.pk, "product_id": self.kg.pk, "request_key": uuid4(), "weight_grams": "0,252"}
        self.assertEqual(self.client.post(url, data).status_code, 409)
        data["order_id"] = first.pk
        data["weight_grams"] = "0,2521"
        self.assertEqual(self.client.post(url, data).status_code, 400)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_removal_returns_capture_without_affecting_other_order(self):
        first, second = self.open_via_http(), self.open_via_http()
        measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=252)
        self.client.post(reverse("consume_measurement"), {"order_id": first.pk, "measurement_id": measurement.pk, "request_key": uuid4()})
        item = OrderItem.objects.get()
        data = {"order_id": second.pk, "item_id": item.pk}
        self.assertEqual(self.client.post(reverse("delete_item"), data).status_code, 409)
        data["order_id"] = first.pk
        self.assertEqual(self.client.post(reverse("delete_item"), data).status_code, 302)
        item.refresh_from_db()
        measurement.refresh_from_db()
        self.assertFalse(item.active)
        self.assertEqual(measurement.status, "AVAILABLE")

    def test_cancel_and_discard_require_explicit_confirmation_and_affect_only_selection(self):
        first, second = self.open_via_http(), self.open_via_http()
        used = capture_measurement(capture_key=uuid4(), net_weight_grams=252)
        pending = capture_measurement(capture_key=uuid4(), net_weight_grams=300)
        self.client.post(reverse("consume_measurement"), {"order_id": first.pk, "measurement_id": used.pk, "request_key": uuid4()})
        cancel = reverse("confirm_cancel", args=[first.pk])
        self.assertEqual(self.client.get(cancel).status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.status, "DRAFT")
        self.assertEqual(self.client.post(cancel, {}).status_code, 400)
        self.assertEqual(self.client.post(cancel, {"confirm": "True"}).status_code, 302)
        second.refresh_from_db()
        used.refresh_from_db()
        self.assertEqual(second.status, "DRAFT")
        self.assertEqual(used.status, "AVAILABLE")
        discard = reverse("confirm_discard", args=[pending.pk]) + f"?order={second.pk}"
        self.assertContains(self.client.get(discard), "0,300 kg")
        self.assertEqual(self.client.post(discard, {}).status_code, 400)
        response = self.client.post(discard, {"confirm": "True"})
        self.assertEqual(response.url, f"/?order={second.pk}")
        pending.refresh_from_db()
        self.assertEqual(pending.status, "DISCARDED")
        self.assertEqual(Measurement.objects.filter(status="AVAILABLE").count(), 1)

    def test_numbering_screen_rejects_occupied_number(self):
        order = self.open_via_http()
        self.assertContains(self.client.get(reverse("numbering")), 'value="2"')
        self.assertEqual(self.client.post(reverse("numbering"), {"number": order.number}).status_code, 409)
        self.assertEqual(self.client.post(reverse("numbering"), {"number": 20}).status_code, 302)
        self.assertEqual(self.open_via_http().number, 20)

    def test_polling_has_revision_and_fixed_selection_without_editable_fields(self):
        order = self.open_via_http()
        page = self.client.get(f"/?order={order.pk}")
        revision = page.context["revision"]
        url = reverse("board_fragment") + f"?order={order.pk}&revision={revision}"
        self.assertEqual(self.client.get(url).status_code, 204)
        capture_measurement(capture_key=uuid4(), net_weight_grams=252)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Selected-Order"], str(order.pk))
        self.assertContains(response, 'name="order_id"')
        self.assertNotContains(response, 'id="product-search"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')

    def test_polling_without_selection_does_not_choose_a_new_order(self):
        self.open_via_http()
        response = self.client.get(reverse("board_fragment") + "?order=&revision=0")
        self.assertEqual(response["X-Selected-Order"], "")
        self.assertContains(response, "Selecione uma comanda aberta")
        self.assertNotContains(response, 'name="order_id"')

    def test_cancelled_selection_does_not_redirect_actions_to_another_draft(self):
        first, second = self.open_via_http(), self.open_via_http()
        self.client.post(reverse("confirm_cancel", args=[first.pk]), {"confirm": "True"})
        response = self.client.get(f"/?order={first.pk}")
        self.assertIsNone(response.context["selected"])
        self.assertContains(response, "Selecione uma comanda aberta")
        self.assertNotContains(response, 'name="order_id"')
        second.refresh_from_db()
        self.assertEqual(second.status, "DRAFT")

    def test_csrf_methods_and_shutdown_gate_protect_commercial_operations(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(reverse("create_order")).status_code, 405)
        self.assertEqual(client.post(reverse("create_order"), {"request_key": uuid4()}).status_code, 403)
        client.get("/")
        token = client.cookies["csrftoken"].value
        state.update(running=False)
        self.assertEqual(client.post(reverse("create_order"), {"request_key": uuid4()}, HTTP_X_CSRFTOKEN=token).status_code, 503)
        self.assertEqual(Order.objects.count(), 0)
