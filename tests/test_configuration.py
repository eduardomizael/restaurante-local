"""Configuration navigation and persistent application display identity."""

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.configuration.models import ApplicationConfiguration
from apps.configuration.services import save_application_configuration
from apps.core.domain import DomainConflict
from apps.core.models import DomainEvent
from runtime.state import state


class ConfigurationTests(TestCase):
    def setUp(self):
        state.update(running=True)

    def tearDown(self):
        state.update(running=False)

    def test_main_navigation_only_links_to_application_areas(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'href="/configuration/"')
        for name in ("numbering", "document_configuration", "equipment_configuration"):
            self.assertNotContains(response, f'href="{reverse(name)}"')
        for text in ("Balança real", "Balança simulada", "Impressão real",
                     "Aplicação independente", "Aceitação pelo spooler"):
            self.assertNotContains(response, text)
        self.assertFalse(ApplicationConfiguration.objects.exists())

    def test_all_configuration_pages_have_shared_subnavigation_and_current_section(self):
        names = ("application_configuration", "numbering", "document_configuration", "equipment_configuration")
        for name in names:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, 'aria-label="Seções de configurações"')
                self.assertContains(response, f'href="{reverse(name)}" aria-current="page"')
                for destination in names:
                    self.assertContains(response, f'href="{reverse(destination)}"')
        self.assertFalse(ApplicationConfiguration.objects.exists())

    def test_save_name_persists_across_pages_without_creating_historical_documents(self):
        response = self.client.post(reverse("application_configuration"), {
            "display_name": "  Restaurante São José  ", "expected_revision": 0,
        })
        self.assertRedirects(response, reverse("application_configuration"))
        saved = ApplicationConfiguration.objects.get(pk=1)
        self.assertEqual(saved.display_name, "Restaurante São José")
        self.assertEqual(saved.revision, 1)
        self.assertTrue(DomainEvent.objects.filter(kind="APPLICATION_CONFIGURATION_SAVED").exists())
        for name in ("home", "catalogue", "print_history", "equipment_configuration"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "<title>Restaurante São José</title>", html=True)
            self.assertContains(response, '<a class="brand" href="/">Restaurante São José</a>', html=True)

    def test_invalid_and_stale_names_preserve_saved_identity(self):
        save_application_configuration(display_name="Nome original", expected_revision=0)
        for name in ("", "   ", "x" * 81):
            response = self.client.post(reverse("application_configuration"), {
                "display_name": name, "expected_revision": 1,
            })
            self.assertEqual(response.status_code, 400)
        with self.assertRaises(ValidationError):
            save_application_configuration(display_name="Nome\ninválido", expected_revision=1)
        with self.assertRaises(DomainConflict):
            save_application_configuration(display_name="Outro nome", expected_revision=0)
        response = self.client.post(reverse("application_configuration"), {
            "display_name": "Outro nome", "expected_revision": 0,
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ApplicationConfiguration.objects.get(pk=1).display_name, "Nome original")

    def test_saved_name_is_escaped_in_navigation_and_title(self):
        save_application_configuration(display_name="<script>alert(1)</script>", expected_revision=0)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_name_write_requires_csrf_post_and_active_runtime(self):
        client = Client(enforce_csrf_checks=True)
        url = reverse("application_configuration")
        data = {"display_name": "Restaurante", "expected_revision": 0}
        self.assertEqual(client.post(url, data).status_code, 403)
        self.assertEqual(self.client.put(url, data).status_code, 405)
        state.update(running=False)
        self.assertEqual(self.client.post(url, data).status_code, 503)
        self.assertFalse(ApplicationConfiguration.objects.exists())
