"""Manual product inclusion inside the attendance dialog."""

from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.orders.models import OrderItem
from apps.orders.services import cancel_order, open_order
from apps.products.services import save_product
from runtime.state import state


class ManualItemDialogTests(TestCase):
    def setUp(self):
        state.update(running=True)
        self.order = open_order(request_key=uuid4())
        self.other_order = open_order(request_key=uuid4())
        self.product = save_product(description="Suco", unit="UN", unit_price_cents=700, is_quick_access=True)
        self.weight_product = save_product(description="Refeição", unit="KG", unit_price_cents=5000)

    def tearDown(self):
        state.update(running=False)

    def url(self, product=None):
        return reverse("manual_item", args=[self.order.pk, (product or self.product).pk])

    def data(self, **changes):
        return {"order_id": self.order.pk, "product_id": self.product.pk,
                "request_key": uuid4(), "quantity_units": 2, **changes}

    def test_quick_and_catalogue_products_open_inline_keypad_with_explicit_order(self):
        response = self.client.get(reverse("home"), {"order": self.order.pk})
        self.assertContains(response, 'id="manual-item-dialog"')
        self.assertContains(response, f'hx-get="{self.url()}"')
        response = self.client.get(self.url(), HTTP_HX_REQUEST="true")
        self.assertContains(response, 'class="manual-item-form"')
        self.assertContains(response, 'data-item-value="0"')
        self.assertContains(response, "Confirmar e adicionar")
        self.assertNotContains(response, "<html")
        self.assertEqual(response["X-Selected-Order"], str(self.order.pk))
        self.assertFalse(OrderItem.objects.exists())

    def test_confirm_returns_items_and_totals_without_navigation_or_duplicate_insertion(self):
        data = self.data()
        response = self.client.post(self.url(), data, HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="shared-board"')
        self.assertContains(response, "R$ 14,00")
        self.assertNotContains(response, "<html")
        self.assertEqual(response["HX-Trigger-After-Swap"], "manualItemAdded")
        self.assertEqual(response["X-Selected-Order"], str(self.order.pk))
        self.assertEqual(OrderItem.objects.get().quantity_units, 2)
        self.assertFalse(OrderItem.objects.filter(order=self.other_order).exists())
        self.client.post(self.url(), data, HTTP_HX_REQUEST="true")
        self.assertEqual(OrderItem.objects.count(), 1)

    def test_invalid_quantity_and_wrong_destination_keep_dialog_and_key(self):
        data = self.data(quantity_units=0)
        response = self.client.post(self.url(), data, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["HX-Retarget"], "#manual-item-content")
        self.assertContains(response, str(data["request_key"]), status_code=400)
        response = self.client.post(self.url(), self.data(order_id=self.other_order.pk), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["HX-Retarget"], "#manual-item-content")
        self.assertFalse(OrderItem.objects.exists())

    def test_weight_dialog_parses_three_decimal_places(self):
        response = self.client.get(self.url(self.weight_product), HTTP_HX_REQUEST="true")
        self.assertContains(response, 'data-item-value="3"')
        response = self.client.post(self.url(self.weight_product), self.data(
            product_id=self.weight_product.pk, quantity_units="", weight_grams="0,252",
        ), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OrderItem.objects.get().weight_grams, 252)
        self.assertEqual(OrderItem.objects.get().total_cents, 1260)

    def test_closed_order_rejects_dialog_submission_and_normal_navigation_still_works(self):
        self.assertContains(self.client.get(self.url()), "<html")
        cancel_order(self.order.pk)
        response = self.client.post(self.url(), self.data(), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(OrderItem.objects.exists())
