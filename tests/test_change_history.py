import json
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.core.history_selectors import change_history, history_seen
from apps.core.history_services import acknowledge_history


class ChangeHistoryTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name) / "data"
        self.override = override_settings(DATA_DIR=self.data)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_bundled_history_has_required_fields_and_descending_dates(self):
        history = change_history()
        self.assertEqual(len(history["fingerprint"]), 64)
        self.assertEqual([release["date"] for release in history["releases"]], sorted(
            [release["date"] for release in history["releases"]], reverse=True))
        project = tomllib.loads((Path(settings.BASE_DIR) / "pyproject.toml").read_text())
        self.assertEqual(history["releases"][0]["version"], project["project"]["version"])
        self.assertEqual(len(history["releases"][0]["changes"]), 6)
        self.assertIn("resources", (Path(settings.BASE_DIR) / "packaging/restaurante.spec").read_text())

    def test_automatic_get_does_not_write_and_stops_after_acknowledgment(self):
        url = reverse("change_history") + "?automatic=1"
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Histórico de mudanças")
        self.assertFalse(self.data.exists())
        response = self.client.post(reverse("acknowledge_change_history"), {
            "fingerprint": change_history()["fingerprint"]}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["HX-Trigger"], "changeHistoryAcknowledged")
        self.assertEqual(self.client.get(url).status_code, 204)
        self.assertContains(self.client.get(reverse("change_history")), "Troca de produto de uma pesagem")

    def test_state_survives_new_client_and_damaged_file_reopens(self):
        fingerprint = change_history()["fingerprint"]
        acknowledge_history(fingerprint)
        self.assertTrue(history_seen(fingerprint))
        self.assertEqual(Client().get(reverse("change_history") + "?automatic=1").status_code, 204)
        (self.data / "change-history-state.json").write_text("[]")
        self.assertFalse(history_seen(fingerprint))
        (self.data / "change-history-state.json").write_text("broken")
        self.assertFalse(history_seen(fingerprint))

    def test_content_change_reopens_even_with_same_entry_count(self):
        acknowledge_history(change_history()["fingerprint"])
        entries = [{"version": "0.2.0", "date": "2026-10-12", "changes": [
            {"summary": "Nova mudança", "description": "Detalhes"}]}]
        root = Path(self.directory.name) / "program"
        (root / "resources").mkdir(parents=True)
        (root / "resources/change-history.json").write_text(json.dumps(entries))
        with override_settings(BASE_DIR=root):
            first = change_history()["fingerprint"]
            acknowledge_history(first)
            entries[0]["changes"][0]["description"] = "Detalhes corrigidos"
            (root / "resources/change-history.json").write_text(json.dumps(entries))
            self.assertNotEqual(first, change_history()["fingerprint"])
            self.assertEqual(self.client.get(reverse("change_history") + "?automatic=1").status_code, 200)
            with self.assertRaises(ValueError):
                acknowledge_history(first)

    def test_groups_are_sorted_by_date_then_numeric_version_and_rendered_together(self):
        entries = [{"version": version, "date": date, "changes": [
            {"summary": "Mudança " + version, "description": "Detalhes " + version} ]}
            for version, date in [("0.9.0", "2026-10-12"), ("0.10.0", "2026-10-12"), ("0.8.0", "2026-10-11")]]
        root = Path(self.directory.name)
        (root / "resources").mkdir()
        path = root / "resources/change-history.json"
        path.write_text(json.dumps(entries))
        with override_settings(BASE_DIR=root):
            self.assertEqual([release["version"] for release in change_history()["releases"]],
                             ["0.10.0", "0.9.0", "0.8.0"])
            response = self.client.get(reverse("change_history"), HTTP_HX_REQUEST="true")
            self.assertContains(response, "Versão 0.10.0 —")
            self.assertContains(response, "12/10/2026")
            self.assertContains(response, "Mudança 0.10.0")
            self.assertContains(response, "Detalhes 0.10.0")
            self.assertContains(response, 'class="card change-history-release"', count=3)
            for invalid in [
                [entries[0], entries[0]],
                [{**entries[0], "changes": []}],
                [{**entries[0], "version": "invalid"}],
                [{**entries[0], "changes": [{"summary": "Sem descrição"}]}],
            ]:
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    change_history()

    def test_failed_atomic_replace_preserves_previous_record_and_removes_temp(self):
        acknowledge_history(change_history()["fingerprint"])
        original = (self.data / "change-history-state.json").read_bytes()
        with patch("apps.core.history_services.os.replace", side_effect=OSError("blocked")):
            response = self.client.post(reverse("acknowledge_change_history"), {
                "fingerprint": change_history()["fingerprint"]}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Tente fechar novamente", status_code=409)
        self.assertEqual(response.headers["X-Change-History-Error"], "1")
        self.assertEqual((self.data / "change-history-state.json").read_bytes(), original)
        self.assertEqual(len(list(self.data.iterdir())), 1)

    def test_post_requires_csrf_and_current_fingerprint(self):
        secure_client = Client(enforce_csrf_checks=True)
        self.assertEqual(secure_client.post(reverse("acknowledge_change_history"), {}).status_code, 403)
        self.assertEqual(self.client.post(reverse("acknowledge_change_history"), {
            "fingerprint": "old"}, HTTP_HX_REQUEST="true").status_code, 409)
        self.assertFalse(self.data.exists())

    def test_normal_post_redirects_and_unavailable_history_does_not_block_start(self):
        response = self.client.post(reverse("acknowledge_change_history"), {
            "fingerprint": change_history()["fingerprint"]})
        self.assertRedirects(response, reverse("status"), fetch_redirect_response=False)
        with override_settings(BASE_DIR=Path(self.directory.name)):
            self.assertEqual(self.client.get(reverse("change_history") + "?automatic=1").status_code, 204)
            self.assertEqual(self.client.get(reverse("change_history")).status_code, 503)
