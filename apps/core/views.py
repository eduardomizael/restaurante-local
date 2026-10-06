from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.core.selectors import runtime_snapshot
from runtime.state import state
from apps.core.http import ShutdownResponse


@require_GET
@never_cache
def status_page(request):
    """Present runtime diagnostics."""
    return render(request, "core/status.html", {"runtime": runtime_snapshot()})


@require_GET
@never_cache
def status_fragment(request):
    """Return the technical polling fragment."""
    template = "core/scale_fragment.html" if request.GET.get("surface") == "attendance" else "core/status_fragment.html"
    return render(request, template, {"runtime": runtime_snapshot()})


@require_GET
@never_cache
@ensure_csrf_cookie
def health(request):
    """Identify the explicitly started process and its readiness."""
    snapshot = state.snapshot()
    return JsonResponse({
        "application": "local-weighing", "ready": snapshot["running"],
        "instance_id": snapshot.get("instance_id"),
    }, status=200 if snapshot["running"] else 503)


@require_POST
@never_cache
def open_window(request):
    """Accept local launcher control with CSRF and a private runtime capability."""
    try:
        state.open_browser(request.headers.get("X-Local-Browser-Token", ""))
    except PermissionError as exc:
        return HttpResponse(str(exc), status=403)
    except (OSError, RuntimeError) as exc:
        return HttpResponse(str(exc), status=409)
    return HttpResponse(status=204)


@require_POST
@never_cache
def toggle_pause(request):
    """Pause or resume the explicit runtime after CSRF validation."""
    try:
        state.toggle_pause()
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    return render(request, "core/status_fragment.html", {"runtime": runtime_snapshot()})


@require_GET
@never_cache
def shutdown_confirmation(request):
    """Ask for an explicit touch-friendly shutdown confirmation."""
    return render(request, "core/shutdown_confirmation.html", {"runtime": runtime_snapshot()})


@require_POST
@never_cache
def shutdown(request):
    """Prepare controlled runtime shutdown after delivering the final page."""
    if request.POST.get("confirmed") != "yes":
        return HttpResponse("Confirme o encerramento na tela da aplicação.", status=400)
    response = ShutdownResponse(None, "core/shutdown_requested.html")
    response.render()
    try:
        response.shutdown_handler = state.prepare_shutdown()
    except RuntimeError as exc:
        return HttpResponse(str(exc), status=409)
    return response


@require_GET
def asset(request, name):
    """Serve only bundled assets, independently of DEBUG."""
    assets = {
        "app.css": ("app.css", "text/css"),
        "app.js": ("app.js", "text/javascript"),
        "htmx.min.js": ("vendor/htmx.min.js", "text/javascript"),
    }
    if name not in assets:
        raise Http404
    relative, content_type = assets[name]
    path = settings.BASE_DIR / "static" / relative
    if not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"), content_type=content_type)
