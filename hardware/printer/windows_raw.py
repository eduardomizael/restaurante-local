"""Windows spooler RAW transport, loaded only at explicit send time."""

import ctypes
from ctypes import wintypes
import os

from hardware.printer.escpos import encode_document
from hardware.printer.results import PrintFailure, PrintResult


class DOC_INFO_1W(ctypes.Structure):
    _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR),
                ("pDatatype", wintypes.LPWSTR)]


class WindowsSpooler:
    """Typed Win32 API wrapper; construction alone never opens a queue."""

    def __init__(self):
        if os.name != "nt":
            raise OSError("Impressão RAW disponível somente no Windows.")
        api = ctypes.WinDLL("winspool.drv", use_last_error=True)
        signatures = {
            "OpenPrinterW": ([wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p], wintypes.BOOL),
            "StartDocPrinterW": ([wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DOC_INFO_1W)], wintypes.DWORD),
            "StartPagePrinter": ([wintypes.HANDLE], wintypes.BOOL),
            "WritePrinter": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            "EndPagePrinter": ([wintypes.HANDLE], wintypes.BOOL),
            "EndDocPrinter": ([wintypes.HANDLE], wintypes.BOOL),
            "AbortPrinter": ([wintypes.HANDLE], wintypes.BOOL),
            "ClosePrinter": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(api, name)
            function.argtypes, function.restype = arguments, result
        self.api = api

    def _check(self, result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def open(self, name):
        handle = wintypes.HANDLE()
        self._check(self.api.OpenPrinterW(name, ctypes.byref(handle), None))
        return handle

    def start(self, handle):
        info = DOC_INFO_1W("Restaurante Local — comanda", None, "RAW")
        return self._check(self.api.StartDocPrinterW(handle, 1, ctypes.byref(info)))

    def page(self, handle):
        self._check(self.api.StartPagePrinter(handle))

    def write(self, handle, data):
        written = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(data)
        self._check(self.api.WritePrinter(handle, buffer, len(data), ctypes.byref(written)))
        return written.value

    def finish(self, handle):
        self._check(self.api.EndPagePrinter(handle))
        self._check(self.api.EndDocPrinter(handle))

    def abort(self, handle):
        self._check(self.api.AbortPrinter(handle))

    def close(self, handle):
        self._check(self.api.ClosePrinter(handle))


class WindowsRawPrinter:
    """Deliver frozen text, recording uncertainty after StartDocPrinter."""

    def __init__(self, printer_name="balanca", *, spooler_factory=WindowsSpooler):
        self.printer_name = printer_name
        self.spooler_factory = spooler_factory
        self.closed = False

    def send(self, text):
        """Return spooler acceptance, keeping all post-start failures uncertain."""
        if self.closed:
            raise PrintFailure("Adaptador de impressão encerrado antes do envio.")
        data = encode_document(text)
        handle, job_id, spooler = None, None, None
        try:
            spooler = self.spooler_factory()
            handle = spooler.open(self.printer_name)
            job_id = spooler.start(handle)
            spooler.page(handle)
            written = 0
            while written < len(data):
                count = spooler.write(handle, data[written:])
                if not 0 < count <= len(data) - written:
                    raise OSError("Spooler não confirmou todos os bytes do documento.")
                written += count
            spooler.finish(handle)
        except Exception as exc:
            if job_id is not None:
                try:
                    spooler.abort(handle)
                except Exception:
                    pass
                raise OSError(f"Resultado incerto do trabalho RAW #{job_id}: {exc}") from exc
            raise PrintFailure(f"Impressão não iniciada: {exc}") from exc
        finally:
            if handle is not None:
                spooler.close(handle)
        return PrintResult("SPOOL_ACCEPTED", f"Spooler aceitou trabalho RAW #{job_id}. Confira a saída física do papel.", job_id)

    def close(self):
        """Stop accepting sends; each send owns and closes its printer handle."""
        self.closed = True
