"""Versioned document DTO and shared text layout, independent of transports."""

import hashlib
import json
import textwrap
from decimal import Decimal

from django.utils import timezone


def fingerprint(content):
    """Hash the canonical commercial content to detect edits after preview."""
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def build_content(order, items, products, configuration):
    """Create serializable snapshots, grouping manuscript lines by product.

    Args:
        order: Explicit draft identity.
        items: Active historical item snapshots in display order.
        products: Active marked products plus products referenced by items.
        configuration: Saved header/footer, or None for defaults.

    Returns:
        dict: Versioned DTO with integer quantities and commercial amounts.
    """
    lines = [{
        "id": item.pk, "product_id": item.product_id, "description": item.product_description,
        "unit": item.unit, "quantity_units": item.quantity_units, "weight_grams": item.weight_grams,
        "unit_price_cents": item.unit_price_cents, "total_cents": item.total_cents,
        "source": item.source, "measurement_id": item.measurement_id,
    } for item in items]
    rows = []
    for product in products:
        inserted = [line for line in lines if line["product_id"] == product.pk]
        variants = []
        for line in inserted:
            variant = {key: line[key] for key in ("description", "unit", "unit_price_cents")}
            if variant not in variants:
                variants.append(variant)
        if not variants:
            variants = [{"description": product.description, "unit": product.unit,
                         "unit_price_cents": product.unit_price_cents}]
        rows.append({
            "product_id": product.pk, "description": variants[0]["description"], "variants": variants,
            "quantity_units": sum(line["quantity_units"] or 0 for line in inserted),
            "weight_grams": sum(line["weight_grams"] or 0 for line in inserted),
            "slip_order": product.slip_order,
        })
    return {
        "version": 1, "paper_width_mm": 80, "columns": 48,
        "order_id": order.pk, "order_number": order.number,
        "opened_at": timezone.localtime(order.created_at).isoformat(),
        "header": configuration.header if configuration else "",
        "footer": configuration.footer if configuration else "",
        "configuration_revision": configuration.revision if configuration else 0,
        "items": lines, "manuscript_rows": rows,
        "subtotal_cents": sum(line["total_cents"] for line in lines),
    }


def _money(cents):
    return f"{Decimal(cents) / 100:.2f}".replace(".", ",")


def _kilograms(grams):
    return f"{Decimal(grams) / 1000:.3f}".replace(".", ",")


def render_text(content, *, second_copy=False):
    """Render continuous text from frozen DTO for preview and simulator.

    Args:
        content: Version 1 document snapshot.
        second_copy: Add a delivery annotation without changing the document.

    Returns:
        str: Complete text with no page-height limit or transport commands.
    """
    if content.get("version") != 1:
        raise ValueError("Versão documental não suportada.")
    width = content["columns"]
    output = []

    def append(value="", centered=False):
        for paragraph in str(value).split("\n"):
            for line in textwrap.wrap(paragraph, width=width, replace_whitespace=False) or [""]:
                output.append(line.center(width) if centered else line)

    append(content["header"], centered=True)
    append(f"COMANDA {content['order_number']}", centered=True)
    if second_copy:
        append("SEGUNDA VIA", centered=True)
    append("Finalização: " + content.get("finalized_at", "Prévia de rascunho"))
    append("-" * width)
    append("ITENS PRÉ-INSERIDOS")
    for item in content["items"]:
        append(item["description"])
        quantity = (f"{item['quantity_units']} UN" if item["unit"] == "UN"
                    else f"{_kilograms(item['weight_grams'])} kg")
        append(f"{quantity} x R$ {_money(item['unit_price_cents'])}/{item['unit']}")
        if item["measurement_id"]:
            append(f"Pesagem #{item['measurement_id']}")
        append(f"VALOR R$ {_money(item['total_cents'])}")
        append()
    append(f"SUBTOTAL PRÉ-INSERIDO R$ {_money(content['subtotal_cents'])}")
    append("-" * width)
    append("ACRÉSCIMOS MANUSCRITOS")
    for row in content["manuscript_rows"]:
        for variant in row["variants"]:
            append(f"{variant['description']} · R$ {_money(variant['unit_price_cents'])}/{variant['unit']}")
        quantities = []
        if row["quantity_units"]:
            quantities.append(f"{row['quantity_units']} UN")
        if row["weight_grams"]:
            quantities.append(f"{_kilograms(row['weight_grams'])} kg")
        append("Já lançado: " + (" + ".join(quantities) or "nenhum"))
        append("[   ] " * (width // 6))
        append()
    append("-" * width)
    append("TOTAL A PAGAR R$ ______________________")
    append("Preenchimento manual após os acréscimos.")
    append()
    append(content["footer"], centered=True)
    return "\n".join(output) + "\n"
