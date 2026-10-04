"""RAW ESC/POS framing for the observed POS-80 profile; no I/O."""

import base64
import binascii

from hardware.printer.results import PrintFailure


def encode_logo(logo):
    """Frame a bounded raster, centered above text without changing text alignment."""
    if not logo:
        return b""
    try:
        width, height = logo["width"], logo["height"]
        if (type(width) is not int or type(height) is not int
                or not 1 <= width <= 384 or not 1 <= height <= 192):
            raise ValueError("Invalid raster dimensions")
        width_bytes = (width + 7) // 8
        encoded = logo["raster_base64"]
        if not isinstance(encoded, str) or len(encoded) > 12_288:
            raise ValueError("Invalid raster encoding")
        raster = base64.b64decode(encoded, validate=True)
        if len(raster) != width_bytes * height:
            raise ValueError("Invalid raster length")
    except (KeyError, TypeError, ValueError, binascii.Error) as exc:
        raise PrintFailure("Logo do documento inválida.") from exc
    return (b"\x1ba\x01\x1dv0\x00" + width_bytes.to_bytes(2, "little")
            + height.to_bytes(2, "little") + raster + b"\x1ba\x00")


def encode_document(text, *, header_lines=0, header_scale=1, bold_lines=(), logo=None):
    """Encode the shared text strictly, rejecting unsupported text before I/O."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines(keepends=True)
    if (type(header_lines) is not int or not 0 <= header_lines <= len(lines)
            or header_scale not in (1, 2)):
        raise PrintFailure("Formatação do cabeçalho inválida.")
    if any(type(index) is not int or not 0 <= index < len(lines) for index in bold_lines):
        raise PrintFailure("Formatação de negrito inválida.")
    if any(ord(char) < 32 and char != "\n" for char in text):
        raise PrintFailure("Documento contém caracteres de controle não permitidos.")
    try:
        encoded = text.encode("cp860", errors="strict")
    except UnicodeEncodeError as exc:
        raise PrintFailure("Documento contém caractere não suportado pelo perfil cp860. Revise o texto.") from exc
    # ESC @ initialize, ESC t 3 selects cp860 on this provisional POS-80 profile.
    # Three feed lines and full cut; paper height is never capped at 210 mm.
    if bold_lines or (header_lines and header_scale == 2):
        chunks = []
        for index, line in enumerate(lines):
            if header_lines and header_scale == 2:
                if index == 0:
                    chunks.append(b"\x1d!\x11")
                if index == header_lines:
                    chunks.append(b"\x1d!\x00")
            if index in bold_lines:
                chunks.append(b"\x1bE\x01")
            chunks.append(line.encode("cp860"))
            if index in bold_lines:
                chunks.append(b"\x1bE\x00")
        if header_lines == len(lines) and header_scale == 2:
            chunks.append(b"\x1d!\x00")
        encoded = b"".join(chunks)
    return b"\x1b@\x1bt\x03" + encode_logo(logo) + encoded + b"\n\n\n\x1dV\x00"
