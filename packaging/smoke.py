"""Verify real Windows bundles and updater with isolated data and simulators."""

import functools
import ctypes
from contextlib import closing
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import struct
import tempfile
import threading
import time
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import build_opener, ProxyHandler
from urllib.request import HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar

ROOT = Path(__file__).resolve().parent.parent


def stop_process(pid):
    """Terminate and wait for a simulator process created by the smoke test."""
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    api.OpenProcess.restype = ctypes.c_void_p
    api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = api.OpenProcess(0x100001, False, pid)
    if handle:
        try:
            api.TerminateProcess(handle, 0)
            api.WaitForSingleObject(handle, 10000)
        finally:
            api.CloseHandle(handle)


def main():
    """Exercise installation, web update, integrity and active-runtime exclusion."""
    architecture = "x64" if struct.calcsize("P") == 8 else "x86"
    archive = ROOT / "dist" / f"RestauranteLocal-windows-{architecture}.zip"
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    script = ROOT / "packaging" / "windows" / "Update.ps1"
    opener = build_opener(ProxyHandler({}))
    with tempfile.TemporaryDirectory(prefix="restaurante-package-") as temporary:
        base = Path(temporary)
        install = base / "program with spaces"
        data = base / "data"
        environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=str(data))
        # Source .env and developer tools must not be needed by the executable.
        environment.pop("SECRET_KEY", None)

        def update(*arguments, success=True):
            result = subprocess.run([
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                "-InstallRoot", str(install), "-NoShortcut", *map(str, arguments),
            ], env=environment, capture_output=True, timeout=180)
            if (result.returncode == 0) != success:
                raise AssertionError(result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))
            return result

        def launch():
            result = subprocess.run([
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(install / "Launch.ps1"),
                "-InstallRoot", str(install), "-RuntimeArguments", "--simulate --preview-print --no-browser --no-tray",
            ], env=environment, capture_output=True, timeout=180)
            assert result.returncode == 0, result.stderr.decode(errors="replace")
            pid = int(result.stdout.strip())
            try:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        with opener.open(f"http://127.0.0.1:{port}/health/", timeout=1) as response:
                            assert json.load(response)["ready"]
                        return pid
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise AssertionError("Inicializador distribuído não confirmou prontidão.")
                        time.sleep(0.2)
            except BaseException:
                stop_process(pid)
                raise

        update("-PackagePath", archive, "-ExpectedHash", "0" * 64, success=False)
        assert not (install / "current.json").exists()
        malicious = base / "traversal.zip"
        with zipfile.ZipFile(malicious, "w") as output:
            output.writestr("../escaped.txt", "invalid")
        update("-PackagePath", malicious, "-ExpectedHash", hashlib.sha256(malicious.read_bytes()).hexdigest(), success=False)
        assert not (install / "escaped.txt").exists()
        update("-PackagePath", archive, "-ExpectedHash", digest)
        wrong_architecture = base / "wrong-architecture.zip"
        with zipfile.ZipFile(archive) as original, zipfile.ZipFile(wrong_architecture, "w", zipfile.ZIP_DEFLATED) as output:
            for entry in original.infolist():
                content = original.read(entry)
                if entry.filename == "app/version.json":
                    info = json.loads(content)
                    info["architecture"] = "x86" if architecture == "x64" else "x64"
                    content = json.dumps(info).encode()
                output.writestr(entry, content)
        update("-PackagePath", wrong_architecture,
               "-ExpectedHash", hashlib.sha256(wrong_architecture.read_bytes()).hexdigest(), success=False)
        assert not (install / "update-failed.txt").exists()
        current = json.loads((install / "current.json").read_text(encoding="utf-8-sig"))
        assert current["architecture"] == architecture
        bundle = install / current["directory"]
        assert (data / "db.sqlite3").is_file()
        with closing(sqlite3.connect(data / "db.sqlite3")) as connection:
            assert connection.execute("SELECT COUNT(*) FROM django_migrations").fetchone()[0] >= 10
        update("-PackagePath", archive, "-ExpectedHash", digest)
        # Create a representative preserved business record using bundled Django only.
        fixture = base / "fixture.json"
        fixture.write_text(json.dumps([{"model": "configuration.applicationconfiguration", "pk": 1,
                                        "fields": {"display_name": "Teste preservado", "revision": 1}}]), encoding="utf-8")
        maintenance = bundle / "Manutencao.exe"
        loaded = subprocess.run([str(maintenance), "loaddata", str(fixture)], env=environment, capture_output=True)
        assert loaded.returncode == 0, loaded.stderr.decode(errors="replace")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        prepared = subprocess.run([str(maintenance), "initialize_local", "--port", str(port)], env=environment, capture_output=True)
        assert prepared.returncode == 0, prepared.stderr.decode(errors="replace")
        runtime = subprocess.Popen([str(bundle / "RestauranteLocal.exe"), "--simulate", "--preview-print", "--no-browser", "--no-tray"], env=environment)
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with opener.open(f"http://127.0.0.1:{port}/health/", timeout=1) as response:
                        assert json.load(response)["ready"]
                    break
                except OSError:
                    if time.monotonic() >= deadline or runtime.poll() is not None:
                        raise AssertionError("Executável não confirmou prontidão; confira logs temporários.")
                    time.sleep(0.2)
            for path in ("/", "/products/", "/configuration/", "/status/"):
                with opener.open(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
                    assert response.status == 200
            before = (install / "current.json").read_bytes()
            update("-PackagePath", archive, "-ExpectedHash", digest, success=False)
            assert (install / "current.json").read_bytes() == before
            assert not (install / "update-failed.txt").exists()
            cookies = CookieJar()
            touch = build_opener(ProxyHandler({}), HTTPCookieProcessor(cookies))
            with touch.open(f"http://127.0.0.1:{port}/runtime/shutdown/confirm/") as response:
                assert "Continuar usando" in response.read().decode()
            token = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
            request = Request(f"http://127.0.0.1:{port}/runtime/shutdown/",
                              data=urlencode({"confirmed": "yes", "csrfmiddlewaretoken": token}).encode())
            with touch.open(request) as response:
                assert "Encerramento solicitado" in response.read().decode()
            assert runtime.wait(timeout=10) == 0
            assert not (data / "instance.json").exists()
        finally:
            if runtime.poll() is None:
                runtime.terminate()
            runtime.wait(timeout=10)
        web = base / "web"
        web.mkdir()
        # A distinct main commit, keeping the same semantic version, must update.
        next_archive = web / "next.zip"
        revision = "f" * 40
        with zipfile.ZipFile(archive) as original, zipfile.ZipFile(next_archive, "w", zipfile.ZIP_DEFLATED) as output:
            for entry in original.infolist():
                content = original.read(entry)
                if entry.filename == "app/version.json":
                    info = json.loads(content)
                    info["revision"] = revision
                    content = json.dumps(info).encode()
                output.writestr(entry, content)
        next_digest = hashlib.sha256(next_archive.read_bytes()).hexdigest()
        filename = f"RestauranteLocal-{next_digest}.zip"
        next_archive.rename(web / filename)
        (web / "latest.json").write_text(json.dumps({"version": current["version"], "revision": revision,
                                                      "sha256": next_digest, "package": filename,
                                                      "architecture": architecture}), encoding="utf-8")
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(web))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/latest.json"
            (install / "update-url.txt").write_text(url, encoding="utf-8")
            launched = launch()
            stop_process(launched)
            updated = json.loads((install / "current.json").read_text(encoding="utf-8-sig"))
            assert updated["revision"] == revision
            assert updated["architecture"] == architecture
            assert updated["directory"] != current["directory"]
            with closing(sqlite3.connect(data / "db.sqlite3")) as connection:
                assert connection.execute("SELECT display_name FROM configuration_applicationconfiguration WHERE id=1").fetchone()[0] == "Teste preservado"
            assert list((data / "backups").glob("*/db.sqlite3"))
            pointer = (install / "current.json").read_bytes()
            manifest_path = web / "latest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            wrong_manifest = dict(manifest, architecture="x86" if architecture == "x64" else "x64")
            manifest_path.write_text(json.dumps(wrong_manifest), encoding="utf-8")
            update("-ManifestUrl", url, success=False)
            assert (install / "current.json").read_bytes() == pointer
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            update("-ManifestUrl", url)
            assert (install / "current.json").read_bytes() == pointer
            (install / "update-failed.txt").write_text("Ensaio de recuperação", encoding="utf-8")
            update("-ManifestUrl", url)
            assert not (install / "update-failed.txt").exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        # Server is now offline: automatic check must still open the installed build.
        launched = launch()
        stop_process(launched)
    print("Pacote Windows validado: instalação, executável offline, HTTP, integridade, exclusão e atualização web com dados preservados.")


if __name__ == "__main__":
    main()
