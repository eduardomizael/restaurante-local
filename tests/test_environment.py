"""Environment loading and isolation from operational data."""

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase

from config.environment import load_environment
from runtime.installation import resolve_data_dir


class EnvironmentTests(SimpleTestCase):
    def test_missing_file_uses_defaults_without_creating_data(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"USERPROFILE": directory}, clear=True):
            path = Path(directory) / ".env"
            environment = load_environment(path)
            self.assertFalse(environment.bool("DEBUG"))
            self.assertEqual(environment.str("TIME_ZONE"), "America/Sao_Paulo")
            self.assertEqual(environment.str("LOCAL_WEIGHING_DATA_DIR"), "")
            self.assertEqual(environment.str("SECRET_KEY", default="installation-key"), "installation-key")
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_dotenv_parses_types_and_selects_external_data_directory(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"USERPROFILE": directory}, clear=True):
            data_dir = Path(directory) / "dados com espaço"
            path = Path(directory) / ".env"
            path.write_text(
                f'DEBUG=True\nTIME_ZONE=UTC\nLOCAL_WEIGHING_DATA_DIR="{data_dir.as_posix()}"\n'
                "SECRET_KEY=local-test-key\n", encoding="utf-8",
            )
            environment = load_environment(path)
            self.assertTrue(environment.bool("DEBUG"))
            self.assertEqual(environment.str("TIME_ZONE"), "UTC")
            self.assertEqual(environment.str("SECRET_KEY", default="installation-key"), "local-test-key")
            self.assertEqual(resolve_data_dir(), data_dir.resolve())
            self.assertFalse(data_dir.exists())

    def test_process_environment_takes_precedence_over_dotenv(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "DEBUG": "False", "LOCAL_WEIGHING_DATA_DIR": directory, "USERPROFILE": directory,
        }, clear=True):
            path = Path(directory) / ".env"
            path.write_text("DEBUG=True\nLOCAL_WEIGHING_DATA_DIR=ignored\n", encoding="utf-8")
            environment = load_environment(path)
            self.assertFalse(environment.bool("DEBUG"))
            self.assertEqual(resolve_data_dir(), Path(directory).resolve())

    def test_default_storage_uses_windows_user_data_directory(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "USERPROFILE": directory, "LOCALAPPDATA": directory,
        }, clear=True):
            load_environment(Path(directory) / ".env")
            self.assertEqual(resolve_data_dir(), Path(directory) / "RestauranteLocal")
            self.assertFalse(resolve_data_dir().exists())
