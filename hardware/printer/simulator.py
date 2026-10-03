"""In-memory transport: never opens a printer, spooler or network endpoint."""


from hardware.printer.results import PrintFailure


class SimulatedPrintFailure(PrintFailure):
    """Known failure before the simulator accepted any content."""


class SimulatedPrinter:
    """Accept complete document text without producing paper."""

    def __init__(self):
        self.closed = False

    def send(self, text):
        """Validate text and return an explicitly simulated acceptance."""
        if self.closed:
            raise SimulatedPrintFailure("Simulador encerrado antes do envio.")
        if not text.strip():
            raise SimulatedPrintFailure("Documento vazio.")
        return "Documento completo validado pelo simulador. Nenhuma impressão física realizada."

    def close(self):
        """Release the simulated transport."""
        self.closed = True
