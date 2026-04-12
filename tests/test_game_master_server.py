"""Tests for quiz/game_master_server.py — HTTP server exposing game state."""

import json
import urllib.error
import urllib.request

import pytest

from quiz.game_state import GameState
from quiz.game_master_server import start_game_master_server


@pytest.fixture
def running_server():
    gs = GameState()
    gs.update(phase="buzzing", question_num=3, question_text="Test?")
    server = start_game_master_server(gs, port=0)  # port 0 = OS picks free port
    port = server.server_address[1]
    yield gs, server, f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


class TestGameMasterServer:

    def test_get_state_returns_snapshot(self, running_server):
        gs, server, url = running_server
        with urllib.request.urlopen(f"{url}/state", timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["phase"] == "buzzing"
        assert data["question_num"] == 3
        assert data["question_text"] == "Test?"

    def test_get_root_also_returns_state(self, running_server):
        gs, server, url = running_server
        with urllib.request.urlopen(f"{url}/", timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["phase"] == "buzzing"

    def test_state_updates_are_visible(self, running_server):
        gs, server, url = running_server
        gs.update(phase="answering", active_team=2)
        with urllib.request.urlopen(f"{url}/state", timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["phase"] == "answering"
        assert data["active_team"] == 2

    def test_cors_header_present(self, running_server):
        _, _, url = running_server
        with urllib.request.urlopen(f"{url}/state", timeout=2) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    def test_unknown_path_returns_404(self, running_server):
        _, _, url = running_server
        try:
            urllib.request.urlopen(f"{url}/nonexistent", timeout=2)
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_server_survives_concurrent_requests(self, running_server):
        """ThreadingHTTPServer should handle multiple concurrent requests."""
        import threading
        _, _, url = running_server
        errors = []

        def fetch():
            try:
                with urllib.request.urlopen(f"{url}/state", timeout=2) as resp:
                    json.loads(resp.read())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fetch) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
