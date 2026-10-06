"""Dedicated browser ownership and private reopening, without personal windows."""

import os
from pathlib import Path
import subprocess
import tempfile
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.test import Client, SimpleTestCase

from runtime.browser import ApplicationBrowser, find_browser
from runtime.state import state


@skipUnless(os.name == "nt", "Windows browser process ownership")
class BrowserOwnershipTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.browser = ApplicationBrowser(Path(self.directory.name), "a" * 32)
        self.find = patch("runtime.browser.find_browser", return_value=("edge", Path("C:/test/msedge.exe")))
        self.find.start()
        self.addCleanup(self.find.stop)
        self.spawn = patch("runtime.browser.subprocess.Popen")
        self.process = self.spawn.start().return_value
        self.process.poll.return_value = None
        self.addCleanup(self.spawn.stop)

    def test_edge_opens_fullscreen_with_an_isolated_profile(self):
        self.browser.open("http://127.0.0.1:8765/")
        arguments = self.spawn.target.Popen.call_args.args[0]
        self.assertIn("--kiosk", arguments)
        self.assertIn("--edge-kiosk-type=fullscreen", arguments)
        profile = Path(self.directory.name) / "browser" / ("a" * 32)
        self.assertIn(f"--user-data-dir={profile}", arguments)
        self.assertTrue(profile.is_dir())

    def test_chrome_fallback_and_maximized_mode(self):
        with patch("runtime.browser.find_browser", return_value=("chrome", Path("C:/test/chrome.exe"))):
            self.browser.open("http://127.0.0.1:8765/")
            self.assertNotIn("--edge-kiosk-type=fullscreen", self.spawn.target.Popen.call_args.args[0])
            self.browser.mode = "maximized"
            self.browser.open("http://127.0.0.1:8765/status/")
            arguments = self.spawn.target.Popen.call_args.args[0]
            self.assertIn("--start-maximized", arguments)
            self.assertIn("--app=http://127.0.0.1:8765/status/", arguments)

    def test_closes_only_live_processes_it_launched_and_rejects_new_windows(self):
        self.browser.open("http://127.0.0.1:8765/")
        own_profile = self.browser.profile
        other_profile = Path(self.directory.name) / "browser" / ("b" * 32)
        other_profile.mkdir()
        self.process.poll.side_effect = [None, 0]
        exited = Mock()
        exited.poll.return_value = 0
        self.browser.processes.append(exited)
        with patch("runtime.browser.close_windows") as close:
            self.browser.close()
        close.assert_called_once_with(self.process.pid)
        self.process.wait.assert_called_once()
        self.process.terminate.assert_not_called()
        exited.wait.assert_not_called()
        self.assertFalse(own_profile.exists())
        self.assertTrue(other_profile.is_dir())
        self.browser.open("http://127.0.0.1:8765/")
        self.assertEqual(self.spawn.target.Popen.call_count, 1)

    def test_unresponsive_window_uses_only_owned_process_handle(self):
        self.browser.open("http://127.0.0.1:8765/")
        self.process.wait.side_effect = [subprocess.TimeoutExpired("owned", 3), None]
        with patch("runtime.browser.close_windows"), self.assertLogs("runtime.browser", level="WARNING"):
            self.browser.close()
        self.process.terminate.assert_called_once()

    def test_rejects_remote_urls_and_invalid_profiles_before_spawn(self):
        for url in ("https://example.com/", "http://localhost:8765/", "file:///C:/test"):
            with self.assertRaises(ValueError):
                self.browser.open(url)
        self.browser.instance_id = "../personal"
        with self.assertRaises(ValueError):
            self.browser.open("http://127.0.0.1:8765/")
        self.spawn.target.Popen.assert_not_called()

    def test_discovery_prefers_edge_and_falls_back_to_chrome(self):
        self.find.stop()
        with patch.dict(os.environ, {"ProgramFiles(x86)": self.directory.name,
                                     "ProgramFiles": self.directory.name, "LOCALAPPDATA": self.directory.name}):
            chrome = Path(self.directory.name) / "Google/Chrome/Application/chrome.exe"
            edge = Path(self.directory.name) / "Microsoft/Edge/Application/msedge.exe"
            for executable in (chrome, edge):
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.touch()
            self.assertEqual(find_browser(), ("edge", edge))
            edge.unlink()
            self.assertEqual(find_browser(), ("chrome", chrome))
            chrome.unlink()
            with self.assertRaisesRegex(RuntimeError, "Instale Microsoft Edge"):
                find_browser()


class BrowserControlTests(SimpleTestCase):
    def setUp(self):
        self.handler = Mock()
        self.token = "a" * 64
        state.update(running=True)
        state.bind_browser(self.handler, self.token)
        self.addCleanup(state.unbind_browser, self.token)
        self.addCleanup(state.update, running=False)
        self.client = Client(enforce_csrf_checks=True)

    def test_reopening_requires_post_csrf_and_private_capability(self):
        url = "/runtime/window/open/"
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, HTTP_X_LOCAL_BROWSER_TOKEN=self.token).status_code, 403)
        response = self.client.get("/health/")
        self.assertNotIn(self.token.encode(), response.content)
        csrf = self.client.cookies["csrftoken"].value
        for token in ("", "b" * 64, "não autorizado"):
            self.assertEqual(self.client.post(url, HTTP_X_CSRFTOKEN=csrf,
                             HTTP_X_LOCAL_BROWSER_TOKEN=token).status_code, 403)
        self.handler.assert_not_called()
        self.assertEqual(self.client.post(url, HTTP_X_CSRFTOKEN=csrf,
                         HTTP_X_LOCAL_BROWSER_TOKEN=self.token).status_code, 204)
        self.handler.assert_called_once_with()
        self.assertNotIn(self.token, str(state.snapshot()))
        state.update(running=False)
        self.assertEqual(self.client.post(url, HTTP_X_CSRFTOKEN=csrf,
                         HTTP_X_LOCAL_BROWSER_TOKEN=self.token).status_code, 409)
        self.assertEqual(self.handler.call_count, 1)
