"""Shared HTTP mutation gate for the explicitly running local application."""

from functools import wraps

from django.http import HttpResponse
from django.template.response import TemplateResponse

from runtime.state import state


class ShutdownResponse(TemplateResponse):
    """Signal shutdown after WSGI delivers the last page to the operator."""

    shutdown_handler = None

    def close(self):
        """Close the response and send the stop signal once."""
        handler, self.shutdown_handler = self.shutdown_handler, None
        try:
            super().close()
        finally:
            if handler is not None:
                handler()


def requires_runtime(view):
    """Reject new POST operations when runtime is absent or stopping."""
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.method == "POST" and not state.snapshot()["running"]:
            return HttpResponse("Inicializador indisponível ou encerrando. Reabra o programa.", status=503)
        return view(request, *args, **kwargs)
    return guarded
