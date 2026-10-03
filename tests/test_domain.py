"""Commercial invariants, historical snapshots and real SQLite contention."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
import sqlite3
import subprocess
import sys
import tempfile
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import IntegrityError, connection, connections, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from apps.core.domain import DomainConflict, calculate_weight_total
from apps.core.models import DomainEvent
from apps.measurements.models import Measurement
from apps.measurements.selectors import available_measurements
from apps.measurements.services import capture_measurement, discard_measurement
from apps.orders.forms import ManualItemForm
from apps.orders.models import Order, OrderItem, OrderSequence
from apps.orders.selectors import open_orders, subtotal_cents
from apps.orders.services import (
    add_measurement_item, add_product_item, cancel_order, open_order, remove_item, set_next_number,
)
from apps.products.forms import ProductForm, ScaledDecimalField
from apps.products.models import Product
from apps.products.services import save_product


def create_scale_product(price=5000):
    """Create the scale catalogue entry through the public service."""
    return save_product(description="Refeição por peso", unit="KG", unit_price_cents=price,
                        is_scale_product=True, appears_on_order_slip=True)


def capture(weight=252, **options):
    """Capture one explicitly identified simulated stable measurement."""
    return capture_measurement(capture_key=uuid4(), net_weight_grams=weight, **options)


class ParsingTests(SimpleTestCase):
    def test_decimal_input_becomes_integer_cents_and_grams(self):
        cents = ScaledDecimalField(decimal_places=2)
        grams = ScaledDecimalField(decimal_places=3, minimum=1)
        self.assertEqual(cents.clean("35,90"), 3590)
        self.assertEqual(cents.clean("0.05"), 5)
        self.assertEqual(grams.clean("0,252"), 252)
        for value in ("1.000,00", "1e2", "-1", "NaN", "Infinity", "3,001", "35.", "1,", "1 000"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                cents.clean(value)

    def test_half_up_rounding_and_rejection_of_float_commercial_values(self):
        self.assertEqual(calculate_weight_total(50, 10), 1)
        self.assertEqual(calculate_weight_total(5000, 252), 1260)
        for invalid in (1.0, Decimal("1"), True):
            with self.assertRaises(ValidationError):
                calculate_weight_total(invalid, 252)
            with self.assertRaises(ValidationError):
                calculate_weight_total(5000, invalid)

    def test_forms_parse_prices_weights_and_explicit_destination(self):
        product = ProductForm({"description": "À vontade", "unit": "UN", "unit_price_cents": "35,90",
                               "active": "on", "quick_access_order": "0", "slip_order": "0"})
        self.assertTrue(product.is_valid(), product.errors)
        self.assertEqual(product.cleaned_data["unit_price_cents"], 3590)
        item = ManualItemForm({"order_id": 7, "product_id": 3, "request_key": str(uuid4()), "weight_grams": "0,252"})
        self.assertTrue(item.is_valid(), item.errors)
        self.assertEqual(item.cleaned_data["order_id"], 7)
        self.assertEqual(item.cleaned_data["weight_grams"], 252)


class DomainTests(TestCase):
    def setUp(self):
        self.product = create_scale_product()
        self.unit_product = save_product(description="À vontade", unit="UN", unit_price_cents=3590)

    def test_requires_an_active_kg_scale_product(self):
        Product.objects.filter(pk=self.product.pk).update(is_scale_product=False)
        with self.assertRaises(DomainConflict):
            capture()
        with self.assertRaises(ValidationError):
            save_product(description="Bebida", unit="UN", unit_price_cents=500, is_scale_product=True)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_scale_product_switch_is_atomic_and_rejects_stale_edit(self):
        second = save_product(description="Novo por peso", unit="KG", unit_price_cents=6000, is_scale_product=True)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_scale_product)
        self.assertEqual(self.product.revision, 2)
        self.assertTrue(second.is_scale_product)
        with self.assertRaises(DomainConflict):
            save_product(product_id=self.product.pk, expected_revision=1, description="Antigo", unit="KG", unit_price_cents=9000)
        self.assertEqual(Product.objects.filter(is_scale_product=True).count(), 1)

    def test_capture_freezes_price_description_and_does_not_subtract_tare(self):
        key = uuid4()
        measurement = capture_measurement(capture_key=key, net_weight_grams=252, tare_grams=100)
        save_product(product_id=self.product.pk, expected_revision=1, description="Preço novo",
                     unit="KG", unit_price_cents=9000, is_scale_product=True)
        repeated = capture_measurement(capture_key=key, net_weight_grams=252, tare_grams=100)
        self.assertEqual(measurement.pk, repeated.pk)
        self.assertEqual(repeated.product_description, "Refeição por peso")
        self.assertEqual(repeated.net_weight_grams, 252)
        self.assertEqual(repeated.total_cents, 1260)
        self.assertEqual(repeated.unit_price_cents, 5000)
        with self.assertRaises(DomainConflict):
            capture_measurement(capture_key=key, net_weight_grams=253, tare_grams=100)
        self.assertEqual(Measurement.objects.count(), 1)

    def test_many_drafts_share_pending_measurements_and_manual_items_do_not_consume_them(self):
        first, second = open_order(request_key=uuid4()), open_order(request_key=uuid4())
        measurement = capture()
        weighed = add_product_item(order_id=first.pk, product_id=self.product.pk, request_key=uuid4(), weight_grams=100)
        unit = add_product_item(order_id=second.pk, product_id=self.unit_product.pk, request_key=uuid4(), quantity_units=2)
        self.assertEqual(weighed.total_cents, 500)
        self.assertEqual(unit.total_cents, 7180)
        self.assertEqual(list(open_orders()), [first, second])
        self.assertEqual(list(available_measurements()), [measurement])
        self.assertEqual(subtotal_cents(first.pk), 500)

    def test_consumption_is_idempotent_and_destination_cannot_change(self):
        first, second = open_order(request_key=uuid4()), open_order(request_key=uuid4())
        measurement = capture()
        key = uuid4()
        item = add_measurement_item(order_id=first.pk, measurement_id=measurement.pk, request_key=key)
        repeated = add_measurement_item(order_id=first.pk, measurement_id=measurement.pk, request_key=key)
        self.assertEqual(item.pk, repeated.pk)
        with self.assertRaises(DomainConflict):
            add_measurement_item(order_id=second.pk, measurement_id=measurement.pk, request_key=key)
        with self.assertRaises(DomainConflict):
            add_measurement_item(order_id=second.pk, measurement_id=measurement.pk, request_key=uuid4())
        self.assertEqual(OrderItem.objects.count(), 1)
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, Measurement.Status.USED)

    def test_failed_item_creation_rolls_back_measurement_consumption(self):
        order = open_order(request_key=uuid4())
        measurement = capture()
        with patch("apps.orders.services.OrderItem.objects.create", side_effect=RuntimeError("Falha de gravação")):
            with self.assertRaises(RuntimeError):
                add_measurement_item(order_id=order.pk, measurement_id=measurement.pk, request_key=uuid4())
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, Measurement.Status.AVAILABLE)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_removed_measurement_can_be_used_again_and_old_click_does_not_reactivate_item(self):
        first, second = open_order(request_key=uuid4()), open_order(request_key=uuid4())
        measurement = capture()
        key = uuid4()
        item = add_measurement_item(order_id=first.pk, measurement_id=measurement.pk, request_key=key)
        remove_item(order_id=first.pk, item_id=item.pk)
        remove_item(order_id=first.pk, item_id=item.pk)
        reused = add_measurement_item(order_id=second.pk, measurement_id=measurement.pk, request_key=uuid4())
        repeated = add_measurement_item(order_id=first.pk, measurement_id=measurement.pk, request_key=key)
        self.assertFalse(repeated.active)
        self.assertTrue(reused.active)
        self.assertEqual(measurement.item_links.count(), 2)
        self.assertEqual(measurement.item_links.filter(active=True).count(), 1)
        self.assertEqual(DomainEvent.objects.filter(kind="ITEM_REMOVED").count(), 1)

    def test_cancel_only_selected_order_preserves_shared_available_captures(self):
        first, second = open_order(request_key=uuid4()), open_order(request_key=uuid4())
        used, available = capture(), capture(300)
        item = add_measurement_item(order_id=first.pk, measurement_id=used.pk, request_key=uuid4())
        other = add_product_item(order_id=second.pk, product_id=self.unit_product.pk, request_key=uuid4(), quantity_units=1)
        cancel_order(first.pk)
        cancel_order(first.pk)
        second.refresh_from_db()
        self.assertEqual(second.status, Order.Status.DRAFT)
        self.assertEqual(set(available_measurements().values_list("pk", flat=True)), {used.pk, available.pk})
        item.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(item.active)
        self.assertTrue(other.active)
        self.assertEqual(OrderItem.objects.count(), 2)
        self.assertEqual(DomainEvent.objects.filter(kind="ORDER_CANCELLED").count(), 1)

    def test_discard_only_available_selected_measurement_and_never_used(self):
        first, second = capture(), capture(300)
        order = open_order(request_key=uuid4())
        add_measurement_item(order_id=order.pk, measurement_id=second.pk, request_key=uuid4())
        discard_measurement(first.pk)
        discard_measurement(first.pk)
        with self.assertRaises(DomainConflict):
            discard_measurement(second.pk)
        first.refresh_from_db()
        self.assertEqual(first.discard_reason, "MANUAL_DISCARD")
        self.assertIsNotNone(first.discarded_at)
        self.assertEqual(Measurement.objects.count(), 2)
        self.assertEqual(DomainEvent.objects.filter(kind="MEASUREMENT_DISCARDED").count(), 1)

    def test_numbering_retries_skips_existing_numbers_and_never_reuses_cancelled_number(self):
        key = uuid4()
        first = open_order(request_key=key)
        self.assertEqual(open_order(request_key=key).pk, first.pk)
        set_next_number(3)
        third = open_order(request_key=uuid4())
        set_next_number(2)
        second = open_order(request_key=uuid4())
        fourth = open_order(request_key=uuid4())
        self.assertEqual([first.number, second.number, third.number, fourth.number], [1, 2, 3, 4])
        cancel_order(second.pk)
        with self.assertRaises(DomainConflict):
            set_next_number(2)
        self.assertEqual(OrderSequence.objects.get().next_number, 5)

    def test_item_snapshot_and_retry_survive_product_change(self):
        order = open_order(request_key=uuid4())
        key = uuid4()
        item = add_product_item(order_id=order.pk, product_id=self.unit_product.pk, request_key=key, quantity_units=1)
        save_product(product_id=self.unit_product.pk, expected_revision=1,
                     description="Novo preço", unit="UN", unit_price_cents=9999, active=False)
        repeated = add_product_item(order_id=order.pk, product_id=self.unit_product.pk, request_key=key, quantity_units=1)
        self.assertEqual(repeated.pk, item.pk)
        self.assertEqual(repeated.product_description, "À vontade")
        self.assertEqual(subtotal_cents(order.pk), 3590)
        with self.assertRaises(DomainConflict):
            add_product_item(order_id=order.pk, product_id=self.unit_product.pk, request_key=key, quantity_units=2)

    def test_finalized_order_cannot_be_changed_or_cancelled(self):
        order = open_order(request_key=uuid4())
        item = add_product_item(order_id=order.pk, product_id=self.unit_product.pk, request_key=uuid4(), quantity_units=1)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.FINALIZED, finalized_at=timezone.now())
        for action in (
            lambda: add_product_item(order_id=order.pk, product_id=self.unit_product.pk, request_key=uuid4(), quantity_units=1),
            lambda: remove_item(order_id=order.pk, item_id=item.pk),
            lambda: cancel_order(order.pk),
        ):
            with self.assertRaises(DomainConflict):
                action()
        self.assertEqual(subtotal_cents(order.pk), 3590)

    def test_wrong_unit_and_wrong_order_are_rejected(self):
        first, second = open_order(request_key=uuid4()), open_order(request_key=uuid4())
        for product, quantities in (
            (self.product, {"quantity_units": 1}),
            (self.unit_product, {"weight_grams": 100}),
            (self.product, {"quantity_units": 1, "weight_grams": 100}),
        ):
            with self.assertRaises(ValidationError):
                add_product_item(order_id=first.pk, product_id=product.pk, request_key=uuid4(), **quantities)
        item = add_product_item(order_id=first.pk, product_id=self.unit_product.pk, request_key=uuid4(), quantity_units=1)
        with self.assertRaises(ValidationError):
            remove_item(order_id=second.pk, item_id=item.pk)

    def test_database_constraints_guard_active_link_units_and_scale_uniqueness(self):
        order = open_order(request_key=uuid4())
        measurement = capture()
        item = add_measurement_item(order_id=order.pk, measurement_id=measurement.pk, request_key=uuid4())
        duplicate_fields = {
            field.attname: getattr(item, field.attname) for field in OrderItem._meta.fields
            if field.name not in {"id", "created_at", "request_key"}
        }
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(**duplicate_fields, request_key=uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.filter(pk=item.pk).update(weight_grams=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.create(description="Outro", unit="KG", unit_price_cents=5000, is_scale_product=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Measurement.objects.filter(pk=measurement.pk).update(status="INVALID")


class SQLiteConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.product = create_scale_product()
        self.assertNotIn("memory", str(connection.settings_dict["NAME"]))
        self.assertTrue(str(connection.settings_dict["NAME"]).endswith(".sqlite3"))

    def race(self, *actions):
        """Race actions through distinct live SQLite connections, collecting conflicts."""
        barrier = Barrier(len(actions))

        def run(action):
            database = connections["default"]
            database.ensure_connection()
            identity = id(database.connection)
            try:
                barrier.wait(timeout=5)
                try:
                    return ("ok", action().pk, identity)
                except DomainConflict:
                    return ("conflict", None, identity)
            finally:
                database.close()

        with ThreadPoolExecutor(max_workers=len(actions)) as executor:
            results = list(executor.map(run, actions))
        self.assertEqual(len({result[2] for result in results}), len(actions))
        return results

    def test_same_capture_cannot_be_consumed_by_two_orders(self):
        first, second = open_order(request_key=uuid4()), open_order(request_key=uuid4())
        measurement = capture()
        results = self.race(*[
            lambda order_id=order.pk: add_measurement_item(order_id=order_id, measurement_id=measurement.pk, request_key=uuid4())
            for order in (first, second)
        ])
        self.assertEqual(sorted(result[0] for result in results), ["conflict", "ok"])
        self.assertEqual(OrderItem.objects.filter(active=True).count(), 1)
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, Measurement.Status.USED)

    def test_concurrent_retry_returns_one_item(self):
        order = open_order(request_key=uuid4())
        measurement = capture()
        key = uuid4()
        action = lambda: add_measurement_item(order_id=order.pk, measurement_id=measurement.pk, request_key=key)
        results = self.race(action, action)
        self.assertEqual([result[0] for result in results], ["ok", "ok"])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(OrderItem.objects.count(), 1)

    def test_concurrent_number_allocation_has_no_collision(self):
        results = self.race(*[lambda: open_order(request_key=uuid4()) for _ in range(8)])
        self.assertTrue(all(result[0] == "ok" for result in results))
        self.assertEqual(list(Order.objects.values_list("number", flat=True)), list(range(1, 9)))
        self.assertEqual(OrderSequence.objects.get().next_number, 9)

    def test_concurrent_open_retry_allocates_one_number(self):
        key = uuid4()
        action = lambda: open_order(request_key=key)
        results = self.race(action, action)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderSequence.objects.get().next_number, 2)

    def test_discard_and_consume_have_exactly_one_winner(self):
        order = open_order(request_key=uuid4())
        measurement = capture()
        results = self.race(
            lambda: discard_measurement(measurement.pk),
            lambda: add_measurement_item(order_id=order.pk, measurement_id=measurement.pk, request_key=uuid4()),
        )
        self.assertEqual(sorted(result[0] for result in results), ["conflict", "ok"])
        measurement.refresh_from_db()
        self.assertEqual(OrderItem.objects.count(), 1 if measurement.status == Measurement.Status.USED else 0)

    def test_duplicate_removal_releases_measurement_once(self):
        order = open_order(request_key=uuid4())
        measurement = capture()
        item = add_measurement_item(order_id=order.pk, measurement_id=measurement.pk, request_key=uuid4())
        action = lambda: remove_item(order_id=order.pk, item_id=item.pk)
        self.race(action, action)
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, Measurement.Status.AVAILABLE)
        self.assertEqual(DomainEvent.objects.filter(kind="ITEM_REMOVED").count(), 1)

    def test_cancel_and_inclusion_do_not_leave_active_items_on_cancelled_order(self):
        order = open_order(request_key=uuid4())
        measurement = capture()
        self.race(
            lambda: cancel_order(order.pk),
            lambda: add_measurement_item(order_id=order.pk, measurement_id=measurement.pk, request_key=uuid4()),
        )
        order.refresh_from_db()
        measurement.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(measurement.status, Measurement.Status.AVAILABLE)
        self.assertFalse(OrderItem.objects.filter(order=order, active=True).exists())

    def test_busy_database_returns_clear_conflict_without_allocating_number(self):
        connection.close()
        with sqlite3.connect(str(connection.settings_dict["NAME"]), timeout=0.1) as other:
            other.execute("BEGIN IMMEDIATE")
            try:
                connection.ensure_connection()
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA busy_timeout=50")
                with self.assertRaises(DomainConflict):
                    open_order(request_key=uuid4())
            finally:
                other.rollback()
                connection.close()
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderSequence.objects.count(), 0)


class DomainRecoveryTests(SimpleTestCase):
    def test_independent_process_recovers_drafts_snapshots_and_measurement_links(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=directory,
                               DJANGO_SETTINGS_MODULE="config.settings")
            initialized = subprocess.run(
                [sys.executable, "manage.py", "initialize_local"], cwd=settings.BASE_DIR,
                env=environment, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            prepare = '''
import django
django.setup()
from uuid import uuid4
from apps.products.services import save_product
from apps.orders.services import open_order, add_measurement_item, add_product_item
from apps.measurements.services import capture_measurement, discard_measurement
kg = save_product(description='Refeição por peso', unit='KG', unit_price_cents=5000, is_scale_product=True)
unit = save_product(description='À vontade', unit='UN', unit_price_cents=3590)
first = open_order(request_key=uuid4())
second = open_order(request_key=uuid4())
measurements = [capture_measurement(capture_key=uuid4(), net_weight_grams=weight) for weight in (252, 300, 400)]
add_measurement_item(order_id=first.pk, measurement_id=measurements[0].pk, request_key=uuid4())
add_product_item(order_id=second.pk, product_id=unit.pk, request_key=uuid4(), quantity_units=1)
discard_measurement(measurements[1].pk)
save_product(product_id=kg.pk, expected_revision=1, description='Novo preço', unit='KG', unit_price_cents=7000, is_scale_product=True)
'''
            recover = '''
import django
django.setup()
from uuid import uuid4
from apps.measurements.models import Measurement
from apps.measurements.selectors import available_measurements
from apps.orders.models import Order
from apps.orders.selectors import open_orders, subtotal_cents
from apps.orders.services import add_measurement_item, cancel_order
from apps.core.models import DomainEvent
first, second = list(open_orders())
assert [first.number, second.number] == [1, 2]
assert subtotal_cents(first.pk) == 1260
assert subtotal_cents(second.pk) == 3590
pending = available_measurements().get()
assert pending.net_weight_grams == 400 and pending.unit_price_cents == 5000
assert pending.product_description == 'Refeição por peso'
assert Measurement.objects.get(net_weight_grams=300).status == 'DISCARDED'
item = add_measurement_item(order_id=second.pk, measurement_id=pending.pk, request_key=uuid4())
assert item.total_cents == 2000 and subtotal_cents(second.pk) == 5590
cancel_order(first.pk)
assert available_measurements().get().net_weight_grams == 252
assert Order.objects.get(pk=second.pk).status == 'DRAFT'
assert DomainEvent.objects.filter(kind='MEASUREMENT_LINKED').count() == 2
'''
            for script in (prepare, recover):
                result = subprocess.run([sys.executable, "-c", script], cwd=settings.BASE_DIR,
                                        env=environment, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
