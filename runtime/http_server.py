"""Waitress ownership with cleanup even when binding the port fails."""

from threading import Event

from waitress import create_server, wasyncore
from waitress.task import ThreadedTaskDispatcher


class LocalHTTPServer:
    """Own socket channels and request threads together."""

    def __init__(self, application, **options):
        self.socket_map = {}
        self.dispatcher = ThreadedTaskDispatcher()
        self.loop_started = Event()
        self.loop_finished = Event()
        self.sockets_closed = Event()
        threads = options.pop("threads", 4)
        try:
            self.server = create_server(
                application, map=self.socket_map, _dispatcher=self.dispatcher, **options,
            )
            self.dispatcher.set_thread_count(threads)
        except BaseException:
            self.close()
            raise

    def run(self):
        """Serve until all owned sockets are closed."""
        self.loop_started.set()
        try:
            self.server.run()
        finally:
            self.loop_finished.set()

    def _close_sockets(self):
        """Close sockets on the event-loop thread, avoiding concurrent select."""
        try:
            wasyncore.close_all(self.socket_map)
        finally:
            self.sockets_closed.set()

    def close(self):
        """Drain request threads and close all sockets, including keep-alive."""
        self.dispatcher.shutdown(cancel_pending=False, timeout=2)
        with self.dispatcher.lock:
            if self.dispatcher.threads:
                raise RuntimeError("Requisições HTTP não encerraram no prazo.")
        if self.sockets_closed.is_set():
            return
        if self.loop_started.is_set() and not self.loop_finished.is_set():
            self.server.trigger.pull_trigger(self._close_sockets)
            if not self.sockets_closed.wait(timeout=2):
                if not self.loop_finished.is_set():
                    raise RuntimeError("Loop HTTP não confirmou fechamento dos sockets.")
                self._close_sockets()
        else:
            self._close_sockets()
