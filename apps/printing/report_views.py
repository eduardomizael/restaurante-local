"""Read report pages and accept explicit, signed snapshot printing requests."""

from datetime import date
from uuid import uuid4

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.configuration.selectors import application_configuration, hardware_configuration
from apps.core.http import requires_runtime
from apps.printing.models import PrintJob
from apps.printing.report_documents import render_report
from apps.printing.report_forms import PeriodForm, ReportPrintForm, TotalsForm
from apps.printing.report_selectors import order_report, totals_report
from apps.printing.report_services import request_report_print
from runtime.state import state

SNAPSHOT_SALT = "printing.totals.v1"


def _period_data(request, *, totals=False):
    """Default to today only on the initial visit, retaining invalid user input."""
    if request.GET:
        return request.GET
    today = timezone.localdate().isoformat()
    return {"start": today, "end": today, **({"mode": "period"} if totals else {})}


@require_GET
@never_cache
def orders(request):
    """Show every order once, with all saved print versions nested inside it."""
    form = PeriodForm(_period_data(request))
    page = None
    if form.is_valid():
        page = Paginator(order_report(**form.cleaned_data), 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    if form.is_valid():
        query["start"] = form.cleaned_data["start"].isoformat()
        query["end"] = form.cleaned_data["end"].isoformat()
    return render(request, "reports/orders.html", {"form": form, "page": page, "period_query": query.urlencode(),
                                                  "report_section": "orders"})


@require_GET
@never_cache
def totals(request):
    """Preview one consolidated summary or a complete list of daily reports."""
    form = TotalsForm(_period_data(request, totals=True))
    reports, print_form = [], None
    if form.is_valid():
        contents = totals_report(**form.cleaned_data, header=application_configuration().display_name)
        print_form = ReportPrintForm(initial={
            "request_key": uuid4(), "reviewed_mode": state.snapshot()["print_mode"],
            "printer_revision": hardware_configuration().revision,
            "snapshot": signing.dumps(contents, salt=SNAPSHOT_SALT, compress=True), "selection": "all",
        })
        reports = [{"content": content, "text": render_report(content),
                    "day": date.fromisoformat(content["start"])} for content in contents]
    return render(request, "reports/totals.html", {"form": form, "reports": reports, "print_form": print_form,
                                                  "report_section": "totals"})


@require_POST
@never_cache
@requires_runtime
def print_totals(request):
    """Print exactly the reviewed snapshot, never recomputing it on POST."""
    form = ReportPrintForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Solicitação inválida. Gere o relatório novamente.", status=400)
    data = form.cleaned_data
    try:
        reports = signing.loads(data["snapshot"], salt=SNAPSHOT_SALT, max_age=3600)
    except signing.BadSignature:
        return HttpResponse("Prévia inválida ou expirada. Gere o relatório novamente.", status=400)
    if data["reviewed_mode"] != state.snapshot()["print_mode"]:
        return HttpResponse("Modo de impressão mudou. Gere o relatório novamente.", status=409)
    try:
        batch_key = request_report_print(reports=reports, selection=data["selection"], request_key=data["request_key"],
                                         delivery_mode=data["reviewed_mode"], expected_printer_revision=data["printer_revision"])
    except ValidationError as exc:
        return render(request, "orders/error.html", {"errors": exc.messages}, status=409)
    return redirect("report_print_result", batch_key=batch_key)


@require_GET
@never_cache
def print_result(request, batch_key):
    """Show persistent results, including uncertain deliveries without auto retry."""
    jobs = list(PrintJob.objects.filter(report_batch_key=batch_key).order_by("pk"))
    if not jobs:
        raise Http404
    for job in jobs:
        job.report_start = date.fromisoformat(job.report_content["start"])
        job.report_end = date.fromisoformat(job.report_content["end"])
    template = "reports/results_content.html" if request.GET.get("fragment") == "1" else "reports/results.html"
    return render(request, template, {"jobs": jobs, "batch_key": batch_key, "report_section": "totals",
                                     "pending": any(job.status in ("PENDING", "SUBMITTING") for job in jobs)})
