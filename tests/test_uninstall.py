"""Exercise removal using isolated Windows folders, never operational data."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import skipUnless

from django.conf import settings
from django.test import SimpleTestCase

from runtime.instance_lock import InstanceLock, instance_mutex_name


@skipUnless(os.name == "nt", "Windows uninstaller")
class WindowsUninstallTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="restaurante-uninstall-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.install = self.base / "program with spaces"
        self.data = self.base / "data"
        self.origin = self.base / "original download"
        for directory in (self.install, self.data, self.origin):
            directory.mkdir()
        (self.data / "db.sqlite3").write_text("test data")
        (self.data / "backups").mkdir()
        (self.data / "backups" / "backup.db").write_text("test backup")
        (self.install / "versions").mkdir()
        (self.install / "versions" / "old.exe").write_text("test executable")
        (self.install / "uninstall-info.json").write_text(json.dumps({
            "application": "RestauranteLocal", "schema_version": 1,
            "install_root": str(self.install),
            "data_locations": [{"data_root": str(self.data), "mutex_name": instance_mutex_name(self.data)}],
            "origins": [str(self.origin)],
        }), encoding="utf-8")
        for name in ("Desinstalar.bat", "Uninstall.ps1"):
            shutil.copyfile(settings.BASE_DIR / "packaging" / "windows" / name, self.install / name)

    def run_uninstall(self, *arguments, answer=b"", batch=False):
        script = self.install / ("Desinstalar.bat" if batch else "Uninstall.ps1")
        command = (["cmd.exe", "/d", "/c", "call"] if batch else
                   ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)])
        if batch:
            command.append(str(script))
        return subprocess.run(command + ["-InstallRoot", str(self.install), "-ShortcutPath",
                                        str(self.base / "shortcut.lnk"), *arguments],
                              cwd=self.base, input=answer, capture_output=True, timeout=30)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))

    def test_preserves_data_and_reports_original_download(self):
        (self.install / '.env').write_text('TEST_SETTING=example')
        result = self.run_uninstall("-Yes")
        self.assert_success(result)
        self.assertFalse(self.install.exists())
        self.assertTrue((self.data / "db.sqlite3").exists())
        self.assertTrue(self.origin.exists())
        self.assertIn(str(self.origin).encode(), result.stdout)
        self.assertIn(b"DADOS PRESERVADOS", result.stdout)
        self.assertEqual((self.data / 'preserved-installation' / '.env').read_text(), 'TEST_SETTING=example')

    def test_batch_removes_itself_and_all_data(self):
        result = self.run_uninstall("-Yes", "-DeleteData", batch=True, answer=b"\r\n")
        self.assert_success(result)
        self.assertFalse(self.install.exists())
        self.assertFalse(self.data.exists())
        self.assertTrue(self.origin.exists())

    def test_cancel_removes_nothing(self):
        result = self.run_uninstall(answer=b"\r\nN\r\n")
        self.assert_success(result)
        self.assertTrue((self.install / "versions" / "old.exe").exists())
        self.assertTrue((self.data / "db.sqlite3").exists())

    def test_removes_only_shortcut_owned_by_installation(self):
        shortcut = self.base / 'shortcut.lnk'
        arguments = '-File "' + str(self.install / 'Launch.ps1') + '"'
        code = "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('" + str(shortcut) + "'); $s.TargetPath = 'powershell.exe'; $s.Arguments = '" + arguments + "'; $s.Save()"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', code], capture_output=True, timeout=10)
        self.assert_success(result)
        self.assertTrue(shortcut.exists())
        self.assert_success(self.run_uninstall('-Yes'))
        self.assertFalse(shortcut.exists())

    def test_running_application_blocks_removal(self):
        lock = InstanceLock(self.data)
        self.assertTrue(lock.acquire())
        try:
            result = self.run_uninstall("-Yes", "-DeleteData")
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((self.install / "versions" / "old.exe").exists())
            self.assertTrue((self.data / "db.sqlite3").exists())
            self.assertFalse((self.install / "update.lock").exists())
        finally:
            lock.release()

    def test_busy_update_blocks_removal(self):
        with (self.install / "update.lock").open("wb"):
            result = self.run_uninstall("-Yes", "-DeleteData")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.install.exists())
        self.assertTrue(self.data.exists())

    def test_mismatched_data_root_blocks_removal(self):
        result = self.run_uninstall("-Yes", "-DeleteData", "-DataRoot", str(self.origin))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.data / "db.sqlite3").exists())
        self.assertTrue(self.origin.exists())

    def test_protected_directory_is_rejected(self):
        script = settings.BASE_DIR / "packaging" / "windows" / "Uninstall.ps1"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(script),
                                 "-InstallRoot", str(Path(self.base.anchor)), "-Yes", "-DeleteData"],
                                capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.data / "db.sqlite3").exists())

    def test_child_junction_does_not_remove_external_target(self):
        link = self.install / "linked"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                 "New-Item -ItemType Junction -Path '" + str(link) + "' -Target '" + str(self.origin) + "'"],
                                capture_output=True, timeout=10)
        self.assert_success(result)
        sentinel = self.origin / "keep.txt"
        sentinel.write_text("external data")
        self.assert_success(self.run_uninstall("-Yes", "-DeleteData"))
        self.assertFalse(self.install.exists())
        self.assertEqual(sentinel.read_text(), "external data")

    def test_failed_removal_keeps_recovery_metadata_and_lists_residue(self):
        import ctypes
        import re

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                                   ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        api.CreateFileW.restype = ctypes.c_void_p
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        blocked = self.install / "versions" / "old.exe"
        handle = api.CreateFileW(str(blocked), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            result = self.run_uninstall("-Yes", "-DeleteData")
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(blocked.exists())
            self.assertTrue((self.install / "uninstall-info.json").exists())
            self.assertIn(str(blocked).encode(), result.stdout)
            report_name = re.search(rb"RestauranteLocal-desinstalacao-[a-f0-9]{32}\.txt", result.stdout)
            self.assertIsNotNone(report_name)
            report = Path(tempfile.gettempdir()) / report_name.group().decode()
            self.assertTrue(report.exists())
            report.unlink()
        finally:
            api.CloseHandle(handle)
        self.assert_success(self.run_uninstall("-Yes", "-DeleteData"))
        self.assertFalse(self.install.exists())
