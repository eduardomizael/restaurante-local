from decimal import Decimal

from runtime.state import state

STATUS_LABELS = {
    "STOPPED": "Leitura parada", "PAUSED": "Leitura pausada",
    "SIMULATED": "Leitura simulada", "ERROR": "Falha de leitura",
    "WAITING_ZERO": "Retire o prato e aguarde zerar",
    "RECOVERING": "Sem resposta. Aguarde",
    "MEASURING": "Pode colocar o prato",
    "STABILIZING": "Aguardando estabilidade",
    "WAITING_REMOVAL": "Pesagem salva. Retire o prato",
    "CONFIG_REQUIRED": "Escolha o produto da balança",
}

STATUS_ICONS = {
    "MEASURING": "✓", "WAITING_REMOVAL": "✓",
    "STABILIZING": "…", "SIMULATED": "≈",
    "WAITING_ZERO": "↑", "RECOVERING": "!",
    "ERROR": "!", "CONFIG_REQUIRED": "!",
    "STOPPED": "■", "PAUSED": "Ⅱ",
}


def runtime_snapshot():
    """Read coherent technical state with presentation values."""
    snapshot = state.snapshot()
    snapshot["weight_kg"] = f"{Decimal(snapshot['weight_grams']) / 1000:.3f}".replace(".", ",")
    snapshot["scale_label"] = STATUS_LABELS[snapshot["scale_status"]]
    snapshot["scale_icon"] = STATUS_ICONS[snapshot["scale_status"]]
    return snapshot
