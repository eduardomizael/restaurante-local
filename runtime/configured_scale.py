"""Observe DB configuration between serial queries, never during a frame."""

from apps.configuration.selectors import hardware_configuration
from hardware.scale.serial_adapter import create_scale_adapter


class ConfiguredSerialScale:
    """Own a replaceable serial adapter on the scale worker's thread."""

    def __init__(self, adapter_factory=create_scale_adapter):
        self.adapter_factory = adapter_factory
        self.adapter = None
        self.revision = None
        self.closed = False

    def read(self):
        """Apply revisions between queries; cycle is rearmed by ScaleWorker."""
        if self.closed:
            raise RuntimeError("Leitor serial encerrado.")
        configuration = hardware_configuration()
        if self.revision != configuration.revision:
            if self.adapter:
                self.adapter.close()
            self.adapter = self.adapter_factory(configuration.scale_port, protocol=configuration.scale_protocol)
            self.revision = configuration.revision
        return self.adapter.read()

    def close(self):
        """Close only the currently owned adapter."""
        self.closed = True
        if self.adapter:
            self.adapter.close()
