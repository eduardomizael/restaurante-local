"""Shared HTTP mutation gate for the explicitly running local application."""

from functools import wraps

from django.http import HttpResponse

from runtime.state import state


def requires_runtime(view):
    """Reject new POST operations when runtime is absent or stopping."""
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.method == "POST" and not state.snapshot()["running"]:
            return HttpResponse("Inicializador indisponível ou encerrando. Reabra o programa.", status=503)
        return view(request, *args, **kwargs)
    return guarded
