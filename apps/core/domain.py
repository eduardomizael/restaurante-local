"""Shared validation, exact commercial arithmetic and short write transactions."""

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction

MAX_MONEY_CENTS = 9_000_000_000_000


class DomainConflict(ValidationError):
    """An operation conflicts with persisted state or an idempotency key."""


def require_integer(value, *, minimum=1, maximum=MAX_MONEY_CENTS, label="Valor"):
    """Validate an integer without coercing floats or booleans.

    Args:
        value: Parsed integer to validate.
        minimum: Inclusive lower limit.
        maximum: Inclusive upper limit.
        label: User-facing field name.

    Returns:
        int: Validated value.

    Raises:
        ValidationError: Value has an invalid type or range.
    """
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(f"{label} deve ser inteiro entre {minimum} e {maximum}.")
    return value


def require_uuid(value):
    """Validate an explicit request/capture identity."""
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Identificador da operação inválido.") from exc


def calculate_weight_total(price_cents, weight_grams):
    """Calculate a kilogram-priced total with half-up rounding to cents."""
    require_integer(price_cents, minimum=0, label="Preço")
    require_integer(weight_grams, maximum=1_000_000, label="Peso em gramas")
    total = int((Decimal(price_cents) * weight_grams / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return require_integer(total, minimum=0, label="Total")


@contextmanager
def write_transaction():
    """Acquire SQLite's IMMEDIATE transaction and translate busy conflicts."""
    try:
        with transaction.atomic():
            yield
    except OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise DomainConflict("Banco ocupado. Tente novamente com o mesmo identificador da operação.") from exc
        raise
