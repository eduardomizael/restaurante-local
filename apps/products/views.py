from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.core.domain import DomainConflict
from apps.core.http import requires_runtime
from apps.products.forms import ProductFlagForm, ProductForm, ProductOrderForm, ScaleProductForm
from apps.products.selectors import catalogue_products, catalogue_snapshot, product_ordering_snapshot, scale_product, scale_product_choices
from apps.products.services import reorder_products, save_product, set_product_flag
from apps.core.selectors import runtime_snapshot
from apps.orders.presentation import attendance_url


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def choose_scale_product(request):
    """Choose a scale product through the existing atomic catalogue service."""
    errors, status = [], 200
    if request.method == "POST":
        form = ScaleProductForm(request.POST)
        if form.is_valid():
            try:
                set_product_flag(**form.cleaned_data, flag="is_scale_product", enabled=True)
            except ValidationError as exc:
                errors = (["Produto alterado. Escolha novamente."]
                          if isinstance(exc, DomainConflict) else exc.messages)
                status = 409 if isinstance(exc, DomainConflict) else 400
            else:
                if request.headers.get("HX-Request") != "true":
                    return redirect(attendance_url(request))
                response = render(request, "core/scale_fragment.html", {
                    "runtime": runtime_snapshot(), "scale_product": scale_product(),
                })
                response["HX-Retarget"] = "#runtime-status"
                response["HX-Reswap"] = "outerHTML"
                response["HX-Trigger-After-Settle"] = "scaleProductSelected"
                return response
        else:
            errors, status = ["Seleção inválida. Escolha novamente."], 400
    response = render(request, "products/scale_dialog_content.html", {
        "products": scale_product_choices(), "errors": errors,
    }, status=status)
    response["X-Scale-Product-Fragment"] = "1"
    return response


def _catalogue_context(search, errors=()):
    """Keep the selected scale product visible independently of search results."""
    return {
        **catalogue_snapshot(search), "search": search, "errors": errors,
    }


@require_GET
@never_cache
def catalogue(request):
    """Present search and all product flags for touch editing."""
    search = request.GET.get("q", "").strip()[:120]
    return render(request, "products/catalogue.html", _catalogue_context(search))


@require_POST
@never_cache
@requires_runtime
def update_order(request):
    """Save list ordering and return authoritative cards on success or conflict."""
    form = ProductOrderForm(request.POST)
    errors, status = [], 200
    if form.is_valid():
        try:
            reorder_products(**form.cleaned_data)
        except ValidationError as exc:
            errors = exc.messages
            status = 409 if isinstance(exc, DomainConflict) else 400
    else:
        errors, status = ["Ordem inválida. A lista salva foi recuperada; tente novamente."], 400
    if request.headers.get("HX-Request") != "true" and not errors:
        return redirect("product_ordering")
    context = {**product_ordering_snapshot(), "errors": errors}
    context["order_saved_kind"] = form.cleaned_data.get("kind") if not errors else None
    context["order_error_kind"] = form.cleaned_data.get("kind") if errors else None
    context["order_error"] = " ".join(errors)
    template = "products/ordering_results.html" if request.headers.get("HX-Request") == "true" else "products/ordering_page.html"
    response = render(request, template, context, status=status)
    response["X-Catalogue-Fragment"] = "1"
    return response


@require_GET
@never_cache
def ordering_page(request):
    """Present the independent ordering lists in their own product subsection."""
    return render(request, "products/ordering_page.html", product_ordering_snapshot())


@require_POST
@never_cache
@requires_runtime
def update_flag(request, product_id):
    """Save one tag and return current cards, including both scale selections."""
    search = request.POST.get("q", "").strip()[:120]
    form = ProductFlagForm(request.POST)
    errors = []
    status = 200
    if form.is_valid():
        try:
            set_product_flag(product_id=product_id, **form.cleaned_data)
        except ValidationError as exc:
            errors = (["Produto alterado em outra tela. As opções foram atualizadas; confira e tente novamente."]
                      if isinstance(exc, DomainConflict) else exc.messages)
            status = 409 if isinstance(exc, DomainConflict) else 400
    else:
        errors = [str(error) for messages in form.errors.values() for error in messages]
        status = 400
    if not request.headers.get("HX-Request") and not errors:
        return redirect(f"{reverse('catalogue')}?{urlencode({'q': search})}")
    template = "products/results.html" if request.headers.get("HX-Request") else "products/catalogue.html"
    response = render(request, template, _catalogue_context(search, errors), status=status)
    response["X-Catalogue-Fragment"] = "1"
    return response


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def edit_product(request, product_id=None):
    """Parse catalogue edits, reject stale revisions and delegate persistence."""
    product = get_object_or_404(catalogue_products(), pk=product_id) if product_id is not None else None
    initial = {}
    if product:
        initial = {name: getattr(product, name) for name in ProductForm.base_fields if name != "expected_revision"}
        initial["unit_price_cents"] = f"{Decimal(product.unit_price_cents) / 100:.2f}".replace(".", ",")
        initial["expected_revision"] = product.revision
    form = ProductForm(request.POST if request.method == "POST" else None, initial=initial)
    response_status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                save_product(product_id=product_id, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
                response_status = 409 if isinstance(exc, DomainConflict) else 400
            else:
                return redirect("catalogue")
        else:
            response_status = 400
    return render(request, "products/edit.html", {"form": form, "product": product}, status=response_status)
