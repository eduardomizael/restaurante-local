"""Strict parser for the 150-byte US 31/2 POP-S profile observed on COM3."""

from decimal import Decimal
import re

from hardware.scale.sample import ScaleSample

FRAME_SIZE = 150
FRAME_PREFIX = bytes.fromhex("08020303020301020014")
FRAME_SUFFIX = bytes.fromhex("0309020103")


class ScaleProtocolError(ValueError):
    """Response cannot safely be used as a commercial measurement."""


class ScaleNoResponseError(ScaleProtocolError):
    """Both bounded queries received no bytes on an otherwise open port."""


def parse_frame(frame, sampled_at):
    """Validate complete framing and parse net/tare without price authority.

    Args:
        frame: One complete response received after the current query.
        sampled_at: Monotonic timestamp of query start, bounding sample age.

    Returns:
        ScaleSample: Integer grams; tare is informational, never subtracted.

    Raises:
        ScaleProtocolError: Incomplete, ambiguous or invalid response.
    """
    if len(frame) != FRAME_SIZE or not frame.startswith(FRAME_PREFIX) or not frame.endswith(FRAME_SUFFIX):
        raise ScaleProtocolError("Quadro incompleto ou perfil da balança não reconhecido.")
    try:
        text = frame[len(FRAME_PREFIX):-len(FRAME_SUFFIX)].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ScaleProtocolError("Quadro contém bytes de texto inválidos.") from exc
    if any(ord(char) < 32 or ord(char) > 126 for char in text):
        raise ScaleProtocolError("Quadro contém caracteres de controle inesperados.")
    if any(word in text.upper() for word in ("OVERLOAD", "SOBRECARGA", "ERROR", "ERRO")):
        raise ScaleProtocolError("Balança informou falha ou sobrecarga.")
    for marker in ("DATA:", "VALID.:", "TARA:", "PESO L:", "R$/kg:", "TOTAL R$:"):
        if text.count(marker) != 1:
            raise ScaleProtocolError("Campos ausentes ou duplicados na resposta da balança.")

    def grams(marker, *, minimum=0):
        matches = re.findall(re.escape(marker) + r"\s*([+-]?[0-9]{1,4}[.,][0-9]{3})kg(?=\s)", text)
        if len(matches) != 1:
            raise ScaleProtocolError("Peso/tara inválido ou com precisão inesperada.")
        value = int(Decimal(matches[0].replace(",", ".")) * 1000)
        if not minimum <= value <= 1_000_000:
            raise ScaleProtocolError("Peso/tara fora do limite técnico.")
        return value

    moving = any(word in text.upper() for word in ("INSTAVEL", "UNSTABLE", "MOTION", "MOVIMENTO"))
    return ScaleSample(grams("PESO L:", minimum=-1_000_000), grams("TARA:"), sampled_at, moving, protocol="USECB2")


def parse_prot_f_frame(frame, sampled_at):
    """Parse observed PROT F weight and instability, rejecting unknown states.

    Args:
        frame: Complete STX/ETX response, with sign and decimal point.
        sampled_at: Monotonic start of the current query.

    Returns:
        ScaleSample: Net grams or a noncommercial moving sample; tare unavailable.

    Raises:
        ScaleProtocolError: Malformed response or unrecognized fault/overload.
    """
    if frame == b"\x02IIIIII\x03":
        return ScaleSample(0, None, sampled_at, moving=True, protocol="PROT_F")
    match = re.fullmatch(rb"\x02([ +\-])([0-9]{2}\.[0-9]{3})\x03", frame)
    if match is None:
        raise ScaleProtocolError("Resposta PROT F inválida, sobrecarga ou estado não reconhecido.")
    grams = int(Decimal(match[2].decode("ascii")) * 1000)
    if match[1] == b"-":
        grams = -grams
    return ScaleSample(grams, None, sampled_at, protocol="PROT_F")
