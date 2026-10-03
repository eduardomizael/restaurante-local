"""Explicit, lazy serial ownership with bounded reads and reconnect."""

import logging
import re
from dataclasses import replace
from time import monotonic

from hardware.scale.protocol import FRAME_SIZE, ScaleProtocolError, parse_frame

logger = logging.getLogger(__name__)


class SerialScale:
    """Query one USB serial port; no I/O occurs during construction/import."""

    def __init__(self, port="COM3", *, timeout=1, serial_factory=None, clock=monotonic):
        if not re.fullmatch(r"COM[1-9][0-9]{0,3}", port.upper()):
            raise ValueError("Porta deve usar um nome COM válido.")
        self.port = port.upper()
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
                while len(frame) < FRAME_SIZE:
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        break
                    connection.timeout = remaining
                    block = connection.read(FRAME_SIZE - len(frame))
                    if not block:
                        break
                    frame.extend(block)
                # Only absence of any bytes permits one bounded retry. Partial,
                # corrupt and oversized replies still invalidate the cycle.
                if frame or connection.in_waiting:
                    break
            self.last_frame = bytes(frame)
            if connection.in_waiting:
                raise ScaleProtocolError("Resposta excede o tamanho do perfil homologável.")
            return replace(parse_frame(self.last_frame, started), device=f"SERIAL:{self.port}")
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
