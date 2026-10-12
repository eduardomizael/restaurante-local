"""Continuous 80 mm report text shared by browser preview and print worker."""

from datetime import datetime
from decimal import Decimal
import textwrap


def render_report(content):
    """Render a frozen totals report within the existing 48-column profile."""
    if content.get("version") != 1:
        raise ValueError("Versão de relatório não suportada.")
    lines = []

    def append(value):
        lines.extend(textwrap.wrap(str(value), width=48) or [""])

    append(content["header"])
    append("RELATÓRIO DE TOTAIS")
    first = datetime.fromisoformat(content["start"]).strftime("%d/%m/%Y")
    last = datetime.fromisoformat(content["end"]).strftime("%d/%m/%Y")
    append(f"Período: {first} a {last}")
    append("Gerado: " + datetime.fromisoformat(content["generated_at"]).strftime("%d/%m/%Y %H:%M:%S"))
    append("Seleção pela data de abertura da comanda.")
    append("Situações no momento da geração.")
    append("-" * 48)
    append(f"Abertas: {content['opened']}")
    append(f"Fechadas: {content['closed']}")
    append(f"Canceladas: {content['cancelled']}")
    append("-" * 48)
    append("ITENS DAS COMANDAS FECHADAS")
    for item in content["items"]:
        append(item["description"])
        quantity = (f"{item['quantity']} UN" if item["unit"] == "UN" else
                    f"{Decimal(item['weight']) / 1000:.3f} kg".replace(".", ","))
        value = f"R$ {Decimal(item['total_cents']) / 100:.2f}".replace(".", ",")
        append(f"{quantity} - {value}")
    if not content["items"]:
        append("Nenhum item de comanda fechada.")
    append("-" * 48)
    append(f"VALOR TOTAL R$ {Decimal(content['total_cents']) / 100:.2f}".replace(".", ","))
    append("Somente itens registrados no sistema.")
    append("Anotações à mão não entram nos totais.")
    append("Não representa confirmação de pagamento.")
    return "\n".join(lines) + "\n"
