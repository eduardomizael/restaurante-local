"""Read-only access to the configured Windows printer queue."""

from hardware.printer.windows_raw import WindowsSpooler


def printer_availability(name, *, spooler_factory=WindowsSpooler):
    """Return queue access and reported conditions, without printing anything."""
    spooler = spooler_factory()
    handle = spooler.open(name)
    try:
        flags = spooler.status(handle)
    finally:
        spooler.close(handle)
    conditions = (
        (0x00000080, "Offline"), (0x00001000, "Indisponível"),
        (0x00000004, "Fila em remoção"), (0x00000001, "Impressão pausada"),
        (0x00000010, "Sem papel"), (0x00000008, "Papel preso"),
        (0x00000040, "Problema com o papel"), (0x00400000, "Tampa aberta"),
        (0x00040000, "Sem tinta ou toner"), (0x00000800, "Bandeja de saída cheia"),
        (0x00200000, "Memória insuficiente"), (0x00000020, "Aguardando papel manual"),
        (0x00080000, "Falha ao imprimir a página"),
        (0x00100000, "Precisa de atenção"), (0x00000002, "Erro informado pelo Windows"),
    )
    messages = [message for mask, message in conditions if flags & mask]
    if messages:
        return "UNAVAILABLE", "; ".join(messages)
    if flags & 0x00800000:
        return "UNKNOWN", "Windows não informou o estado da impressora."
    return "AVAILABLE", "Fila acessível; o Windows não informou impedimentos."
