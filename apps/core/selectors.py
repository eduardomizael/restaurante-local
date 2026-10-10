from decimal import Decimal

from runtime.state import state

STATUS_LABELS = {
    "STOPPED": "Leitura parada", "PAUSED": "Leitura pausada",
    "SIMULATED": "Leitura simulada", "ERROR": "Falha de leitura",
    "WAITING_ZERO": "Captura bloqueada · retire o prato e aguarde retorno ao zero",
    "RECOVERING": "Balança sem resposta · aguardando novas leituras válidas",
    "MEASURING": "Pronta para o próximo prato",
    "STABILIZING": "Aguardando peso estável",
    "WAITING_REMOVAL": "Peso fixado · pesagem salva · aguardando zero",
    "CONFIG_REQUIRED": "Selecione um produto ativo em KG no cadastro",
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
