"""Own a dedicated Windows browser without touching personal browser sessions."""

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from threading import Lock
from urllib.parse import urlsplit
import webbrowser

logger = logging.getLogger(__name__)


def find_browser():
    """Locate Edge or Chrome in their standard Windows installation folders."""
    for name, relative in (
        ("edge", "Microsoft/Edge/Application/msedge.exe"),
        ("chrome", "Google/Chrome/Application/chrome.exe"),
    ):
        for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            root = os.environ.get(variable)
            if root:
                executable = Path(root) / relative
                if executable.is_file():
                    return name, executable
    raise RuntimeError("Instale Microsoft Edge ou Google Chrome para abrir a janela do Restaurante Local.")


def close_windows(pid):
    """Request normal closure of top-level windows owned by one launched process."""
    api = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    api.EnumWindows.restype = wintypes.BOOL
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.GetWindowThreadProcessId.restype = wintypes.DWORD
    api.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    api.PostMessageW.restype = wintypes.BOOL

    @callback_type
    def visit(window, parameter):
        owner = wintypes.DWORD()
        api.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == pid:
            api.PostMessageW(window, 0x0010, 0, 0)  # WM_CLOSE, asynchronous.
        return True

    if not api.EnumWindows(visit, 0):
        raise ctypes.WinError(ctypes.get_last_error())


class ApplicationBrowser:
    """Launch and close only browsers using this runtime's isolated profile."""

    def __init__(self, data_dir, instance_id, mode="fullscreen"):
        if mode not in ("fullscreen", "maximized"):
            raise ValueError("Modo do navegador deve ser fullscreen ou maximized.")
        self.data_dir = Path(data_dir)
        self.instance_id = instance_id
        self.mode = mode
        self.processes = []
        self.lock = Lock()
        self.closed = False
        self.profile = None

    def _launch(self, url, instance_id):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
            raise ValueError("A janela dedicada aceita somente o servidor HTTP local.")
        if not re.fullmatch(r"[a-f0-9]{32}", instance_id):
            raise ValueError("Identidade de janela inválida.")
        if os.name != "nt":
            return webbrowser.open(url)
        name, executable = find_browser()
        profile = self.data_dir / "browser" / instance_id
        profile.mkdir(parents=True, exist_ok=True)
        self.profile = profile
        arguments = [str(executable), f"--user-data-dir={profile}", "--no-first-run",
                     "--no-default-browser-check", "--disable-background-mode"]
        if self.mode == "maximized":
            arguments.extend(["--start-maximized", f"--app={url}"])
        else:
            arguments.extend(["--kiosk", url])
            if name == "edge":
                arguments.append("--edge-kiosk-type=fullscreen")
        return subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

    def open(self, url):
        """Open the application, tracking handles rather than browser process names."""
        with self.lock:
            if self.closed:
                return
            self.processes = [process for process in self.processes if process.poll() is None]
            process = self._launch(url, self.instance_id)
            if os.name == "nt":
                self.processes.append(process)
                logger.info("Janela dedicada iniciada: pid=%s mode=%s", process.pid, self.mode)

    def close(self):
        """Close owned windows normally, with a bounded process-handle fallback."""
        with self.lock:
            self.closed = True
            active = [process for process in self.processes if process.poll() is None]
            for process in active:
                try:
                    close_windows(process.pid)
                except OSError:
                    logger.exception("Não foi possível solicitar fechamento da janela dedicada.")
            deadline = time.monotonic() + 3
            for process in active:
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    # The handle belongs to a process created with our unique profile.
                    # Never use taskkill, browser names or a personal browser profile.
                    logger.warning("Janela dedicada não respondeu; encerrando seu processo.")
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        logger.exception("Falha ao encerrar processo da janela dedicada.")
            if all(process.poll() is not None for process in active):
                self._remove_profile()
            self.processes.clear()

    def _remove_profile(self):
        """Remove only this session's profile after its processes have exited."""
        if self.profile is None:
            return
        root = (self.data_dir / "browser").resolve()
        profile = self.profile.resolve()
        if profile.parent != root or profile.name != self.instance_id:
            logger.error("Perfil fora da pasta da sessão; limpeza recusada.")
            return
        for attempt in range(3):
            try:
                shutil.rmtree(profile)
                self.profile = None
                return
            except FileNotFoundError:
                self.profile = None
                return
            except OSError:
                if attempt == 2:
                    logger.warning("Perfil da sessão conservado para limpeza posterior: %s", profile)
                else:
                    time.sleep(0.1)
