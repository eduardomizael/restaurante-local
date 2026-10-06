"""Verify source activation, offline preservation and data failure recovery."""

import hashlib
import http.cookiejar
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import subprocess
import socket
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from runtime import source_update
from runtime.instance_lock import InstanceLock


class SourceUpdateTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "program"
        self.root.mkdir()
        self.revision = "a" * 40
        self.record = {"mode": "source", "architecture": "x64", "revision": self.revision,
                       "directory": "versions/" + hashlib.sha256(self.revision.encode()).hexdigest()}

    def install_pointer(self):
        source_update.write_record(self.root / "current.json", self.record)
        return self.root / self.record["directory"]

    def test_active_instance_does_not_contact_git_or_uv(self):
        self.install_pointer()
        with patch.object(source_update, "maintenance", side_effect=source_update.ToolFailure("python", 2)), patch.object(source_update, "command") as command:
            source_update.update(self.root, check_on_start=True)
            command.assert_not_called()
            with self.assertRaises(source_update.ToolFailure):
                source_update.update(self.root)

    def test_unchanged_revision_does_not_sync_or_migrate(self):
        self.install_pointer()
        with patch.object(source_update, "maintenance") as maintenance, patch.object(source_update, "command", return_value=self.revision + "\trefs/heads/main") as command:
            source_update.update(self.root)
            maintenance.assert_called_once()
            self.assertEqual(command.call_count, 1)

    def test_network_failure_preserves_pointer_and_does_not_block_offline_start(self):
        self.install_pointer()
        original = (self.root / "current.json").read_bytes()
        with patch.object(source_update, "maintenance"), patch.object(source_update, "command", side_effect=subprocess.TimeoutExpired("git", 15)):
            with self.assertRaises(subprocess.TimeoutExpired):
                source_update.update(self.root)
        self.assertEqual((self.root / "current.json").read_bytes(), original)
        self.assertFalse((self.root / "update-failed.txt").exists())

    def test_unsafe_pointer_never_executes_maintenance(self):
        self.record["directory"] = "../outside"
        self.install_pointer()
        with patch.object(source_update, "maintenance") as maintenance:
            with self.assertRaises(ValueError):
                source_update.update(self.root)
            maintenance.assert_not_called()

    def prepare_candidate(self):
        directory = self.install_pointer()
        tools = directory / "packaging/windows"
        tools.mkdir(parents=True)
        for name in source_update.TOOLS:
            (tools / name).write_text("# test tool", encoding="utf-8")
        source_update.write_record(directory / "packaging/toolchain.json", {"python": "3.13.14"})
        (self.root / "update-failed.txt").write_text("interrupted")
        return directory

    def tool_result(self, arguments, **kwargs):
        if "ls-remote" in arguments:
            return self.revision + "\trefs/heads/main"
        if "rev-parse" in arguments:
            return self.revision
        return ""

    def test_migration_failure_keeps_pointer_and_failure_marker(self):
        self.prepare_candidate()
        original = (self.root / "current.json").read_bytes()

        def maintenance(directory, record, action, **kwargs):
            if action == "describe_installation":
                return json.dumps({"data_root": str(self.root.parent / "data"), "mutex_name": "test"})
            if action == "initialize_local":
                raise source_update.ToolFailure("python", 1)

        with patch.object(source_update, "maintenance", side_effect=maintenance), patch.object(source_update, "command", side_effect=self.tool_result):
            with self.assertRaises(source_update.ToolFailure):
                source_update.update(self.root)
        self.assertEqual((self.root / "current.json").read_bytes(), original)
        self.assertTrue((self.root / "update-failed.txt").exists())

    def test_retry_prepares_data_before_activation_and_removes_block(self):
        self.prepare_candidate()
        events = []

        def maintenance(directory, record, action, **kwargs):
            events.append(action)
            if action == "describe_installation":
                return json.dumps({"data_root": str(self.root.parent / "data"), "mutex_name": "test"})

        with patch.object(source_update, "maintenance", side_effect=maintenance), patch.object(source_update, "command", side_effect=self.tool_result):
            source_update.update(self.root)
        self.assertIn("initialize_local", events)
        self.assertFalse((self.root / "update-failed.txt").exists())
        self.assertEqual(source_update.read_record(self.root / "current.json"), self.record)
        self.assertTrue((self.root / "Launch.ps1").exists())


@skipUnless(os.name == "nt", "Windows source installation")
class WindowsSourceInstallTests(SimpleTestCase):
    """Use a temporary local Git remote, real uv and isolated SQLite data."""

    def test_install_upgrade_offline_and_running_instance(self):
        with tempfile.TemporaryDirectory(prefix="restaurante-source-test-") as temporary:
            base = Path(temporary).resolve()
            repository = base / "remote"
            repository.mkdir()
            root = base / "program with spaces"
            data = base / "data"
            environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=str(data),
                               UV_CACHE_DIR=str(settings.BASE_DIR / ".uv-cache"),
                               UV_PYTHON_INSTALL_DIR=str(settings.BASE_DIR / ".uv-python"))
            # Only program files are copied; never development databases/settings.
            for name in ("apps", "config", "runtime", "hardware", "templates", "static", "packaging"):
                shutil.copytree(settings.BASE_DIR / name, repository / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for name in ("manage.py", "pyproject.toml", "uv.lock", ".gitignore"):
                shutil.copyfile(settings.BASE_DIR / name, repository / name)

            def run(arguments, cwd=repository, timeout=180):
                result = subprocess.run(arguments, cwd=cwd, env=environment,
                                        capture_output=True, text=True, timeout=timeout)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout.strip()

            run(["git", "init", "--initial-branch=main"])
            run(["git", "add", "."])

            def commit():
                # Commits exist only in this disposable test repository.
                run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "test fixture"])
                return run(["git", "rev-parse", "HEAD"])

            first = commit()
            installer = settings.BASE_DIR / "packaging/windows/Update.ps1"
            run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer),
                 "-Source", "-InstallRoot", str(root), "-Repository", str(repository), "-NoShortcut"], timeout=600)
            self.assertEqual(source_update.read_record(root / "current.json")["revision"], first)
            self.assertTrue((data / "db.sqlite3").exists())
            with closing(sqlite3.connect(data / "db.sqlite3")) as database:
                database.execute("CREATE TABLE source_update_probe (value TEXT NOT NULL)")
                database.execute("INSERT INTO source_update_probe VALUES (?)", ("saved test data",))
                database.commit()
            (repository / "fixture.txt").write_text("second revision")
            run(["git", "add", "fixture.txt"])
            second = commit()
            run(["powershell.exe", "-NoProfile", "-File", str(root / "Update.ps1"),
                 "-InstallRoot", str(root), "-NoShortcut"], timeout=600)
            record = source_update.read_record(root / "current.json")
            self.assertEqual(record["revision"], second)
            self.assertEqual(source_update.read_record(root / "previous.json")["revision"], first)
            backups = list((data / "backups").glob("*/db.sqlite3"))
            self.assertTrue(backups)
            for path in (data / "db.sqlite3", backups[-1]):
                with closing(sqlite3.connect(path)) as database:
                    self.assertEqual(database.execute("SELECT value FROM source_update_probe").fetchone(), ("saved test data",))
            # Active runtime ownership prevents even a fetch.
            lock = InstanceLock(data)
            self.assertTrue(lock.acquire())
            try:
                run(["powershell.exe", "-NoProfile", "-File", str(root / "Update.ps1"),
                     "-InstallRoot", str(root), "-CheckOnStart"])
                blocked = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(root / "Update.ps1"),
                                          "-InstallRoot", str(root), "-NoShortcut"], env=environment,
                                         capture_output=True, timeout=30)
                self.assertNotEqual(blocked.returncode, 0)
            finally:
                lock.release()
            source_update.write_record(root / "source-settings.json", {"repository": str(base / "missing"), "branch": "main"})
            failed = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(root / "Update.ps1"),
                                     "-InstallRoot", str(root), "-NoShortcut"], env=environment,
                                    capture_output=True, timeout=30)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(source_update.read_record(root / "current.json"), record)
            self.assertFalse((root / "update-failed.txt").exists())
            version = root / record["directory"]
            # Verify the installed interpreter works offline without uv.
            run([str(version / ".venv/Scripts/python.exe"), "manage.py", "check"], cwd=version)
            configuration = source_update.read_record(data / "installation.json")
            with socket.socket() as port_probe:
                port_probe.bind(("127.0.0.1", 0))
                port = port_probe.getsockname()[1]
            configuration["port"] = port
            source_update.write_record(data / "installation.json", configuration)
            launched_pid = int(run(["powershell.exe", "-NoProfile", "-File", str(root / "Launch.ps1"),
                 "-InstallRoot", str(root), "-RuntimeArguments",
                 "--simulate --preview-print --no-tray --no-browser"]))
            import ctypes

            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
            api.OpenProcess.restype = ctypes.c_void_p
            api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            api.CloseHandle.argtypes = [ctypes.c_void_p]
            process_handle = api.OpenProcess(0x00100001, False, launched_pid)
            url = f"http://127.0.0.1:{port}"
            cookies = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
            ready = False
            try:
                for _ in range(30):
                    try:
                        with opener.open(url + "/health/", timeout=1) as response:
                            ready = json.load(response)["ready"]
                        break
                    except OSError:
                        time.sleep(0.2)
                diagnostics = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                                        for path in (data / "logs").glob("*.log")) if (data / "logs").exists() else "Sem logs do runtime."
                if (root / "update-error.log").exists():
                    diagnostics += (root / "update-error.log").read_text(encoding="utf-8", errors="replace")
                self.assertTrue(ready, "Atalho pythonw não iniciou o runtime offline.\n" + diagnostics)
                with opener.open(url + "/runtime/shutdown/confirm/", timeout=3) as response:
                    response.read()
                token = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
                request = urllib.request.Request(url + "/runtime/shutdown/",
                    data=urllib.parse.urlencode({"confirmed": "yes"}).encode(),
                    headers={"X-CSRFToken": token})
                with opener.open(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    response.read()
                for _ in range(30):
                    probe = InstanceLock(data)
                    if probe.acquire():
                        probe.release()
                        break
                    time.sleep(0.2)
                else:
                    self.fail("Runtime não liberou os dados após encerramento.")
            finally:
                # Only the captured isolated process can be terminated on test failure.
                if process_handle:
                    if api.WaitForSingleObject(process_handle, 5000) == 258:
                        api.TerminateProcess(process_handle, 1)
                        api.WaitForSingleObject(process_handle, 5000)
                    api.CloseHandle(process_handle)
            run(["powershell.exe", "-NoProfile", "-File", str(root / "Uninstall.ps1"),
                 "-InstallRoot", str(root), "-ShortcutPath", str(base / "none.lnk"), "-Yes"], cwd=base)
            self.assertFalse(root.exists())
            self.assertTrue((data / "db.sqlite3").exists())
