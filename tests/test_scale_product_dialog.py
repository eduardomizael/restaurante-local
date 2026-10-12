"""Attendance scale selection reuses catalogue rules and preserves captures."""

from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from apps.measurements.services import capture_measurement
from apps.products.models import Product
from apps.products.services import save_product
from runtime.state import state


class ScaleProductDialogTests(TestCase):
    def setUp(self):
        state.update(running=True, scale_status="MEASURING")
        self.current = save_product(description="Refeição comum", unit="KG", unit_price_cents=5000,
                                    is_scale_product=True)
        self.other = save_product(description="Refeição especial", unit="KG", unit_price_cents=7000)
        self.drink = save_product(description="Suco", unit="UN", unit_price_cents=500)
        self.inactive = save_product(description="Inativo", unit="KG", unit_price_cents=100, active=False)
        self.url = reverse("choose_scale_product")

    def tearDown(self):
        state.update(running=False)

    def choose(self, product, revision=None):
        return self.client.post(self.url, {
            "product_id": product.pk, "expected_revision": revision or product.revision,
        }, HTTP_HX_REQUEST="true")

    def test_card_and_dialog_show_current_selection_and_only_eligible_choices(self):
        for url in (reverse("home"), reverse("attendance_alternative")):
            response = self.client.get(url)
            self.assertContains(response, 'id="scale-product-dialog"', count=1)
            self.assertContains(response, 'class="scale-product-choice"')
            self.assertContains(response, self.current.description)
        response = self.client.get(self.url)
        self.assertContains(response, self.current.description)
        self.assertContains(response, self.other.description)
        self.assertNotContains(response, self.drink.description)
        self.assertNotContains(response, self.inactive.description)

    def test_selection_updates_card_and_polling_without_changing_saved_measurement(self):
        measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=250)
        original = (measurement.product_id, measurement.product_description, measurement.unit_price_cents)
        response = self.choose(self.other)
        self.assertContains(response, self.other.description)
        self.assertEqual(response["HX-Retarget"], "#runtime-status")
        self.assertEqual(response["HX-Trigger-After-Settle"], "scaleProductSelected")
        self.assertEqual(Product.objects.get(is_scale_product=True).pk, self.other.pk)
        for url in (reverse("board_fragment"), reverse("status_fragment") + "?surface=attendance"):
            self.assertContains(self.client.get(url), self.other.description)
        measurement.refresh_from_db()
        self.assertEqual((measurement.product_id, measurement.product_description, measurement.unit_price_cents), original)
        new = capture_measurement(capture_key=uuid4(), net_weight_grams=300)
        self.assertEqual(new.product_id, self.other.pk)

    def test_invalid_inactive_missing_and_stale_choices_keep_selection(self):
        for product in (self.drink, self.inactive):
            self.assertEqual(self.choose(product).status_code, 400)
        Product.objects.filter(pk=self.other.pk).update(revision=2)
        response = self.choose(self.other, revision=1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["X-Scale-Product-Fragment"], "1")
        self.assertContains(response, "Escolha novamente", status_code=409)
        self.assertEqual(self.client.post(self.url, {}, HTTP_HX_REQUEST="true").status_code, 400)
        self.assertEqual(Product.objects.get(is_scale_product=True).pk, self.current.pk)

    def test_csrf_runtime_gate_and_get_does_not_change_selection(self):
        self.client.get(self.url)
        self.assertEqual(Product.objects.get(is_scale_product=True).pk, self.current.pk)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, {}).status_code, 403)
        state.update(running=False)
        self.assertEqual(self.choose(self.other).status_code, 503)

    def test_no_selection_offers_picker_and_empty_catalogue_explains_next_step(self):
        Product.objects.all().update(is_scale_product=False)
        self.assertContains(self.client.get(reverse("home")), "Escolher produto")
        Product.objects.all().update(active=False)
        self.assertContains(self.client.get(self.url), "Nenhum produto ativo por kg")
