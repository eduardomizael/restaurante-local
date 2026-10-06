"""Primary compact attendance and the legacy alternative preserve operations."""

from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.orders.models import OrderItem
from apps.orders.services import open_order
from apps.products.services import save_product
from apps.printing.services import save_document_configuration
from runtime.state import state


class AlternativeAttendanceTests(TestCase):
    def setUp(self):
        state.update(running=True)
        self.order = open_order(request_key=uuid4())
        self.other = open_order(request_key=uuid4())
        self.product = save_product(description="Suco", unit="UN", unit_price_cents=700, is_quick_access=True)
        self.url = reverse("home")
        self.manual_url = reverse("manual_item", args=[self.order.pk, self.product.pk])

    def tearDown(self):
        state.update(running=False)

    def test_layouts_remain_separate_and_use_same_selected_order(self):
        current = self.client.get(reverse("attendance_alternative"), {"order": self.order.pk})
        self.assertTemplateUsed(current, "orders/attendance.html")
        self.assertNotContains(current, 'id="product-picker-dialog"')
        alternative = self.client.get(self.url, {"order": self.order.pk})
        self.assertTemplateUsed(alternative, "orders/alternative/attendance.html")
        self.assertContains(alternative, 'id="product-picker-dialog"')
        self.assertContains(alternative, f'href="{self.url}?order={self.other.pk}"')
        self.assertEqual(alternative.context["selected"], self.order)

    def test_quick_panel_and_full_catalogue_are_separate(self):
        normal = save_product(description="Produto fora do acesso rápido", unit="UN", unit_price_cents=900)
        response = self.client.get(self.url, {"order": self.order.pk})
        self.assertTemplateUsed(response, "orders/alternative/quick_picker.html")
        self.assertTemplateUsed(response, "orders/alternative/catalogue_picker.html")
        self.assertContains(response, 'id="quick-product-cards"', count=1)
        self.assertContains(response, 'id="product-search"', count=1)
        self.assertContains(response, 'input delay:200ms, submit')
        self.assertContains(response, normal.description, count=1)
        self.assertContains(response, self.product.description, count=2)

    def test_filter_returns_matches_and_empty_filter_restores_catalogue(self):
        save_product(description="Água", unit="UN", unit_price_cents=500)
        route = reverse("product_choices")
        response = self.client.get(route, {"order": self.order.pk, "layout": "primary", "q": "suc"})
        self.assertContains(response, "Suco")
        self.assertNotContains(response, "Água")
        response = self.client.get(route, {"order": self.order.pk, "layout": "primary", "q": ""})
        self.assertContains(response, "Suco")
        self.assertContains(response, "Água")

    def test_selection_fragment_keeps_alternative_workspace(self):
        response = self.client.get(self.url, {"order": self.other.pk}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "orders/alternative/workspace.html")
        self.assertContains(response, 'data-layout="primary"')
        self.assertNotContains(response, "<html")

    def test_new_order_stays_on_alternative_route(self):
        response = self.client.post(reverse("create_order"), {
            "request_key": uuid4(),
        }, HTTP_HX_REQUEST="true")
        self.assertTrue(response["HX-Push-Url"].startswith(self.url + "?order="))
        self.assertTemplateUsed(response, "orders/alternative/workspace.html")

    def test_modal_insertion_refreshes_alternative_panel_once(self):
        response = self.client.get(self.manual_url, HTTP_HX_REQUEST="true")
        self.assertContains(response, f'hx-post="{self.manual_url}"')
        data = {"order_id": self.order.pk, "product_id": self.product.pk,
                "quantity_units": 2, "request_key": uuid4()}
        response = self.client.post(self.manual_url, data, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "orders/alternative/order_panel.html")
        self.assertContains(response, "R$ 14,00")
        self.assertEqual(response["HX-Trigger-After-Swap"], "manualItemAdded")
        self.client.post(self.manual_url, data, HTTP_HX_REQUEST="true")
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(OrderItem.objects.get().order_id, self.order.pk)

    def test_normal_insertion_redirect_and_confirmation_keep_layout(self):
        response = self.client.post(self.manual_url, {
            "order_id": self.order.pk, "product_id": self.product.pk,
            "quantity_units": 1, "request_key": uuid4(),
        })
        self.assertRedirects(response, f"{self.url}?order={self.order.pk}")
        response = self.client.get(reverse("confirm_cancel", args=[self.order.pk]))
        self.assertContains(response, f'href="{self.url}?order={self.order.pk}"')

    def test_search_and_poll_preserve_alternative_item_links_and_panel(self):
        response = self.client.get(reverse("product_choices"), {
            "order": self.order.pk, "q": "Suco", "layout": "primary",
        }, HTTP_HX_REQUEST="true")
        self.assertContains(response, self.manual_url)
        response = self.client.get(reverse("board_fragment"), {
            "order": self.order.pk, "layout": "primary",
        }, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "orders/alternative/order_panel.html")
        self.assertContains(response, 'hx-swap-oob="outerHTML"')

    def test_unknown_layout_keeps_current_route(self):
        response = self.client.get(reverse("home"), {"layout": "unknown"})
        self.assertTemplateUsed(response, "orders/alternative/attendance.html")

    def test_legacy_alternative_preserves_action_and_preview_destinations(self):
        old_url = reverse("attendance_alternative")
        page = self.client.get(old_url, {"order": self.order.pk})
        self.assertTemplateUsed(page, "orders/attendance.html")
        self.assertContains(page, 'name="layout" value="alternative"')
        self.assertContains(page, reverse("print_preview", args=[self.order.pk]) + "?layout=alternative")
        manual = reverse("manual_item", args=[self.order.pk, self.product.pk]) + "?layout=alternative"
        response = self.client.post(manual, {
            "order_id": self.order.pk, "product_id": self.product.pk,
            "quantity_units": 1, "request_key": uuid4(),
        })
        self.assertRedirects(response, f"{old_url}?order={self.order.pk}")
        board = self.client.get(reverse("board_fragment"), {
            "order": self.order.pk, "layout": "alternative",
        }, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(board, "orders/order_panel.html")
        self.assertContains(board, reverse("delete_item") + "?layout=alternative")
        response = self.client.post(reverse("create_order") + "?layout=alternative", {
            "request_key": uuid4(),
        }, HTTP_HX_REQUEST="true")
        self.assertTrue(response["HX-Push-Url"].startswith(old_url))
        self.assertTemplateUsed(response, "orders/workspace.html")

    def test_reviewed_preview_print_redirect_preserves_alternative(self):
        self.client.post(self.manual_url, {
            "order_id": self.order.pk, "product_id": self.product.pk,
            "quantity_units": 1, "request_key": uuid4(),
        })
        save_document_configuration(header="Restaurante de teste", footer="", expected_revision=0)
        preview = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertContains(preview, f'href="{self.url}?order={self.order.pk}"')
        response = self.client.post(reverse("print_open_order", args=[self.order.pk]),
                                    preview.context["form"].initial)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("layout=alternative", response.url)
        saved = self.client.get(response.url)
        self.assertContains(saved, f'href="{self.url}?order={self.order.pk}"')

    def print_dialog(self):
        state.update(print_mode="PREVIEW")
        self.client.post(self.manual_url, {
            "order_id": self.order.pk, "product_id": self.product.pk,
            "quantity_units": 1, "request_key": uuid4(),
        })
        save_document_configuration(header="Restaurante de teste", footer="", expected_revision=0)
        return self.client.get(reverse("print_preview", args=[self.order.pk]), {
            "layout": "primary", "dialog": "print",
        }, HTTP_HX_REQUEST="true")

    def test_print_dialog_and_full_page_are_separate(self):
        response = self.print_dialog()
        self.assertTemplateUsed(response, "printing/preview_dialog.html")
        self.assertNotContains(response, "<html")
        self.assertContains(response, "Imprimir e fechar")
        full = self.client.get(reverse("print_preview", args=[self.order.pk]))
        self.assertTemplateUsed(full, "printing/preview.html")
        self.assertContains(full, "<html")

    def test_dialog_print_keeps_order_open_and_finalize_closes_only_selected(self):
        from apps.orders.models import Order
        from apps.printing.models import OrderDocument
        response = self.print_dialog()
        data = {**response.context["form"].initial, "return_to_attendance": "1"}
        response = self.client.post(reverse("print_open_order", args=[self.order.pk]),
                                    data, HTTP_HX_REQUEST="true")
        self.assertEqual(response["HX-Redirect"], f"{self.url}?order={self.order.pk}")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DRAFT)
        self.assertEqual(OrderDocument.objects.count(), 1)
        from threading import Event
        from runtime.print_worker import PrintWorker
        PrintWorker(Event()).process_one()
        preview = self.client.get(reverse("print_preview", args=[self.order.pk]), {
            "layout": "primary", "dialog": "print",
        }, HTTP_HX_REQUEST="true")
        response = self.client.post(reverse("finalize_order", args=[self.order.pk]),
                                    {**preview.context["form"].initial, "return_to_attendance": "1"},
                                    HTTP_HX_REQUEST="true")
        self.assertEqual(response["HX-Redirect"], self.url)
        self.order.refresh_from_db()
        self.other.refresh_from_db()
        self.assertNotEqual(self.order.status, Order.Status.DRAFT)
        self.assertEqual(self.other.status, Order.Status.DRAFT)

    def test_stale_dialog_preview_returns_error_without_printing(self):
        from apps.printing.models import OrderDocument
        preview = self.print_dialog()
        self.client.post(self.manual_url, {
            "order_id": self.order.pk, "product_id": self.product.pk,
            "quantity_units": 1, "request_key": uuid4(),
        })
        response = self.client.post(reverse("print_open_order", args=[self.order.pk]),
                                    {**preview.context["form"].initial, "return_to_attendance": "1"},
                                    HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["X-Print-Preview-Fragment"], "1")
        self.assertTemplateUsed(response, "printing/preview_dialog.html")
        self.assertFalse(OrderDocument.objects.exists())
