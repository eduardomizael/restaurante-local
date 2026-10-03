import re

from django.core.exceptions import ValidationError

from apps.configuration.models import HardwareConfiguration
from apps.core.domain import DomainConflict, require_integer, write_transaction
from apps.core.services import record_event


def save_hardware_configuration(*, scale_port, printer_name, expected_revision):
    """Save equipment names atomically, leaving physical I/O to workers."""
    if not isinstance(scale_port, str) or not re.fullmatch(r"COM[1-9][0-9]{0,3}", scale_port.strip().upper()):
        raise ValidationError("Porta deve usar COM seguida de um número positivo.")
    if (not isinstance(printer_name, str) or not 1 <= len(printer_name.strip()) <= 120
            or any(ord(char) < 32 for char in printer_name)):
        raise ValidationError("Nome da impressora deve conter de 1 a 120 caracteres válidos.")
    require_integer(expected_revision, minimum=0, maximum=2_147_483_647, label="Revisão")
    with write_transaction():
        current = HardwareConfiguration.objects.filter(pk=1).first()
        if (current.revision if current else 0) != expected_revision:
            raise DomainConflict("Equipamentos alterados em outra tela. Recarregue antes de salvar.")
        if current is None:
            current = HardwareConfiguration(pk=1)
        else:
            current.revision += 1
        current.scale_port, current.printer_name = scale_port.strip().upper(), printer_name.strip()
        current.save()
        record_event("HARDWARE_CONFIGURATION_SAVED", current, revision=current.revision,
                     scale_port=current.scale_port, printer_name=current.printer_name)
        return current
