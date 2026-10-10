from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.domain import DomainConflict, calculate_weight_total, require_integer, require_uuid, write_transaction
from apps.core.services import record_event
from apps.measurements.models import Measurement
from apps.products.selectors import scale_product


def capture_measurement(*, capture_key, net_weight_grams, tare_grams=0, device="SIMULATOR", stability_parameters=None,
                        expected_product_id=None, expected_product_revision=None):
    """Persist one explicitly stable capture with immutable commercial values.

    Args:
        capture_key: Stable UUID for retries of this physical capture.
        net_weight_grams: Positive net weight, already excluding tare.
        tare_grams: Informative tare, or None when not transmitted; never subtracted again.
        device: Adapter identity for history.
        stability_parameters: JSON-compatible parameters used for stability.
        expected_product_id: Optional product identity observed by the cycle.
        expected_product_revision: Optional observed revision to reject changes mid-cycle.

    Returns:
        Measurement: Existing or newly persisted capture.

    Raises:
        ValidationError: No selected product, invalid weight or conflicting retry.
    """
    key = require_uuid(capture_key)
    require_integer(net_weight_grams, maximum=1_000_000, label="Peso líquido")
    if tare_grams is not None:
        require_integer(tare_grams, minimum=0, maximum=1_000_000, label="Tara")
    if not isinstance(device, str) or not 1 <= len(device.strip()) <= 120:
        raise ValidationError("Dispositivo inválido.")
    parameters = {} if stability_parameters is None else stability_parameters
    if not isinstance(parameters, dict):
        raise ValidationError("Parâmetros de estabilidade devem ser um objeto.")
    with write_transaction():
        existing = Measurement.objects.filter(capture_key=key).first()
        if existing:
            if (existing.net_weight_grams, existing.tare_grams, existing.device, existing.stability_parameters) != (net_weight_grams, tare_grams, device.strip(), parameters):
                raise DomainConflict("Identificador de captura já usado com outros dados.")
            return existing
        product = scale_product()
        if product is None:
            raise DomainConflict("Selecione um produto ativo em KG antes de capturar medições.")
        if expected_product_id is not None and (product.pk, product.revision) != (expected_product_id, expected_product_revision):
            raise DomainConflict("Produto da balança mudou durante a captura; aguarde retorno ao zero.")
        measurement = Measurement.objects.create(
            capture_key=key, product=product, product_description=product.description,
            unit_price_cents=product.unit_price_cents,
            total_cents=calculate_weight_total(product.unit_price_cents, net_weight_grams),
            net_weight_grams=net_weight_grams, tare_grams=tare_grams, device=device.strip(),
            stability_parameters=parameters,
        )
        record_event("MEASUREMENT_CAPTURED", measurement, net_weight_grams=net_weight_grams,
                     unit_price_cents=measurement.unit_price_cents, total_cents=measurement.total_cents)
        return measurement


def discard_measurement(measurement_id):
    """Discard only an explicitly selected available capture, idempotently."""
    with write_transaction():
        measurement = Measurement.objects.filter(pk=measurement_id).first()
        if measurement is None:
            raise ValidationError("Medição não encontrada.")
        if measurement.status == Measurement.Status.DISCARDED:
            return measurement
        updated = Measurement.objects.filter(pk=measurement.pk, status=Measurement.Status.AVAILABLE).update(
            status=Measurement.Status.DISCARDED, discard_reason="MANUAL_DISCARD", discarded_at=timezone.now(),
        )
        if updated != 1:
            raise DomainConflict("Somente medições disponíveis podem ser descartadas.")
        measurement.refresh_from_db()
        record_event("MEASUREMENT_DISCARDED", measurement, reason="MANUAL_DISCARD")
        return measurement
