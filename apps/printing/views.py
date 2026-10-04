from uuid import uuid4

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.domain import DomainConflict
from apps.core.http import requires_runtime
from apps.configuration.selectors import hardware_configuration
from runtime.state import state
from apps.orders.models import Order
from apps.printing.documents import fingerprint, preview_parts
from apps.printing.forms import DocumentConfigurationForm, FinalizeForm, ReprintForm
from apps.printing.models import OrderDocument, PrintJob
from apps.printing.selectors import document_configuration, document_jobs, draft_content, order_document, print_history
from apps.printing.services import finalize_order, request_reprint, save_document_configuration


def _error(request, error):
    return render(request, "orders/error.html", {"errors": error.messages}, status=409)


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def configuration(request):
    """Edit document-only settings without touching equipment."""
    saved = document_configuration()
    form = DocumentConfigurationForm(request.POST if request.method == "POST" else None, initial={
        "header": saved.header if saved else "", "footer": saved.footer if saved else "",
        "expected_revision": saved.revision if saved else 0,
    })
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                save_document_configuration(**form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
                status = 409 if isinstance(exc, DomainConflict) else 400
            else:
                return redirect("document_configuration")
        else:
            status = 400
    return render(request, "printing/configuration.html", {"form": form}, status=status)


@require_GET
@never_cache
def preview(request, order_id):
    """Show the same complete text consumed by the simulated transport."""
    order = get_object_or_404(Order, pk=order_id)
    document = order_document(order_id)
    if document is None and order.status != Order.Status.DRAFT:
        return _error(request, ValidationError("Comanda cancelada não possui documento para impressão."))
    content = document.content if document else draft_content(order)
    form = FinalizeForm(initial={"request_key": uuid4(), "expected_fingerprint": fingerprint(content),
                                 "reviewed_mode": state.snapshot()["print_mode"],
                                 "printer_revision": hardware_configuration().revision})
    return render(request, "printing/preview.html", {
        "order": order, "document": document, **preview_parts(content), "form": form,
        "can_finalize": bool(content["header"] and content["items"]),
        "jobs": document_jobs(document.pk) if document else [],
    })


@require_POST
@never_cache
@requires_runtime
def finalize(request, order_id):
    """Finalize only the explicit route destination after reviewed preview."""
    form = FinalizeForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Identificador ou revisão da prévia inválidos.", status=400)
    try:
        values = dict(form.cleaned_data)
        reviewed_mode = values.pop("reviewed_mode")
        printer_revision = values.pop("printer_revision")
        if reviewed_mode != state.snapshot()["print_mode"]:
            raise DomainConflict("Modo de impressão mudou após a prévia. Revise novamente.")
        finalize_order(order_id=order_id, delivery_mode=reviewed_mode,
                       expected_printer_revision=printer_revision, **values)
    except ValidationError as exc:
        return _error(request, exc)
    return redirect("print_preview", order_id=order_id)


@require_GET
@never_cache
def history(request):
    """Expose frozen documents and every delivery outcome."""
    return render(request, "printing/history.html", {"documents": print_history()})


@require_GET
@never_cache
def job_fragment(request, document_id):
    """Refresh delivery statuses independently of the immutable paper preview."""
    get_object_or_404(OrderDocument, pk=document_id)
    return render(request, "printing/jobs.html", {"document_id": document_id, "jobs": document_jobs(document_id)})


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def reprint(request, document_id):
    """Require an explicit second-copy action, including uncertain outcomes."""
    document = get_object_or_404(OrderDocument.objects.select_related("order"), pk=document_id)
    form = ReprintForm(request.POST if request.method == "POST" else None, initial={
        "request_key": uuid4(), "reviewed_mode": state.snapshot()["print_mode"],
        "printer_revision": hardware_configuration().revision,
    })
    if request.method == "POST":
        if not form.is_valid():
            return HttpResponse("Confirme a solicitação de segunda via.", status=400)
        try:
            if form.cleaned_data["reviewed_mode"] != state.snapshot()["print_mode"]:
                raise DomainConflict("Modo de impressão mudou após a revisão. Reabra a segunda via.")
            request_reprint(document_id=document_id, request_key=form.cleaned_data["request_key"],
                            delivery_mode=state.snapshot()["print_mode"],
                            expected_printer_revision=form.cleaned_data["printer_revision"])
        except ValidationError as exc:
            return _error(request, exc)
        return redirect("print_preview", order_id=document.order_id)
    return render(request, "printing/reprint.html", {
        "document": document, "form": form, **preview_parts(document.content, second_copy=True),
        "uncertain": document.jobs.filter(status=PrintJob.Status.UNKNOWN).exists(),
    })
