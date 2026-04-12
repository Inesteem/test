"""Tests for quiz/team_answer_source.py — polls team client HTTP servers."""

import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import pytest

from quiz.team_answer_source import TeamAnswerSource


# ---------------------------------------------------------------------------
# Fake team client HTTP server
# ---------------------------------------------------------------------------

class FakeTeamClientHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/answer":
            body = json.dumps({"answer": self.server.state["answer"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/reset":
            self.server.state["answer"] = None
            self.server.state["reset_count"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # silent


@pytest.fixture
def fake_client():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTeamClientHandler)
    server.state = {"answer": None, "reset_count": 0}
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTeamAnswerSource:

    def test_poll_returns_none_when_no_answer(self, fake_client):
        server, url = fake_client
        src = TeamAnswerSource({1: url})
        assert src.poll_once(1) is None

    def test_poll_returns_answer_when_set(self, fake_client):
        server, url = fake_client
        server.state["answer"] = "b"
        src = TeamAnswerSource({1: url})
        assert src.poll_once(1) == "b"

    def test_poll_returns_none_for_unknown_buzzer(self, fake_client):
        _, url = fake_client
        src = TeamAnswerSource({1: url})
        assert src.poll_once(99) is None

    def test_poll_returns_none_for_invalid_answer(self, fake_client):
        server, url = fake_client
        server.state["answer"] = "z"  # not a/b/c
        src = TeamAnswerSource({1: url})
        assert src.poll_once(1) is None

    def test_reset_clears_server_answer(self, fake_client):
        import time
        server, url = fake_client
        server.state["answer"] = "c"
        src = TeamAnswerSource({1: url})
        src.reset(1)
        time.sleep(0.3)  # reset is async (fire-and-forget)
        assert server.state["answer"] is None
        assert server.state["reset_count"] == 1

    def test_reset_unknown_buzzer_no_crash(self, fake_client):
        _, url = fake_client
        src = TeamAnswerSource({1: url})
        src.reset(99)  # should not raise

    def test_poll_unreachable_server_returns_none(self):
        src = TeamAnswerSource({1: "http://127.0.0.1:1"})  # port 1 = reserved, unreachable
        assert src.poll_once(1) is None

    def test_reset_unreachable_server_no_crash(self):
        src = TeamAnswerSource({1: "http://127.0.0.1:1"})
        src.reset(1)  # should not raise

    def test_trailing_slash_in_url_is_stripped(self, fake_client):
        _, url = fake_client
        src = TeamAnswerSource({1: url + "/"})
        # Should still work — internal normalization strips trailing slash
        assert src.poll_once(1) is None  # no answer set

    def test_multiple_teams(self, fake_client):
        server, url = fake_client
        server.state["answer"] = "a"
        src = TeamAnswerSource({1: url, 2: url})
        assert src.poll_once(1) == "a"
        assert src.poll_once(2) == "a"
