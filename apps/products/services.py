from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone

from apps.core.domain import DomainConflict, require_integer, write_transaction
from apps.core.services import record_event
from apps.products.models import Product


def set_product_flag(*, product_id, flag, enabled, expected_revision):
    """Set one catalogue flag without overwriting other product fields.

    Args:
        product_id: Product being edited.
        flag: One of the three editable catalogue flag names.
        enabled: Explicit desired boolean value.
        expected_revision: Revision displayed when the action was requested.

    Returns:
        Product: Saved product, with an atomic scale selection transfer if needed.

    Raises:
        ValidationError: Invalid flag, product, value or stale revision.
    """
    if flag not in {"is_scale_product", "is_quick_access", "appears_on_order_slip"}:
        raise ValidationError("Opção de produto inválida.")
    if type(enabled) is not bool:
        raise ValidationError("Opção do produto deve ser booleana.")
    require_integer(expected_revision, minimum=1, label="Revisão")
    with write_transaction():
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            raise ValidationError("Produto não encontrado.")
        values = {name: getattr(product, name) for name in (
            "description", "unit", "unit_price_cents", "active", "is_scale_product",
            "is_quick_access", "appears_on_order_slip", "quick_access_order", "slip_order",
        )}
        values[flag] = enabled
        return save_product(product_id=product.pk, expected_revision=expected_revision, **values)


def save_product(*, description, unit, unit_price_cents, product_id=None, expected_revision=None,
                 active=True, is_scale_product=False, is_quick_access=False,
                 appears_on_order_slip=False, quick_access_order=0, slip_order=0):
    """Create or update catalogue values without changing historical snapshots.

    Args:
        description: Product name.
        unit: UN or KG.
        unit_price_cents: Nonnegative integer unit/kg price.
        product_id: Existing product identity, or None for creation.
        expected_revision: Required revision when updating to reject stale edits.
        active: Whether the product is available for new items.
        is_scale_product: Whether this is the unique active scale product.
        is_quick_access: Whether it is offered as a quick action.
        appears_on_order_slip: Whether to reserve a manuscript line.
        quick_access_order: Nonnegative quick-access sorting position.
        slip_order: Nonnegative manuscript sorting position.

    Returns:
        Product: Saved current catalogue record.

    Raises:
        ValidationError: Invalid data, missing product or stale revision.
    """
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 120:
        raise ValidationError("Descrição deve conter de 1 a 120 caracteres.")
    if unit not in Product.Unit.values:
        raise ValidationError("Unidade deve ser UN ou KG.")
    for flag in (active, is_scale_product, is_quick_access, appears_on_order_slip):
        if type(flag) is not bool:
            raise ValidationError("Opções do produto devem ser booleanas.")
    require_integer(unit_price_cents, minimum=0, label="Preço em centavos")
    require_integer(quick_access_order, minimum=0, maximum=2_147_483_647, label="Ordem rápida")
    require_integer(slip_order, minimum=0, maximum=2_147_483_647, label="Ordem no papel")
    if is_scale_product and (unit != Product.Unit.KILOGRAM or not active):
        raise ValidationError("Produto da balança deve estar ativo e usar KG.")
    values = dict(description=description.strip(), unit=unit, unit_price_cents=unit_price_cents,
                  active=active, is_scale_product=is_scale_product, is_quick_access=is_quick_access,
                  appears_on_order_slip=appears_on_order_slip, quick_access_order=quick_access_order,
                  slip_order=slip_order)
    with write_transaction():
        product = Product() if product_id is None else Product.objects.filter(pk=product_id).first()
        if product is None:
            raise ValidationError("Produto não encontrado.")
        if product_id is not None and product.revision != expected_revision:
            raise DomainConflict("Produto alterado em outra tela. Recarregue antes de salvar.")
        if is_scale_product:
            for previous in Product.objects.filter(is_scale_product=True).exclude(pk=product_id):
                Product.objects.filter(pk=previous.pk).update(
                    is_scale_product=False, revision=F("revision") + 1, updated_at=timezone.now(),
                )
                record_event("SCALE_PRODUCT_UNSELECTED", previous)
        for field, value in values.items():
            setattr(product, field, value)
        if product_id is not None:
            product.revision += 1
        product.save()
        record_event("PRODUCT_SAVED", product, **values, revision=product.revision)
        return product
