"""Explicit meal grouping across catalogue, capture, item and frozen documents."""

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.domain import DomainConflict
from apps.measurements.models import Measurement
from apps.measurements.services import capture_measurement, change_measurement_product
from apps.orders.models import Order, OrderItem
from apps.orders.services import add_measurement_item, add_product_item, open_order
from apps.printing.documents import fingerprint, render_text
from apps.printing.selectors import draft_content
from apps.printing.services import print_open_order, save_document_configuration
from apps.products.models import Product
from apps.products.services import save_product, set_product_flag
from runtime.state import state


class MealClassificationTests(TestCase):
    def setUp(self):
        state.update(running=True)
        self.order = open_order(request_key=uuid4())

    def tearDown(self):
        state.update(running=False)

    def product(self, name="Marmita", unit="UN", **kwargs):
        return save_product(description=name, unit=unit, unit_price_cents=2000, **kwargs)

    def add(self, product):
        return add_product_item(order_id=self.order.pk, product_id=product.pk, request_key=uuid4(),
                                **({"weight_grams": 250} if product.unit == "KG" else {"quantity_units": 1}))

    def flag(self, product, enabled):
        return set_product_flag(product_id=product.pk, flag="is_meal", enabled=enabled,
                                expected_revision=product.revision)

    def test_new_products_require_explicit_flag_regardless_of_name_or_unit(self):
        products = [self.product("Refeição"), self.product("À vontade"), self.product("Produto por kg", "KG")]
        for product in products:
            self.assertFalse(product.is_meal)
            self.assertFalse(self.add(product).is_meal)
        meal = self.product("Marmita", is_meal=True, appears_on_order_slip=True)
        self.assertTrue(self.add(meal).is_meal)
        content = draft_content(self.order)
        self.assertEqual([item["description"] for item in content["items"] if item["is_meal"]], ["Marmita"])
        self.assertEqual({row["description"] for row in content["manuscript_rows"]}, {p.description for p in products})

    def test_nonmeal_kilogram_rows_preserve_weight_value_and_price(self):
        product = self.product("Produto por kg", "KG")
        self.add(product)
        content = draft_content(self.order)
        self.assertFalse(content["items"][0]["is_meal"])
        self.assertEqual(content["manuscript_rows"][0]["variants"][0]["weight_grams"], 250)
        text = render_text(content)
        self.assertIn("Peso lançado: 0,250 kg - R$ 5,00", text)
        self.assertIn("Produto por kg (KG)", text)
        self.assertIn("SUBTOTAL REFEIÇÕES R$ 0,00", text)

    def test_flag_does_not_reclassify_existing_items_and_preserves_other_flags(self):
        product = self.product(is_meal=True, is_quick_access=True, appears_on_order_slip=True)
        first = self.add(product)
        product = self.flag(product, False)
        self.assertTrue(product.is_quick_access)
        self.assertTrue(product.appears_on_order_slip)
        second = self.add(product)
        first.refresh_from_db()
        self.assertTrue(first.is_meal)
        self.assertFalse(second.is_meal)
        content = draft_content(self.order)
        self.assertEqual([item["is_meal"] for item in content["items"]], [True, False])
        self.assertEqual(content["manuscript_rows"][0]["quantity_units"], 1)
        with self.assertRaises(DomainConflict):
            set_product_flag(product_id=product.pk, flag="is_meal", enabled=True, expected_revision=1)
        with self.assertRaises(ValidationError):
            save_product(description="Inválido", unit="UN", unit_price_cents=100, is_meal=1)

    def test_capture_preserves_flag_and_explicit_correction_copies_new_product_flag(self):
        product = self.product("Por peso", "KG", is_meal=True, is_scale_product=True)
        measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=250)
        self.assertTrue(measurement.is_meal)
        self.flag(product, False)
        item = add_measurement_item(order_id=self.order.pk, measurement_id=measurement.pk, request_key=uuid4())
        self.assertTrue(item.is_meal)
        other = capture_measurement(capture_key=uuid4(), net_weight_grams=300)
        self.assertFalse(other.is_meal)
        meal = self.product("Especial", "KG", is_meal=True)
        corrected = change_measurement_product(measurement_id=other.pk, product_id=meal.pk,
                                               expected_revision=1, expected_product_revision=1)
        self.assertTrue(corrected.is_meal)
        self.assertTrue(add_measurement_item(order_id=self.order.pk, measurement_id=other.pk, request_key=uuid4()).is_meal)

    def test_saved_document_remains_unchanged_after_catalogue_flag_change(self):
        product = self.product(is_meal=True)
        self.add(product)
        save_document_configuration(header="Teste", footer="Obrigado", expected_revision=0)
        content = draft_content(self.order)
        job = print_open_order(order_id=self.order.pk, request_key=uuid4(), expected_fingerprint=fingerprint(content))
        text = render_text(job.document.content)
        self.flag(product, False)
        job.document.refresh_from_db()
        self.assertEqual(render_text(job.document.content), text)
        self.assertTrue(job.document.content["items"][0]["is_meal"])

    def test_legacy_snapshots_preserve_previous_rule_without_duplicate_marked_rows(self):
        product = self.product("Refeição", appears_on_order_slip=True)
        item = self.add(product)
        OrderItem.objects.filter(pk=item.pk).update(is_meal=None)
        content = draft_content(self.order)
        self.assertTrue(content["items"][0]["is_meal"])
        self.assertEqual(content["manuscript_rows"], [])
        kg = self.product("Por peso", "KG", is_scale_product=True)
        measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=250)
        Measurement.objects.filter(pk=measurement.pk).update(is_meal=None)
        self.assertTrue(add_measurement_item(order_id=self.order.pk, measurement_id=measurement.pk,
                                             request_key=uuid4()).is_meal)
        self.assertFalse(kg.is_meal)

    def test_edit_form_and_inline_flag_support_explicit_mark_and_unmark(self):
        product = self.product()
        response = self.client.get(reverse("edit_product", args=[product.pk]))
        self.assertContains(response, 'name="is_meal"')
        self.assertContains(response, "É refeição")
        data = {"description": "Marmita", "unit": "UN", "unit_price_cents": "20,00", "active": "on",
                "is_meal": "on", "expected_revision": 1, "quick_access_order": 0, "slip_order": 0}
        response = self.client.post(reverse("edit_product", args=[product.pk]), data)
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertTrue(product.is_meal)
        response = self.client.get(reverse("catalogue"))
        self.assertContains(response, f'id="product-{product.pk}-is_meal"')
        response = self.client.post(reverse("update_product_flag", args=[product.pk]), {
            "flag": "is_meal", "expected_revision": product.revision,
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertFalse(product.is_meal)


class MealClassificationMigrationTests(TransactionTestCase):
    def test_upgrade_defaults_catalogue_to_explicit_choice_and_preserves_old_snapshots(self):
        previous = [("products", "0001_initial"), ("measurements", "0003_measurement_revision"),
                    ("orders", "0001_initial")]
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(previous)
            apps = executor.loader.project_state(previous).apps
            product = apps.get_model("products", "Product").objects.create(
                description="Refeição antiga", unit="KG", unit_price_cents=5000,
            )
            measurement = apps.get_model("measurements", "Measurement").objects.create(
                capture_key=uuid4(), product_id=product.pk, product_description=product.description,
                net_weight_grams=250, unit_price_cents=5000, total_cents=1250, device="SIMULATOR",
            )
            order = apps.get_model("orders", "Order").objects.create(number=1, request_key=uuid4())
            item = apps.get_model("orders", "OrderItem").objects.create(
                order_id=order.pk, product_id=product.pk, source="MANUAL", request_key=uuid4(),
                product_description=product.description, unit="KG", weight_grams=250,
                unit_price_cents=5000, total_cents=1250,
            )
            MigrationExecutor(connection).migrate(latest)
            self.assertFalse(Product.objects.get(pk=product.pk).is_meal)
            self.assertIsNone(Measurement.objects.get(pk=measurement.pk).is_meal)
            self.assertIsNone(OrderItem.objects.get(pk=item.pk).is_meal)
            content = draft_content(Order.objects.get(pk=order.pk))
            self.assertTrue(content["items"][0]["is_meal"])
            self.assertIn("Refeição antiga", render_text(content))
        finally:
            MigrationExecutor(connection).migrate(latest)
