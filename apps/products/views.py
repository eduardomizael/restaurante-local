from decimal import Decimal

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.domain import DomainConflict
from apps.core.http import requires_runtime
from apps.products.forms import ProductForm
from apps.products.selectors import catalogue_products
from apps.products.services import save_product


@require_GET
@never_cache
def catalogue(request):
    """Present search and all product flags for touch editing."""
    search = request.GET.get("q", "").strip()[:120]
    return render(request, "products/catalogue.html", {"products": catalogue_products(search), "search": search})


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
