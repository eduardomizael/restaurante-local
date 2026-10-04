"""Inline catalogue edits preserve fields and the unique scale selection."""

from django.test import Client, TestCase
from django.urls import reverse

from apps.products.models import Product
from apps.products.services import save_product
from runtime.state import state


class ProductFlagTests(TestCase):
    def setUp(self):
        state.update(running=True)
        self.scale = save_product(description="Refeição da balança", unit="KG", unit_price_cents=5000,
                                  is_scale_product=True)
        self.other = save_product(description="Refeição especial", unit="KG", unit_price_cents=6500)
        self.drink = save_product(description="Suco", unit="UN", unit_price_cents=500)

    def tearDown(self):
        state.update(running=False)

    def change(self, product, flag, enabled=True, revision=None, search=""):
        data = {"flag": flag, "expected_revision": revision or product.revision, "q": search}
        if enabled:
            data["enabled"] = "on"
        return self.client.post(reverse("update_product_flag", args=[product.pk]), data, HTTP_HX_REQUEST="true")

    def test_scale_product_has_own_section_and_is_not_duplicated(self):
        response = self.client.get(reverse("catalogue"))
        self.assertContains(response, "Produto da balança")
        self.assertContains(response, f'id="product-{self.scale.pk}"', count=1)
        self.assertContains(response, 'class="card product-row scale-product-card"')
        self.assertContains(response, 'type="checkbox"', count=9)
        self.assertContains(response, 'name="flag" value="is_scale_product"', count=3)

    def test_each_flag_updates_only_its_field_and_returns_current_cards(self):
        for flag in ("is_quick_access", "appears_on_order_slip"):
            response = self.change(self.drink, flag)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "<!doctype html>")
            self.drink.refresh_from_db()
            self.assertTrue(getattr(self.drink, flag))
            self.assertEqual(self.drink.unit_price_cents, 500)
            self.assertEqual(self.drink.description, "Suco")
            response = self.change(self.drink, flag, False)
            self.assertEqual(response.status_code, 200)
            self.drink.refresh_from_db()
            self.assertFalse(getattr(self.drink, flag))
        self.assertEqual(Product.objects.filter(is_scale_product=True).count(), 1)

    def test_scale_selection_transfer_updates_both_cards_atomically(self):
        response = self.change(self.other, "is_scale_product")
        self.assertEqual(response.status_code, 200)
        self.scale.refresh_from_db()
        self.other.refresh_from_db()
        self.assertFalse(self.scale.is_scale_product)
        self.assertTrue(self.other.is_scale_product)
        self.assertEqual(self.scale.revision, 2)
        self.assertEqual(self.other.revision, 2)
        self.assertEqual(Product.objects.filter(is_scale_product=True).count(), 1)
        text = response.content.decode()
        selected_section = text.split('aria-labelledby="other-products-heading"')[0]
        self.assertIn(f'id="product-{self.other.pk}"', selected_section)
        self.assertNotIn(f'id="product-{self.scale.pk}"', selected_section)
        self.assertIn(f'id="product-{self.scale.pk}"', text)

    def test_scale_can_be_unselected_and_search_is_preserved_on_transfer(self):
        response = self.change(self.other, "is_scale_product", search="Suco")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="q" value="Suco"')
        self.assertContains(response, f'id="product-{self.other.pk}"')
        self.assertContains(response, f'id="product-{self.drink.pk}"')
        self.assertNotContains(response, f'id="product-{self.scale.pk}"')
        self.other.refresh_from_db()
        response = self.change(self.other, "is_scale_product", False)
        self.assertContains(response, "Nenhum produto selecionado para a balança")
        self.assertFalse(Product.objects.filter(is_scale_product=True).exists())

    def test_invalid_scale_candidate_or_stale_revision_preserves_selection(self):
        response = self.change(self.drink, "is_scale_product")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Produto da balança deve estar ativo e usar KG", status_code=400)
        inactive = save_product(description="Inativo", unit="KG", unit_price_cents=100, active=False)
        self.assertEqual(self.change(inactive, "is_scale_product").status_code, 400)
        self.assertEqual(self.change(self.other, "is_quick_access").status_code, 200)
        self.assertEqual(self.change(self.other, "is_scale_product", revision=1).status_code, 409)
        self.assertEqual(Product.objects.get(is_scale_product=True).pk, self.scale.pk)
        self.assertEqual(Product.objects.get(pk=self.other.pk).revision, 2)

    def test_invalid_flag_and_missing_revision_do_not_update_product(self):
        self.assertEqual(self.change(self.drink, "active").status_code, 400)
        response = self.client.post(reverse("update_product_flag", args=[self.drink.pk]), {
            "flag": "is_quick_access", "enabled": "on",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 400)
        self.drink.refresh_from_db()
        self.assertEqual(self.drink.revision, 1)
        self.assertTrue(self.drink.active)

    def test_requires_post_csrf_and_running_runtime(self):
        url = reverse("update_product_flag", args=[self.drink.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, {}).status_code, 403)
        state.update(running=False)
        self.assertEqual(self.change(self.drink, "is_quick_access").status_code, 503)
