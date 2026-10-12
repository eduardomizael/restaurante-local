from decimal import Decimal
from time import monotonic

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
    snapshot["scale_equipment"] = equipment_status(snapshot, "scale")
    snapshot["printer_equipment"] = equipment_status(snapshot, "printer")
    return snapshot


def equipment_status(snapshot, equipment):
    """Describe cached equipment access without hardware or database I/O."""
    scale = equipment == "scale"
    checked = snapshot["scale_last_response" if scale else "printer_checked_at"]
    result = {"device": snapshot["scale_device" if scale else "printer_device"],
              "checked_at": checked, "tone": "unknown"}
    if not snapshot["running"]:
        return {**result, "label": "Não verificado", "message": "Inicializador parado."}
    if snapshot["scale_mode" if scale else "print_mode"] != ("SERIAL" if scale else "RAW"):
        return {**result, "label": "Modo simulado", "message": "Equipamento físico não verificado."}
    if scale and snapshot["paused"]:
        return {**result, "label": "Leitura pausada", "message": "Retome a leitura para verificar a balança."}
    tick = snapshot["scale_last_response_tick" if scale else "printer_checked_tick"]
    access = snapshot["scale_access" if scale else "printer_access"]
    message = snapshot["scale_access_message" if scale else "printer_access_message"]
    if tick is not None and monotonic() - tick > (5 if scale else 30) and (not scale or access == "AVAILABLE"):
        return {**result, "label": "Aguardando confirmação", "message": "A última verificação está desatualizada."}
    labels = {"AVAILABLE": "Respondendo" if scale else "Disponível no Windows",
              "NO_RESPONSE": "Sem resposta", "UNAVAILABLE": "Indisponível", "UNKNOWN": "Não confirmado"}
    return {**result, "label": labels[access], "message": message,
            "tone": "ok" if access == "AVAILABLE" else "error" if access in ("UNAVAILABLE", "NO_RESPONSE") else "unknown"}
