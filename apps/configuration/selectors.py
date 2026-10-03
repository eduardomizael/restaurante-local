from types import SimpleNamespace

from apps.configuration.models import HardwareConfiguration


def hardware_configuration():
    """Read configuration, using confirmed COM3/balanca defaults before setup."""
    return HardwareConfiguration.objects.filter(pk=1).first() or SimpleNamespace(
        scale_port="COM3", printer_name="balanca", revision=0,
    )
