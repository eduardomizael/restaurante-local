"""Explicit, lazy serial ownership with bounded reads and reconnect."""

import logging
import re
from dataclasses import replace
from time import monotonic

from hardware.scale.protocol import FRAME_SIZE, ScaleNoResponseError, ScaleProtocolError, parse_frame, parse_prot_f_frame

logger = logging.getLogger(__name__)


class SerialScale:
    """Query USECB2 or PROT F; no I/O occurs during construction/import."""

    def __init__(self, port="COM3", *, timeout=1, serial_factory=None, clock=monotonic, protocol="USECB2"):
        if not re.fullmatch(r"COM[1-9][0-9]{0,3}", port.upper()):
            raise ValueError("Porta deve usar um nome COM válido.")
        self.port = port.upper()
        if protocol not in ("USECB2", "PROT_F"):
            raise ValueError("Protocolo serial não suportado.")
        self.protocol = protocol
        self.timeout = timeout
        self.serial_factory = serial_factory
        self.clock = clock
        self.connection = None
        self.closed = False
        self.last_frame = None

    def _open(self):
        if self.connection is not None:
            return
        import serial

        factory = self.serial_factory or serial.Serial
        connection = factory(port=None, baudrate=9600, bytesize=8, parity="N", stopbits=2,
                             timeout=self.timeout, write_timeout=self.timeout,
                             xonxoff=False, rtscts=False, dsrdtr=False)
        try:
            connection.dtr = False
            connection.rts = False
            connection.port = self.port
            connection.open()
        except BaseException:
            connection.close()
            raise
        self.connection = connection

    def _disconnect(self):
        connection, self.connection = self.connection, None
        if connection is not None:
            connection.close()

    def read(self):
        """Read one fresh complete frame, discarding stale bytes before query."""
        if self.closed:
            raise RuntimeError("Adaptador serial encerrado.")
        self.last_frame = None
        try:
            self._open()
            connection = self.connection
            started = self.clock()
            for attempt in range(2):
                connection.reset_input_buffer()
                if connection.write(b"\x04") != 1:
                    raise OSError("Consulta serial não enviada por completo.")
                frame = bytearray()
                deadline = started + self.timeout * (attempt + 1)
                frame_limit = FRAME_SIZE if self.protocol == "USECB2" else 9
                while len(frame) < frame_limit:
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        break
                    connection.timeout = remaining
                    block = connection.read(FRAME_SIZE - len(frame) if self.protocol == "USECB2" else 1)
                    if not block:
                        break
                    frame.extend(block)
                    if self.protocol == "PROT_F" and frame.endswith(b"\x03"):
                        break
                # Only absence of any bytes permits one bounded retry. Partial,
                # corrupt and oversized replies still invalidate the cycle.
                if frame or connection.in_waiting:
                    break
            self.last_frame = bytes(frame)
            if connection.in_waiting:
                raise ScaleProtocolError("Resposta excede o tamanho do perfil homologável.")
            if not self.last_frame:
                raise ScaleNoResponseError("Balança não respondeu após duas consultas.")
            parser = parse_frame if self.protocol == "USECB2" else parse_prot_f_frame
            identity = f"SERIAL:{self.port}" + (":PROT_F" if self.protocol == "PROT_F" else "")
            return replace(parser(self.last_frame, started), device=identity)
        except ScaleNoResponseError:
            # Silence alone does not imply a broken port. The cycle bounds
            # recovery; subsequent queries still discard all pending bytes.
            raise
        except Exception:
            if self.last_frame is not None:
                logger.debug("Rejected serial frame on %s: size=%d hex=%s", self.port,
                             len(self.last_frame), self.last_frame.hex())
            self._disconnect()
            raise

    def close(self):
        """Close the owned port; retries after shutdown are not permitted."""
        self.closed = True
        self._disconnect()

    def probe(self, *, duration, query, emit):
        """Observe raw diagnostic chunks without assuming a frame format.

        Args:
            duration: Maximum observation duration in seconds, from 1 to 60.
            query: Whether to send the known read-only 0x04 query once per second.
            emit: Callback receiving elapsed seconds and each received byte chunk.

        Returns:
            int: Total bytes received, capped at 65536.
        """
        if self.closed or not 1 <= duration <= 60:
            raise ValueError("Sonda encerrada ou duração fora de 1 a 60 segundos.")
        try:
            self._open()
            self.connection.reset_input_buffer()
            started = self.clock()
            next_query = started
            total = 0
            while (now := self.clock()) - started < duration and total < 65536:
                if query and now >= next_query:
                    if self.connection.write(b"\x04") != 1:
                        raise OSError("Consulta serial não enviada por completo.")
                    next_query = now + 1
                self.connection.timeout = min(0.2, duration - (now - started))
                block = self.connection.read(min(max(1, self.connection.in_waiting), 4096, 65536 - total))
                if block:
                    total += len(block)
                    emit(self.clock() - started, block)
            return total
        finally:
            self.close()


class ProtFScale(SerialScale):
    """Reader for signed PROT F weights and explicit instability responses."""

    def __init__(self, port="COM3", **kwargs):
        super().__init__(port, protocol="PROT_F", **kwargs)


def create_scale_adapter(port, *, protocol="USECB2"):
    """Create the selected reader without opening hardware."""
    readers = {"USECB2": SerialScale, "PROT_F": ProtFScale}
    if protocol not in readers:
        raise ValueError("Protocolo serial não suportado.")
    return readers[protocol](port)
