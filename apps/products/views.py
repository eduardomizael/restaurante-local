from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.core.domain import DomainConflict
from apps.core.http import requires_runtime
from apps.products.forms import ProductFlagForm, ProductForm
from apps.products.selectors import catalogue_products, catalogue_snapshot
from apps.products.services import save_product, set_product_flag


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
