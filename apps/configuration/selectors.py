from types import SimpleNamespace

from apps.configuration.models import ApplicationConfiguration, HardwareConfiguration


def application_configuration():
    """Read display identity without creating a configuration on page access."""
    return ApplicationConfiguration.objects.filter(pk=1).first() or SimpleNamespace(
        display_name="Restaurante Local", revision=0,
    )


def hardware_configuration():
    """Read configuration, using confirmed COM3/balanca defaults before setup."""
    return HardwareConfiguration.objects.filter(pk=1).first() or SimpleNamespace(
        scale_port="COM3", printer_name="balanca", revision=0,
    )
