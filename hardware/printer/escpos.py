"""RAW ESC/POS framing for the observed POS-80 profile; no I/O."""

from hardware.printer.results import PrintFailure


def encode_document(text, *, header_lines=0, header_scale=1):
    """Encode the shared text strictly, rejecting unsupported text before I/O."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines(keepends=True)
    if (type(header_lines) is not int or not 0 <= header_lines <= len(lines)
            or header_scale not in (1, 2)):
        raise PrintFailure("Formatação do cabeçalho inválida.")
    if any(ord(char) < 32 and char != "\n" for char in text):
        raise PrintFailure("Documento contém caracteres de controle não permitidos.")
    try:
        encoded = text.encode("cp860", errors="strict")
    except UnicodeEncodeError as exc:
        raise PrintFailure("Documento contém caractere não suportado pelo perfil cp860. Revise o texto.") from exc
    # ESC @ initialize, ESC t 3 selects cp860 on this provisional POS-80 profile.
    # Three feed lines and full cut; paper height is never capped at 210 mm.
    if header_lines and header_scale == 2:
        header = "".join(lines[:header_lines]).encode("cp860")
        body = "".join(lines[header_lines:]).encode("cp860")
        encoded = b"\x1d!\x11" + header + b"\x1d!\x00" + body
    return b"\x1b@\x1bt\x03" + encoded + b"\n\n\n\x1dV\x00"
