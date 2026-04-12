"""Tests for quiz/game_master_server.py — HTTP server exposing game state."""

import json
import queue
import threading
import time
import urllib.error
import urllib.request

import pytest

from quiz.game_state import GameState
from quiz.game_master_server import start_game_master_server
from quiz.web_display import WebDisplay


@pytest.fixture
def running_server():
    gs = GameState()
    gs.update(phase="buzzing", question_num=3, question_text="Test?")
    server = start_game_master_server(gs, port=0)  # port 0 = OS picks free port
    port = server.server_address[1]
    yield gs, server, f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def gm_server():
    """Server with an attached WebDisplay."""
    gs = GameState()
    wd = WebDisplay()
    server = start_game_master_server(gs, port=0, web_display=wd)
    port = server.server_address[1]
    yield gs, server, wd, f"http://127.0.0.1:{port}"
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


class TestGMRoutes:
    """Tests for /gm, /gm/events, and /gm/command routes."""

    # ── /gm HTML page ──────────────────────────────────────────────────────────

    def test_gm_serves_html(self, gm_server):
        _, _, _, url = gm_server
        with urllib.request.urlopen(f"{url}/gm", timeout=2) as resp:
            ct = resp.headers.get("Content-Type", "")
            body = resp.read().decode()
        assert "text/html" in ct
        assert "<!DOCTYPE html>" in body or "<!doctype html>" in body.lower()

    def test_gm_html_served_without_web_display(self, running_server):
        """The GM HTML page is always served (it handles missing SSE gracefully in JS)."""
        _, _, url = running_server
        with urllib.request.urlopen(f"{url}/gm", timeout=2) as resp:
            ct = resp.headers.get("Content-Type", "")
            body = resp.read().decode()
        assert "text/html" in ct
        assert len(body) > 100

    # ── /gm/events SSE ─────────────────────────────────────────────────────────

    def test_gm_events_without_web_display_returns_503(self, running_server):
        _, _, url = running_server
        try:
            urllib.request.urlopen(f"{url}/gm/events", timeout=2)
            assert False, "expected 503"
        except urllib.error.HTTPError as e:
            assert e.code == 503

    def test_gm_events_sends_current_state_on_connect(self, gm_server):
        _, _, wd, url = gm_server
        wd.draw_error("Test error", "detail")

        received = []
        done = threading.Event()

        def read_one_event():
            req = urllib.request.Request(f"{url}/gm/events")
            req.add_header("Accept", "text/event-stream")
            try:
                conn = urllib.request.urlopen(req, timeout=3)
                while True:
                    line = conn.readline().decode().strip()
                    if line.startswith("data:"):
                        received.append(json.loads(line[5:].strip()))
                        done.set()
                        conn.close()
                        return
            except Exception:
                done.set()

        t = threading.Thread(target=read_one_event, daemon=True)
        t.start()
        done.wait(timeout=3)
        t.join(timeout=1)

        assert len(received) == 1
        assert received[0]["screen"] == "error"

    def test_gm_events_sse_headers(self, gm_server):
        _, _, wd, url = gm_server
        wd.draw_scores({1: 0}, {1: {"name": "T1", "color": "#fff", "color_name": "White"}})

        headers_captured = {}
        done = threading.Event()

        def read_headers():
            req = urllib.request.Request(f"{url}/gm/events")
            try:
                conn = urllib.request.urlopen(req, timeout=3)
                headers_captured.update(dict(conn.headers))
                conn.readline()  # read at least one line
                conn.close()
            except Exception:
                pass
            finally:
                done.set()

        t = threading.Thread(target=read_headers, daemon=True)
        t.start()
        done.wait(timeout=3)
        t.join(timeout=1)

        ct = headers_captured.get("Content-Type", "")
        assert "text/event-stream" in ct

    # ── POST /gm/command ───────────────────────────────────────────────────────

    def test_gm_command_posts_to_web_display(self, gm_server):
        _, _, wd, url = gm_server
        body = json.dumps({"cmd": "enter"}).encode()
        req = urllib.request.Request(
            f"{url}/gm/command", data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        assert data.get("ok") is True
        # The command must be in the WebDisplay queue
        assert wd.get_command() == "enter"

    def test_gm_command_invalid_json_returns_400(self, gm_server):
        _, _, _, url = gm_server
        req = urllib.request.Request(
            f"{url}/gm/command", data=b"not-json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=2)
            assert False, "expected 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_gm_command_no_web_display_still_returns_200(self, running_server):
        """When there is no WebDisplay the command is silently dropped but response is 200."""
        _, _, url = running_server
        body = json.dumps({"cmd": "space"}).encode()
        req = urllib.request.Request(
            f"{url}/gm/command", data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        assert data.get("ok") is True

    # ── /gm/static/ serving ────────────────────────────────────────────────────

    def test_gm_static_serves_existing_file(self, gm_server):
        _, _, _, url = gm_server
        with urllib.request.urlopen(f"{url}/gm/static/gm.html", timeout=2) as resp:
            ct = resp.headers.get("Content-Type", "")
            body = resp.read().decode()
        assert "text/html" in ct
        assert len(body) > 100  # non-trivial content

    def test_gm_static_missing_file_returns_404(self, gm_server):
        _, _, _, url = gm_server
        try:
            urllib.request.urlopen(f"{url}/gm/static/nope.txt", timeout=2)
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_gm_static_path_traversal_blocked(self, gm_server):
        _, _, _, url = gm_server
        # Attempt to escape the static dir via ../
        try:
            urllib.request.urlopen(
                f"{url}/gm/static/../../quiz/game_master_server.py", timeout=2)
            # A 403 or 404 is both acceptable — what is NOT acceptable is 200
            assert False, "expected 403 or 404"
        except urllib.error.HTTPError as e:
            assert e.code in (403, 404)

    # ── web_display=None backward compat ───────────────────────────────────────

    def test_start_without_web_display_still_works(self):
        gs = GameState()
        server = start_game_master_server(gs, port=0)
        port = server.server_address[1]
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/state", timeout=2) as resp:
                data = json.loads(resp.read())
            assert isinstance(data, dict)
        finally:
            server.shutdown()
            server.server_close()
