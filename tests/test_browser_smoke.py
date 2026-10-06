"""Opt-in native browser validation with isolated data and simulated hardware."""

import ctypes
from ctypes import wintypes
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from unittest import skipUnless
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from django.conf import settings
from django.test import SimpleTestCase

from runtime.browser import ApplicationBrowser, close_windows


def windows_for(pid):
    """Find visible top-level windows belonging to an explicitly launched process."""
    api = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.IsWindowVisible.argtypes = [wintypes.HWND]
    api.IsWindowVisible.restype = wintypes.BOOL
    found = []

    @callback_type
    def visit(window, parameter):
        owner = wintypes.DWORD()
        api.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == pid and api.IsWindowVisible(window):
            found.append(window)
        return True

    api.EnumWindows(visit, 0)
    return found


def wait_for(condition, timeout=20):
    """Wait for a native process/window transition with a fixed deadline."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("Transição da janela não ocorreu no prazo.")


@skipUnless(os.name == "nt" and os.environ.get("LOCAL_WEIGHING_BROWSER_SMOKE") == "1",
            "Native browser smoke requires explicit opt-in")
class NativeBrowserSmokeTests(SimpleTestCase):
    def test_fullscreen_http_exit_preserves_unrelated_window(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as socket_probe:
            socket_probe.bind(("127.0.0.1", 0))
            port = socket_probe.getsockname()[1]
            socket_probe.close()
            data = Path(directory) / "data"
            environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=str(data), DJANGO_SETTINGS_MODULE="config.settings")
            initialized = subprocess.run([sys.executable, "manage.py", "initialize_local", "--port", str(port)],
                                         cwd=settings.BASE_DIR, env=environment, capture_output=True, timeout=30)
            self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
            # This is another isolated test browser, never the user's personal profile.
            unrelated = ApplicationBrowser(Path(directory) / "unrelated", "b" * 32, "maximized")
            runtime = None
            try:
                unrelated.open(f"http://127.0.0.1:{port}/health/")
                unrelated_pid = unrelated.processes[0].pid
                wait_for(lambda: windows_for(unrelated_pid))
                runtime = subprocess.Popen([sys.executable, "manage.py", "run_local", "--simulate",
                                            "--preview-print", "--no-tray"], cwd=settings.BASE_DIR,
                                           env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log = data / "logs/runtime.log"

                def browser_pid():
                    text = log.read_text(encoding="utf-8") if log.exists() else ""
                    matches = re.findall(r"Janela dedicada iniciada: pid=(\d+) mode=fullscreen", text)
                    return int(matches[-1]) if matches else None

                pid = wait_for(browser_pid)
                window = wait_for(lambda: windows_for(pid))[0]
                api = ctypes.WinDLL("user32", use_last_error=True)
                api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                api.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
                api.MonitorFromWindow.restype = wintypes.HANDLE

                class MonitorInfo(ctypes.Structure):
                    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                                ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

                api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]

                def covers_monitor():
                    rectangle = wintypes.RECT()
                    self.assertTrue(api.GetWindowRect(window, ctypes.byref(rectangle)))
                    info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
                    self.assertTrue(api.GetMonitorInfoW(api.MonitorFromWindow(window, 2), ctypes.byref(info)))
                    return (rectangle.left <= info.monitor.left and rectangle.top <= info.monitor.top
                            and rectangle.right >= info.monitor.right and rectangle.bottom >= info.monitor.bottom)

                wait_for(covers_monitor)
                # Closing only the window must leave the runtime and data alive.
                close_windows(pid)
                wait_for(lambda: not windows_for(pid))
                self.assertIsNone(runtime.poll())
                duplicated = subprocess.run([sys.executable, "manage.py", "run_local", "--simulate",
                                             "--preview-print", "--no-tray"], cwd=settings.BASE_DIR,
                                            env=environment, capture_output=True, timeout=15)
                self.assertEqual(duplicated.returncode, 0, duplicated.stdout + duplicated.stderr)
                pid = wait_for(lambda: browser_pid() if browser_pid() != pid else None)
                window = wait_for(lambda: windows_for(pid))[0]
                wait_for(covers_monitor)
                cookies = CookieJar()
                opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(cookies))
                url = f"http://127.0.0.1:{port}/"
                with opener.open(url + "runtime/shutdown/confirm/", timeout=3) as response:
                    self.assertIn("Continuar usando", response.read().decode())
                csrf = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
                request = Request(url + "runtime/shutdown/", data=urlencode({
                    "confirmed": "yes", "csrfmiddlewaretoken": csrf,
                }).encode())
                with opener.open(request, timeout=3) as response:
                    self.assertIn("Encerramento solicitado", response.read().decode())
                self.assertEqual(runtime.wait(timeout=15), 0)
                wait_for(lambda: not windows_for(pid))
                self.assertTrue(windows_for(unrelated_pid))
                self.assertIsNone(unrelated.processes[0].poll())
                self.assertFalse((data / "instance.json").exists())
            finally:
                if runtime is not None and runtime.poll() is None:
                    # Ask for normal shutdown first; forced cleanup is limited to this test process.
                    runtime.terminate()
                    runtime.wait(timeout=5)
                unrelated.close()
