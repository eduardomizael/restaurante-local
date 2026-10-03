"""Commercial writes serialized by short SQLite IMMEDIATE transactions."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.domain import DomainConflict, calculate_weight_total, require_integer, require_uuid, write_transaction
from apps.core.services import record_event
from apps.measurements.models import Measurement
from apps.orders.models import Order, OrderItem, OrderSequence
from apps.products.models import Product

MAX_ORDER_NUMBER = 2_147_483_647


def _draft(order_id):
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        raise ValidationError("Comanda não encontrada.")
    if order.status != Order.Status.DRAFT:
        raise DomainConflict("Comanda encerrada não aceita alterações.")
    return order


def open_order(*, request_key):
    """Allocate one unique number, returning the same order on a retried action.

    Args:
        request_key: Stable UUID identifying the user's open-order action.

    Returns:
        Order: New or previously created order.
    """
    key = require_uuid(request_key)
    with write_transaction():
        existing = Order.objects.filter(request_key=key).first()
        if existing:
            return existing
        sequence, _ = OrderSequence.objects.get_or_create(pk=1)
        number = sequence.next_number
        while Order.objects.filter(number=number).exists():
            number += 1
        require_integer(number, maximum=MAX_ORDER_NUMBER, label="Número da comanda")
        order = Order.objects.create(number=number, request_key=key)
        sequence.next_number = number + 1
        sequence.save(update_fields=["next_number"])
        record_event("ORDER_OPENED", order, number=number)
        return order


def set_next_number(number):
    """Set an unused positive next number without renumbering any history."""
    require_integer(number, maximum=MAX_ORDER_NUMBER, label="Próximo número")
    with write_transaction():
        if Order.objects.filter(number=number).exists():
            raise DomainConflict("Este número já foi usado, inclusive por comanda encerrada.")
        sequence, _ = OrderSequence.objects.get_or_create(pk=1)
        if sequence.next_number != number:
            previous = sequence.next_number
            sequence.next_number = number
            sequence.save(update_fields=["next_number"])
            record_event("ORDER_SEQUENCE_CHANGED", sequence, previous=previous, next_number=number)
        return sequence


def add_product_item(*, order_id, product_id, request_key, quantity_units=None, weight_grams=None):
    """Add a manual unit or kilogram snapshot without consuming a measurement.

    Args:
        order_id: Explicit destination order, independent of browser selection.
        product_id: Active catalogue product.
        request_key: Stable UUID for this inclusion, reused only for retries.
        quantity_units: Positive whole quantity for UN products.
        weight_grams: Positive parsed grams for KG products.

    Returns:
        OrderItem: New or previously saved immutable snapshot.
    """
    key = require_uuid(request_key)
    if quantity_units is not None:
        require_integer(quantity_units, maximum=100_000, label="Quantidade")
    if weight_grams is not None:
        require_integer(weight_grams, maximum=1_000_000, label="Peso")
    with write_transaction():
        existing = OrderItem.objects.filter(request_key=key).first()
        if existing:
            if (existing.order_id, existing.product_id, existing.source, existing.quantity_units, existing.weight_grams) != (order_id, product_id, OrderItem.Source.MANUAL, quantity_units, weight_grams):
                raise DomainConflict("Identificador de inclusão já usado com outros dados.")
            return existing
        order = _draft(order_id)
        product = Product.objects.filter(pk=product_id, active=True).first()
        if product is None:
            raise ValidationError("Produto não encontrado ou inativo.")
        if product.unit == Product.Unit.UNIT:
            if weight_grams is not None or quantity_units is None:
                raise ValidationError("Produto em UN exige quantidade inteira, sem peso.")
            total = require_integer(product.unit_price_cents * quantity_units, minimum=0, label="Total")
        else:
            if quantity_units is not None or weight_grams is None:
                raise ValidationError("Produto em KG exige peso, sem quantidade unitária.")
            total = calculate_weight_total(product.unit_price_cents, weight_grams)
        item = OrderItem.objects.create(
            order=order, product=product, request_key=key, source=OrderItem.Source.MANUAL,
            product_description=product.description, unit=product.unit, quantity_units=quantity_units,
            weight_grams=weight_grams, unit_price_cents=product.unit_price_cents, total_cents=total,
        )
        record_event("ITEM_ADDED", item, order_id=order.pk, source=item.source, total_cents=total)
        return item


def add_measurement_item(*, order_id, measurement_id, request_key):
    """Consume an AVAILABLE capture exactly once, preserving captured prices.

    Args:
        order_id: Explicit destination draft order.
        measurement_id: Shared measurement selected by the user.
        request_key: Stable UUID for this inclusion action.

    Returns:
        OrderItem: New or previously saved item for this exact action.

    Raises:
        DomainConflict: Measurement is unavailable or the action key conflicts.
    """
    key = require_uuid(request_key)
    with write_transaction():
        existing = OrderItem.objects.filter(request_key=key).first()
        if existing:
            if (existing.order_id, existing.measurement_id, existing.source) != (order_id, measurement_id, OrderItem.Source.SCALE):
                raise DomainConflict("Identificador de inclusão já usado para outro destino ou medição.")
            return existing
        order = _draft(order_id)
        measurement = Measurement.objects.filter(pk=measurement_id).first()
        if measurement is None:
            raise ValidationError("Medição não encontrada.")
        consumed = Measurement.objects.filter(pk=measurement.pk, status=Measurement.Status.AVAILABLE).update(status=Measurement.Status.USED)
        if consumed != 1:
            raise DomainConflict("Esta medição já foi utilizada ou descartada.")
        item = OrderItem.objects.create(
            order=order, product_id=measurement.product_id, measurement=measurement,
            request_key=key, source=OrderItem.Source.SCALE,
            product_description=measurement.product_description, unit=Product.Unit.KILOGRAM,
            weight_grams=measurement.net_weight_grams, unit_price_cents=measurement.unit_price_cents,
            total_cents=measurement.total_cents,
        )
        record_event("MEASUREMENT_LINKED", item, order_id=order.pk, measurement_id=measurement.pk)
        return item


def _remove(item):
    if not item.active:
        return
    item.active = False
    item.removed_at = timezone.now()
    item.save(update_fields=["active", "removed_at"])
    if item.measurement_id:
        released = Measurement.objects.filter(pk=item.measurement_id, status=Measurement.Status.USED).update(status=Measurement.Status.AVAILABLE)
        if released != 1:
            raise DomainConflict("Vínculo da medição inconsistente; nenhuma alteração foi salva.")
    record_event("ITEM_REMOVED", item, order_id=item.order_id, measurement_id=item.measurement_id)


def remove_item(*, order_id, item_id):
    """Undo a draft item without deleting history, releasing its measurement."""
    with write_transaction():
        _draft(order_id)
        item = OrderItem.objects.filter(pk=item_id, order_id=order_id).first()
        if item is None:
            raise ValidationError("Item não pertence à comanda selecionada.")
        _remove(item)
        return item


def cancel_order(order_id):
    """Cancel only one draft and release its links, preserving available captures."""
    with write_transaction():
        order = Order.objects.filter(pk=order_id).first()
        if order is None:
            raise ValidationError("Comanda não encontrada.")
        if order.status == Order.Status.CANCELLED:
            return order
        _draft(order_id)
        for item in OrderItem.objects.filter(order=order, active=True):
            _remove(item)
        order.status = Order.Status.CANCELLED
        order.cancelled_at = timezone.now()
        order.save(update_fields=["status", "cancelled_at"])
        record_event("ORDER_CANCELLED", order, number=order.number)
        return order
