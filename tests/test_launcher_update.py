"""Explicit launcher update choice without operational data or hardware."""

import json
from contextlib import closing
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from runtime.application import InstallationUpdateRequired


class LauncherCommandTests(SimpleTestCase):
    def test_only_installation_gate_uses_exit_code_three_and_stops_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(INSTALLATION={"port": 8765}, DATA_DIR=Path(directory)):
                for error, code in ((InstallationUpdateRequired("Banco desatualizado"), 3),
                                    (RuntimeError("Outra falha"), 1)):
                    with patch("apps.core.management.commands.run_local.LocalApplication") as factory:
                        factory.return_value.start.side_effect = error
                        with self.assertRaises(CommandError) as caught:
                            call_command("run_local", simulate=True, preview_print=True, no_tray=True, no_browser=True)
                        self.assertEqual(caught.exception.returncode, code)
                        factory.return_value.stop.assert_called_once()

    @override_settings(INSTALLATION={})
    def test_absent_installation_uses_same_gate_without_creating_runtime(self):
        with patch("apps.core.management.commands.run_local.LocalApplication") as factory:
            with self.assertRaises(CommandError) as caught:
                call_command("run_local")
            self.assertEqual(caught.exception.returncode, 3)
            factory.assert_not_called()


@skipUnless(os.name == "nt", "Windows batch launcher")
class WindowsLauncherTests(SimpleTestCase):
    def launch(self, directory, answer):
        environment = dict(os.environ, LOCAL_WEIGHING_DATA_DIR=directory,
                           DJANGO_SETTINGS_MODULE="config.settings")
        return subprocess.run(["cmd.exe", "/d", "/c", "Iniciar.bat", "--simulate", "--preview-print",
                               "--no-tray", "--no-browser"], cwd=settings.BASE_DIR, env=environment,
                              input=answer, capture_output=True, timeout=30)

    def test_declining_does_not_initialize_database(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.launch(directory, b"N\r\n")
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn(b"Atualizacao cancelada", result.stdout)
            self.assertFalse((Path(directory) / "db.sqlite3").exists())
            self.assertFalse((Path(directory) / "installation.json").exists())

    def test_failed_update_does_not_retry_startup(self):
        # The updater deliberately rejects data folders inside program files.
        with tempfile.TemporaryDirectory(dir=settings.BASE_DIR) as directory:
            result = self.launch(directory, b"S\r\n")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(b"Nao foi possivel atualizar os dados", result.stdout)
            self.assertNotIn(b"Atualizacao concluida", result.stdout)
            self.assertFalse((Path(directory) / "db.sqlite3").exists())

    def test_accepting_updates_with_backup_then_retries_startup(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as occupied:
            # Block this isolated installation's HTTP port so the retry exits
            # before workers can start. Simulation flags are also passed.
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            path = Path(directory)
            original = {"port": occupied.getsockname()[1], "secret_key": "test-only-" + "x" * 64}
            (path / "installation.json").write_text(json.dumps(original), encoding="utf-8")
            result = self.launch(directory, b"S\r\n")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(b"Atualizacao concluida. Iniciando", result.stdout)
            self.assertEqual(result.stdout.count(b"[S/N]"), 1)
            backups = list((path / "backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads((backups[0] / "installation.json").read_text()), original)
            with closing(sqlite3.connect(path / "db.sqlite3")) as database:
                self.assertIn("logo", {row[1] for row in database.execute("PRAGMA table_info(printing_documentconfiguration)")})
            self.assertNotIn(b"Executar a atualizacao", result.stdout.split(b"Atualizacao concluida")[-1])
