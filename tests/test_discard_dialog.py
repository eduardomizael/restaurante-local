"""Measurement discard confirmation within attendance."""

from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.measurements.models import Measurement
from apps.measurements.services import capture_measurement
from apps.orders.services import add_measurement_item, open_order
from apps.products.services import save_product
from runtime.state import state


class DiscardDialogTests(TestCase):
    def setUp(self):
        state.update(running=True)
        save_product(description="Refeição", unit="KG", unit_price_cents=5000, is_scale_product=True)
        self.order = open_order(request_key=uuid4())
        self.measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=300)
        self.other = capture_measurement(capture_key=uuid4(), net_weight_grams=400)
        self.url = reverse("confirm_discard", args=[self.measurement.pk]) + f"?order={self.order.pk}"

    def tearDown(self):
        state.update(running=False)

    def test_both_layouts_open_fragment_without_discarding(self):
        for route in ("home", "attendance_alternative"):
            response = self.client.get(reverse(route), {"order": self.order.pk})
            self.assertContains(response, 'id="discard-measurement-dialog"')
            self.assertContains(response, 'hx-target="#discard-measurement-content"')
        response = self.client.get(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(response, "0,300 kg")
        self.assertContains(response, "R$ 15,00")
        self.assertContains(response, "Voltar sem alterar")
        self.assertContains(response, 'hx-target="#shared-board"')
        self.assertNotContains(response, "<html")
        self.assertEqual(Measurement.objects.filter(status="AVAILABLE").count(), 2)

    def test_confirmation_refreshes_board_and_only_discards_selection(self):
        for layout in ("", "&layout=alternative"):
            measurement = capture_measurement(capture_key=uuid4(), net_weight_grams=250)
            url = reverse("confirm_discard", args=[measurement.pk]) + f"?order={self.order.pk}" + layout
            response = self.client.post(url, {"confirm": "True"}, HTTP_HX_REQUEST="true")
            self.assertContains(response, 'id="shared-board"')
            self.assertNotContains(response, "<html")
            self.assertEqual(response["HX-Trigger-After-Swap"], "measurementDiscarded")
            self.assertEqual(response["X-Selected-Order"], str(self.order.pk))
            measurement.refresh_from_db()
            self.assertEqual(measurement.status, "DISCARDED")
        self.assertEqual(Measurement.objects.filter(status="AVAILABLE").count(), 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "DRAFT")

    def test_missing_confirmation_and_concurrent_use_keep_errors_in_dialog(self):
        response = self.client.post(self.url, {}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["HX-Retarget"], "#discard-measurement-feedback")
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.status, "AVAILABLE")
        add_measurement_item(order_id=self.order.pk, measurement_id=self.measurement.pk, request_key=uuid4())
        response = self.client.post(self.url, {"confirm": "True"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["HX-Retarget"], "#discard-measurement-feedback")
        self.assertEqual(response["X-Discard-Fragment"], "1")
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.status, "USED")

    def test_without_order_and_normal_navigation_fallback(self):
        url = reverse("confirm_discard", args=[self.measurement.pk])
        self.assertContains(self.client.get(url), "<html")
        response = self.client.post(url, {"confirm": "True"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="shared-board"')
        self.assertEqual(response["X-Selected-Order"], "")
        response = self.client.post(reverse("confirm_discard", args=[self.other.pk]), {"confirm": "True"})
        self.assertEqual(response.status_code, 302)
