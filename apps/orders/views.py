from uuid import uuid4

from django.core.exceptions import ValidationError
from django import forms
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.vary import vary_on_headers

from apps.core.domain import DomainConflict
from apps.core.http import requires_runtime
from apps.core.selectors import runtime_snapshot
from apps.measurements.selectors import available_measurements
from apps.measurements.services import discard_measurement
from apps.orders.forms import (
    ConfirmationForm, ManualItemForm, MeasurementItemForm, NextNumberForm, OpenOrderForm, RemoveItemForm,
)
from apps.orders.selectors import all_orders, attendance_snapshot, board_snapshot, next_order_number, subtotal_cents
from apps.orders.services import add_measurement_item, add_product_item, cancel_order, open_order, remove_item, set_next_number
from apps.products.selectors import active_products
from apps.orders.presentation import compact_layout, attendance_url


def _selected_id(request):
    value = request.GET.get("order")
    if not value:
        return None
    try:
        value = int(value)
    except (ValueError, TypeError):
        return -1
    return value if value > 0 else -1


def _attendance_redirect(request, order_id=None):
    url = attendance_url(request)
    return redirect(f"{url}?order={order_id}" if order_id is not None else url)


def _operation_error(request, error, order_id=None, status=409):
    messages = error.messages if isinstance(error, ValidationError) else [str(error)]
    if request.headers.get("HX-Request") == "true":
        response = render(request, "orders/action_error.html", {"errors": messages}, status=status)
        response["HX-Retarget"] = "#attendance-feedback"
        response["HX-Reswap"] = "innerHTML"
        return response
    return render(request, "orders/error.html", {"errors": messages, "order_id": order_id}, status=status)


def _board_response(request, data):
    """Refresh the shared lists and items with their explicit destination."""
    response = render(request, "orders/board_response.html", data)
    response["X-Selected-Order"] = str(data["selected_id"])
    return response


def _attendance_result(request, order_id, *, navigate=False):
    """Return affected fragments for HTMX and preserve ordinary form navigation."""
    if request.headers.get("HX-Request") != "true":
        return _attendance_redirect(request, order_id)
    runtime = runtime_snapshot()
    if navigate:
        template = "orders/alternative/workspace.html" if compact_layout(request) else "orders/workspace.html"
        data = attendance_snapshot(order_id)
        data["runtime"] = runtime
        response = render(request, template, data)
        response["HX-Push-Url"] = f"{attendance_url(request)}?order={order_id}"
        return response
    data = board_snapshot(order_id)
    data["runtime"] = runtime
    return _board_response(request, data)


@require_GET
@never_cache
@vary_on_headers("HX-Request")
def attendance(request):
    """Present drafts, captures and explicit catalogue/item actions."""
    search = request.GET.get("q", "").strip()[:120]
    runtime = runtime_snapshot()
    data = attendance_snapshot(_selected_id(request), search)
    data["runtime"] = runtime
    fragment = request.headers.get("HX-Request") == "true" and request.headers.get("HX-History-Restore-Request") != "true"
    template = "orders/workspace.html" if fragment else "orders/attendance.html"
    if compact_layout(request):
        template = "orders/alternative/workspace.html" if fragment else "orders/alternative/attendance.html"
    return render(request, template, data)


@require_GET
@never_cache
def product_choices(request):
    """Filter catalogue choices without replacing the search field or order."""
    data = attendance_snapshot(_selected_id(request), request.GET.get("q", "").strip()[:120])
    response = render(request, "orders/product_choices.html", data)
    response["X-Selected-Order"] = str(data["selected_id"])
    return response


@require_GET
@never_cache
def alternative_products(request):
    """Offer a normal navigation fallback for the alternative product picker."""
    data = attendance_snapshot(_selected_id(request), request.GET.get("q", "").strip()[:120])
    return render(request, "orders/alternative/products.html", data)


@require_GET
@never_cache
def board_fragment(request):
    """Read scale status before lists so a saved capture is already visible."""
    destination = _selected_id(request)
    runtime = runtime_snapshot()
    data = board_snapshot(destination if destination is not None else 0)
    data["runtime"] = runtime
    if destination is None:
        data["selected_id"] = ""
    if (request.GET.get("revision") == str(data["revision"])
            and request.GET.get("runtime_revision") == str(runtime["revision"])):
        return HttpResponse(status=204)
    return _board_response(request, data)


@require_POST
@never_cache
@requires_runtime
def create_order(request):
    """Open one idempotent draft using the submitted action key."""
    form = OpenOrderForm(request.POST)
    if not form.is_valid():
        return _operation_error(request, "Identificador de abertura inválido.", status=400)
    try:
        order = open_order(**form.cleaned_data)
    except ValidationError as exc:
        return _operation_error(request, exc)
    return _attendance_result(request, order.pk, navigate=True)


@require_http_methods(["GET", "POST"])
@never_cache
@vary_on_headers("HX-Request")
@requires_runtime
def manual_item(request, order_id, product_id):
    """Use product unit to parse quantity while fixing the route destination."""
    order = get_object_or_404(all_orders(), pk=order_id)
    product = get_object_or_404(active_products(), pk=product_id)
    form = ManualItemForm(request.POST if request.method == "POST" else None, unit=product.unit, initial={
        "order_id": order_id, "product_id": product_id, "request_key": uuid4(), "quantity_units": 1,
    })
    modal = request.headers.get("HX-Request") == "true"
    if modal:
        field_name = "weight_grams" if product.unit == "KG" else "quantity_units"
        precision = "3" if product.unit == "KG" else "0"
        form.fields[field_name].widget = forms.TextInput(attrs={
            "inputmode": "decimal" if product.unit == "KG" else "numeric",
            "autocomplete": "off", "data-item-value": precision,
        })
    response_status = 200
    if request.method == "POST":
        if form.is_valid():
            if (form.cleaned_data["order_id"], form.cleaned_data["product_id"]) != (order_id, product_id):
                form.add_error(None, "Destino da inclusão inválido. Reabra a ação na comanda desejada.")
                response_status = 409
            else:
                try:
                    add_product_item(**form.cleaned_data)
                except ValidationError as exc:
                    form.add_error(None, exc)
                    response_status = 409 if isinstance(exc, DomainConflict) else 400
                else:
                    response = _attendance_result(request, order_id)
                    if modal:
                        response["HX-Trigger-After-Swap"] = "manualItemAdded"
                    return response
        else:
            response_status = 400
    elif order.status != "DRAFT":
        return _operation_error(request, "Comanda encerrada não aceita novos itens.", order_id)
    template = "orders/manual_item_dialog.html" if modal else "orders/manual_item.html"
    response = render(request, template, {"form": form, "order": order, "product": product}, status=response_status)
    if modal:
        response["X-Selected-Order"] = str(order_id)
        response["X-Manual-Item-Fragment"] = "1"
        if response_status != 200:
            response["HX-Retarget"] = "#manual-item-content"
            response["HX-Reswap"] = "innerHTML"
    return response


@require_POST
@never_cache
@requires_runtime
def consume_measurement(request):
    """Consume a shared measurement for the submitted destination only."""
    form = MeasurementItemForm(request.POST)
    if not form.is_valid():
        return _operation_error(request, "Destino, medição ou identificador inválido.", status=400)
    order_id = form.cleaned_data["order_id"]
    try:
        add_measurement_item(**form.cleaned_data)
    except ValidationError as exc:
        return _operation_error(request, exc, order_id)
    return _attendance_result(request, order_id)


@require_POST
@never_cache
@requires_runtime
def delete_item(request):
    """Remove only an item belonging to the explicit destination draft."""
    form = RemoveItemForm(request.POST)
    if not form.is_valid():
        return _operation_error(request, "Item ou comanda inválidos.", status=400)
    order_id = form.cleaned_data["order_id"]
    try:
        remove_item(**form.cleaned_data)
    except ValidationError as exc:
        return _operation_error(request, exc, order_id)
    return _attendance_result(request, order_id)


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def confirm_cancel(request, order_id):
    """Show the selected order and explicitly confirm its cancellation."""
    order = get_object_or_404(all_orders(), pk=order_id)
    form = ConfirmationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if not form.is_valid():
            return _operation_error(request, "Confirme o cancelamento da comanda.", order_id, 400)
        try:
            cancel_order(order_id)
        except ValidationError as exc:
            return _operation_error(request, exc, order_id)
        return _attendance_redirect(request)
    return render(request, "orders/confirm.html", {
        "form": form, "title": f"Cancelar comanda {order.number}?", "order_id": order_id,
        "description": "Os itens serão removidos e as pesagens vinculadas voltarão à lista disponível.",
        "button_label": "Sim, cancelar comanda", "subtotal": subtotal_cents(order_id),
        "show_subtotal": True,
    })


@require_http_methods(["GET", "POST"])
@never_cache
@vary_on_headers("HX-Request")
@requires_runtime
def confirm_discard(request, measurement_id):
    """Confirm one manual discard without altering other captures or orders."""
    modal = request.headers.get("HX-Request") == "true"
    form = ConfirmationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        error = None
        status = 400
        if not form.is_valid():
            error = "Confirme o descarte da medição."
        else:
            try:
                discard_measurement(measurement_id)
            except ValidationError as exc:
                error = exc
                status = 409
        if error is not None:
            response = _operation_error(request, error, status=status)
            if modal:
                response["HX-Retarget"] = "#discard-measurement-feedback"
                response["X-Discard-Fragment"] = "1"
            return response
        destination = _selected_id(request)
        if modal and destination is None:
            data = board_snapshot(0)
            data["selected_id"] = ""
            data["runtime"] = runtime_snapshot()
            response = _board_response(request, data)
        else:
            response = _attendance_result(request, destination)
        if modal:
            response["HX-Trigger-After-Swap"] = "measurementDiscarded"
        return response
    measurement = get_object_or_404(available_measurements(), pk=measurement_id)
    template = "orders/discard_dialog_content.html" if modal else "orders/confirm.html"
    return render(request, template, {
        "form": form, "title": f"Descartar medição {measurement.pk}?",
        "description": "Somente esta pesagem será retirada da lista disponível.",
        "button_label": "Sim, descartar medição", "measurement": measurement,
        "order_id": _selected_id(request),
    })


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def numbering(request):
    """Edit the sequence through the same touch-friendly parsing and service."""
    form = NextNumberForm(request.POST if request.method == "POST" else None, initial={"number": next_order_number()})
    response_status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                set_next_number(form.cleaned_data["number"])
            except ValidationError as exc:
                form.add_error(None, exc)
                response_status = 409
            else:
                return _attendance_redirect(request)
        else:
            response_status = 400
    return render(request, "orders/numbering.html", {"form": form}, status=response_status)
