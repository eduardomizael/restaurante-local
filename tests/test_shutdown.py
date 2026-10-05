"""Shutdown confirmation, CSRF and response delivery without real hardware."""

from threading import Event, Thread
from unittest.mock import Mock, patch
import sys

from django.test import Client, RequestFactory, TransactionTestCase, SimpleTestCase

from apps.core.views import shutdown
from runtime.state import state
from runtime.tray import run_tray


class ShutdownHTTPTests(TransactionTestCase):
    def setUp(self):
        self.stop = Mock()
        state.update(running=True)
        state.bind_shutdown(self.stop)
        self.addCleanup(state.unbind_shutdown, self.stop)
        self.addCleanup(state.update, running=False)

    def test_confirmation_and_cancel_do_not_stop_application(self):
        self.assertContains(self.client.get("/runtime/shutdown/confirm/"), "Continuar usando")
        self.client.get("/")
        self.stop.assert_not_called()
        self.assertTrue(state.snapshot()["running"])

    def test_post_and_csrf_are_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get("/runtime/shutdown/").status_code, 405)
        self.assertEqual(client.post("/runtime/shutdown/", {"confirmed": "yes"}).status_code, 403)
        client.get("/runtime/shutdown/confirm/")
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post("/runtime/shutdown/", HTTP_X_CSRFTOKEN=token).status_code, 400)
        response = client.post("/runtime/shutdown/", {"confirmed": "yes"}, HTTP_X_CSRFTOKEN=token)
        self.assertContains(response, "Encerramento solicitado")
        self.stop.assert_called_once()
        self.assertEqual(client.post("/runtime/shutdown/", {"confirmed": "yes"}, HTTP_X_CSRFTOKEN=token).status_code, 409)

    def test_signal_waits_for_response_close_and_mutations_are_blocked(self):
        response = shutdown(RequestFactory().post("/runtime/shutdown/", {"confirmed": "yes"}))
        self.assertContains(response, "Encerramento solicitado")
        self.stop.assert_not_called()
        self.assertFalse(state.snapshot()["running"])
        self.assertEqual(self.client.post("/runtime/pause/").status_code, 409)
        response.close()
        response.close()
        self.stop.assert_called_once()

    def test_stopped_or_unbound_runtime_rejects_shutdown(self):
        state.unbind_shutdown(self.stop)
        self.assertEqual(self.client.post("/runtime/shutdown/", {"confirmed": "yes"}).status_code, 409)
        self.stop.assert_not_called()


class TrayShutdownTests(SimpleTestCase):
    def test_interface_stop_wakes_tray_loop(self):
        application = Mock(stop_event=Event())
        icon = Mock()
        pystray = Mock()
        pystray.Icon.return_value = icon

        def run(*, setup):
            watcher = Thread(target=setup, args=(icon,))
            watcher.start()
            application.stop_event.set()
            watcher.join(timeout=2)
            self.assertFalse(watcher.is_alive())

        icon.run.side_effect = run
        with patch.dict(sys.modules, {"pystray": pystray}):
            run_tray(application)
        self.assertTrue(icon.visible)
        self.assertTrue(icon.stop.called)
