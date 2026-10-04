from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.configuration.forms import ApplicationConfigurationForm, HardwareConfigurationForm
from apps.configuration.selectors import application_configuration, hardware_configuration
from apps.configuration.services import save_application_configuration, save_hardware_configuration
from apps.core.domain import DomainConflict
from apps.core.http import requires_runtime


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def general(request):
    """Edit the name displayed throughout the application."""
    saved = application_configuration()
    form = ApplicationConfigurationForm(request.POST if request.method == "POST" else None, initial={
        "display_name": saved.display_name, "expected_revision": saved.revision,
    })
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                save_application_configuration(**form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
                status = 409 if isinstance(exc, DomainConflict) else 400
            else:
                return redirect("application_configuration")
        else:
            status = 400
    return render(request, "configuration/general.html", {"form": form}, status=status)


@require_http_methods(["GET", "POST"])
@never_cache
@requires_runtime
def equipment(request):
    """Edit names without opening serial ports or submitting print jobs."""
    saved = hardware_configuration()
    form = HardwareConfigurationForm(request.POST if request.method == "POST" else None, initial={
        "scale_port": saved.scale_port, "printer_name": saved.printer_name, "expected_revision": saved.revision,
    })
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                save_hardware_configuration(**form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
                status = 409 if isinstance(exc, DomainConflict) else 400
            else:
                return redirect("equipment_configuration")
        else:
            status = 400
    return render(request, "configuration/equipment.html", {"form": form}, status=status)
