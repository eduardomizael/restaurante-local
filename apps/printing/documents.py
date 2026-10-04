"""Versioned document DTO and shared text layout, independent of transports."""

import hashlib
import json
import textwrap
import unicodedata
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
        "is_meal": _is_meal(item.product_description, item.unit),
    } for item in items]
    rows = []
    for product in products:
        inserted = [line for line in lines if line["product_id"] == product.pk]
        inserted = [line for line in inserted if not line["is_meal"]]
        if not inserted and (_is_meal(product.description, product.unit)
                             or not (product.active and product.appears_on_order_slip)):
            continue
        variants = []
        for line in inserted:
            variant = {key: line[key] for key in ("description", "unit", "unit_price_cents")}
            if variant not in variants:
                variants.append(variant)
        if not variants:
            variants = [{"description": product.description, "unit": product.unit,
                         "unit_price_cents": product.unit_price_cents}]
        for variant in variants:
            matching = [line for line in inserted if all(line[key] == variant[key]
                        for key in ("description", "unit", "unit_price_cents"))]
            variant["quantity_units"] = sum(line["quantity_units"] or 0 for line in matching)
            variant["total_cents"] = sum(line["total_cents"] for line in matching)
        rows.append({
            "product_id": product.pk, "description": variants[0]["description"], "variants": variants,
            "quantity_units": sum(line["quantity_units"] or 0 for line in inserted),
            "weight_grams": sum(line["weight_grams"] or 0 for line in inserted),
            "slip_order": product.slip_order,
        })
    price_columns = max([6] + [len(_money(variant["unit_price_cents"]))
                               for row in rows for variant in row["variants"]])
    return {
        "version": 3, "paper_width_mm": 80, "columns": 48,
        "layout": {"header_scale": 2, "name_columns": 20, "price_columns": price_columns},
        "order_id": order.pk, "order_number": order.number,
        "opened_at": timezone.localtime(order.created_at).isoformat(),
        "header": configuration.header if configuration else "",
        "footer": configuration.footer if configuration else "",
        "configuration_revision": configuration.revision if configuration else 0,
        "items": lines, "manuscript_rows": rows,
        "subtotal_cents": sum(line["total_cents"] for line in lines),
    }


def _is_meal(description, unit):
    """Identify weight meals and named fixed-price meals in the local catalogue."""
    name = " ".join(unicodedata.normalize("NFKD", description).encode("ascii", "ignore")
                    .decode("ascii").upper().split())
    return unit == "KG" or name.startswith("REFEICAO ") or name == "REFEICAO" or name.startswith("A VONTADE")


def _money(cents):
    return f"{Decimal(cents) / 100:.2f}".replace(".", ",")


def _kilograms(grams):
    return f"{Decimal(grams) / 1000:.3f}".replace(".", ",")


def render_header(content):
    """Render the frozen header at its physical character width."""
    scale = content.get("layout", {}).get("header_scale", 1) if content["version"] in (2, 3) else 1
    width = content["columns"] // scale
    lines = []
    for paragraph in content["header"].split("\n"):
        lines.extend(line.center(width) for line in
                     (textwrap.wrap(paragraph, width=width, replace_whitespace=False) or [""]))
    return "\n".join(lines) + "\n"


def preview_parts(content, *, second_copy=False):
    """Share header/body boundaries between HTML and the physical transport."""
    header = render_header(content)
    text = render_text(content, second_copy=second_copy)
    return {"slip_text": text, "slip_header": header, "slip_body": text[len(header):],
            "slip_header_scale": content.get("layout", {}).get("header_scale", 1)
            if content["version"] in (2, 3) else 1}


def render_text(content, *, second_copy=False):
    """Render continuous text from frozen DTO for preview and simulator.

    Args:
        content: Version 1, 2 or 3 document snapshot.
        second_copy: Add a delivery annotation without changing the document.

    Returns:
        str: Complete text with no page-height limit or transport commands.
    """
    if content.get("version") not in (1, 2, 3):
        raise ValueError("Versão documental não suportada.")
    width = content["columns"]
    output = []

    def append(value="", centered=False):
        for paragraph in str(value).split("\n"):
            for line in textwrap.wrap(paragraph, width=width, replace_whitespace=False) or [""]:
                output.append(line.center(width) if centered else line)

    output.extend(render_header(content).splitlines())
    append(f"COMANDA {content['order_number']}", centered=True)
    if second_copy:
        append("SEGUNDA VIA", centered=True)
    append("Finalização: " + content.get("finalized_at", "Prévia de rascunho"))
    append("-" * width)
    meal_layout = content["version"] in (3,)
    displayed_items = [item for item in content["items"] if item["is_meal"]] if meal_layout else content["items"]
    append("REFEIÇÕES PRÉ-INSERIDAS" if meal_layout else "ITENS PRÉ-INSERIDOS")
    for item in displayed_items:
        append(item["description"])
        quantity = (f"{item['quantity_units']} UN" if item["unit"] == "UN"
                    else f"{_kilograms(item['weight_grams'])} kg")
        append(f"{quantity} x R$ {_money(item['unit_price_cents'])}/{item['unit']}")
        if item["measurement_id"]:
            append(f"Pesagem #{item['measurement_id']}")
        append(f"VALOR R$ {_money(item['total_cents'])}")
        append()
    if meal_layout:
        append(f"SUBTOTAL REFEIÇÕES R$ {_money(sum(item['total_cents'] for item in displayed_items))}")
    else:
        append(f"SUBTOTAL PRÉ-INSERIDO R$ {_money(content['subtotal_cents'])}")
    append("-" * width)
    append("ACRÉSCIMOS MANUSCRITOS")
    compact = content["version"] in (2, 3)
    if compact:
        name_columns = content["layout"]["name_columns"]
        price_columns = content["layout"]["price_columns"]
        prefix_columns = name_columns + price_columns + 2
        marks = "[ ]" * ((width - prefix_columns) // 3)
        output.append(f"{'PRODUTO':<{name_columns}} {'R$':>{price_columns}} MARCAÇÕES")
    for row in content["manuscript_rows"]:
        for variant in row["variants"]:
            if compact:
                name = " ".join(variant["description"].split())
                if variant["unit"] == "KG":
                    name += " (KG)"
                name_lines = textwrap.wrap(name, width=name_columns)
                price = _money(variant["unit_price_cents"])
                row_marks = marks
                if meal_layout:
                    count = variant["quantity_units"]
                    capacity = len(marks) // 3
                    row_marks = "[X]" * min(count, capacity) + "[ ]" * max(capacity - count, 0)
                output.append(f"{name_lines[0]:<{name_columns}} {price:>{price_columns}} {row_marks}")
                output.extend(line.ljust(name_columns) for line in name_lines[1:])
                if meal_layout and variant["quantity_units"] and content["version"] == 3:
                    append(f"Lançado: {variant['quantity_units']} UN · R$ {_money(variant['total_cents'])}")
            else:
                append(f"{variant['description']} · R$ {_money(variant['unit_price_cents'])}/{variant['unit']}")
        quantities = []
        if row["quantity_units"]:
            quantities.append(f"{row['quantity_units']} UN")
        if row["weight_grams"]:
            quantities.append(f"{_kilograms(row['weight_grams'])} kg")
        if not meal_layout and (quantities or not compact):
            append("Já lançado: " + (" + ".join(quantities) or "nenhum"))
        if not compact:
            append("[   ] " * (width // 6))
            append()
    if compact:
        append("[X] = unidade já lançada; [ ] = acréscimo." if meal_layout
               else "Valores por unidade; (KG) indica preço/kg.")
    append("-" * width)
    if meal_layout:
        append(f"SUBTOTAL PRÉ-INSERIDO R$ {_money(content['subtotal_cents'])}")
    append("TOTAL A PAGAR R$ ______________________")
    append("Preenchimento manual após os acréscimos.")
    append()
    append(content["footer"], centered=True)
    return "\n".join(output) + "\n"
