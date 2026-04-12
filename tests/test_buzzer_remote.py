"""Tests for buzzers/buzzer_remote.py — RemoteBuzzerController."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import pytest

from buzzers.buzzer_remote import RemoteBuzzerController


# ---------------------------------------------------------------------------
# Fake server
# ---------------------------------------------------------------------------

class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(self.server.state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip("/") == "/reset":
            self.server.state["ranking"] = []
            body = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # silence test output


@pytest.fixture
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), FakeHandler)
    server.state = {"buzzers": [1, 2], "ranking": []}
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server, f"http://127.0.0.1:{port}"
    server.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRemoteBuzzerController:

    def test_start_fetches_buzzer_list(self, fake_server):
        server, url = fake_server
        ctrl = RemoteBuzzerController(url)
        ctrl.start()
        assert ctrl.get_buzzers() == [1, 2]

    def test_get_ranking_empty(self, fake_server):
        server, url = fake_server
        ctrl = RemoteBuzzerController(url)
        ctrl.start()
        assert ctrl.get_ranking() == []

    def test_get_ranking_reflects_server_state(self, fake_server):
        server, url = fake_server
        server.state["ranking"] = [2, 1]
        ctrl = RemoteBuzzerController(url)
        ctrl.start()
        assert ctrl.get_ranking() == [2, 1]

    def test_reset_clears_ranking(self, fake_server):
        server, url = fake_server
        server.state["ranking"] = [1, 2]
        ctrl = RemoteBuzzerController(url)
        ctrl.start()
        ctrl.reset()
        assert ctrl.get_ranking() == []

    def test_get_ranking_returns_empty_on_unreachable_server(self):
        ctrl = RemoteBuzzerController("http://127.0.0.1:1")
        assert ctrl.get_ranking() == []

    def test_start_with_unreachable_server_no_crash(self):
        ctrl = RemoteBuzzerController("http://127.0.0.1:1")
        ctrl.start()  # should not raise
        assert ctrl.get_buzzers() == []

    def test_stop_is_noop(self, fake_server):
        _, url = fake_server
        ctrl = RemoteBuzzerController(url)
        ctrl.start()
        ctrl.stop()  # should not raise
