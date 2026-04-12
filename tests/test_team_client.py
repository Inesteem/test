"""Tests for team_client.py — HTTP handler including the new /connect and /client_info endpoints."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch, MagicMock

import pytest

import team_client


def _make_server():
    """Start a TeamClientHandler on a free port; return (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), team_client.TeamClientHandler)
    server.daemon_threads = True
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


def _post(url, payload):
    """POST JSON to url; return (status, dict)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(url):
    """GET url; return (status, dict)."""
    with urllib.request.urlopen(url, timeout=3) as resp:
        return resp.status, json.loads(resp.read())


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset all module-level state before each test."""
    old_gm = team_client._game_master_url
    old_tn = team_client._team_num
    old_cfg = team_client._team_config
    old_port = team_client._server_port
    old_event_set = team_client._config_event.is_set()

    team_client._game_master_url = ""
    team_client._team_num = None
    team_client._team_config = None
    team_client._server_port = 7777
    team_client._config_event.clear()

    yield

    team_client._game_master_url = old_gm
    team_client._team_num = old_tn
    team_client._team_config = old_cfg
    team_client._server_port = old_port
    if old_event_set:
        team_client._config_event.set()
    else:
        team_client._config_event.clear()


@pytest.fixture
def server():
    s, url = _make_server()
    yield url
    s.shutdown()
    s.server_close()


# ── /client_info ──

class TestClientInfo:

    def test_no_config_returns_config_done_false(self, server):
        status, data = _get(f"{server}/client_info")
        assert status == 200
        assert data["config_done"] is False
        assert data["team_num"] is None

    def test_config_done_true_when_gm_and_team_set(self, server):
        team_client._game_master_url = "http://10.0.0.2:9000"
        team_client._team_num = 3
        status, data = _get(f"{server}/client_info")
        assert status == 200
        assert data["config_done"] is True
        assert data["team_num"] == 3
        assert data["default_name"] == "Team 3"

    def test_port_field_reflects_server_port(self, server):
        team_client._server_port = 8888
        _, data = _get(f"{server}/client_info")
        assert data["port"] == 8888

    def test_config_field_present(self, server):
        team_client._game_master_url = "http://10.0.0.2:9000"
        team_client._team_num = 1
        with team_client._team_config_lock:
            team_client._team_config = {"name": "Blue", "color": "#0000ff", "color_name": "Blue"}
        _, data = _get(f"{server}/client_info")
        assert data["config"] is not None
        assert data["config"]["name"] == "Blue"

    def test_config_done_false_when_only_team_num_set(self, server):
        """Both gm url AND team_num must be set for config_done to be True."""
        team_client._team_num = 2
        team_client._game_master_url = ""
        _, data = _get(f"{server}/client_info")
        assert data["config_done"] is False

    def test_config_done_false_when_only_gm_set(self, server):
        team_client._game_master_url = "http://10.0.0.2:9000"
        team_client._team_num = None
        _, data = _get(f"{server}/client_info")
        assert data["config_done"] is False


# ── /connect ──

class TestConnect:

    def _fake_register_server(self, team_num):
        """Start a tiny HTTP server that accepts POST /register and returns team_num."""
        import http.server

        class FakeGMHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                body = json.dumps({"team_num": team_num}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeGMHandler)
        srv.daemon_threads = True
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv

    def test_missing_game_master_returns_400(self, server):
        status, data = _post(f"{server}/connect", {})
        assert status == 400
        assert "game_master" in data["error"]

    def test_empty_game_master_returns_400(self, server):
        status, data = _post(f"{server}/connect", {"game_master": "  "})
        assert status == 400

    def test_unreachable_master_returns_502(self, server):
        # Port 1 is always refused
        status, data = _post(f"{server}/connect", {"game_master": "127.0.0.1:1"})
        assert status == 502
        assert "Cannot reach" in data["error"]

    def test_successful_connect_sets_globals_and_returns_team_num(self, server):
        fake_gm = self._fake_register_server(team_num=4)
        gm_port = fake_gm.server_address[1]
        try:
            status, data = _post(f"{server}/connect", {"game_master": f"127.0.0.1:{gm_port}"})
            assert status == 200
            assert data["ok"] is True
            assert data["team_num"] == 4
            assert team_client._team_num == 4
            assert f":{gm_port}" in team_client._game_master_url
        finally:
            fake_gm.shutdown()
            fake_gm.server_close()

    def test_successful_connect_adds_http_scheme(self, server):
        fake_gm = self._fake_register_server(team_num=2)
        gm_port = fake_gm.server_address[1]
        try:
            _post(f"{server}/connect", {"game_master": f"127.0.0.1:{gm_port}"})
            assert team_client._game_master_url.startswith("http://")
        finally:
            fake_gm.shutdown()
            fake_gm.server_close()

    def test_successful_connect_sets_config_event(self, server):
        fake_gm = self._fake_register_server(team_num=1)
        gm_port = fake_gm.server_address[1]
        try:
            assert not team_client._config_event.is_set()
            _post(f"{server}/connect", {"game_master": f"127.0.0.1:{gm_port}"})
            assert team_client._config_event.is_set()
        finally:
            fake_gm.shutdown()
            fake_gm.server_close()

    def test_failed_connect_does_not_set_config_event(self, server):
        _post(f"{server}/connect", {"game_master": "127.0.0.1:1"})
        assert not team_client._config_event.is_set()

    def test_http_prefix_preserved(self, server):
        fake_gm = self._fake_register_server(team_num=5)
        gm_port = fake_gm.server_address[1]
        try:
            _post(f"{server}/connect", {"game_master": f"http://127.0.0.1:{gm_port}"})
            # Should not double-prefix
            assert team_client._game_master_url.count("http://") == 1
        finally:
            fake_gm.shutdown()
            fake_gm.server_close()

    def test_invalid_json_returns_400(self, server):
        raw = b"not-json"
        req = urllib.request.Request(
            f"{server}/connect", data=raw,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        assert status == 400


# ── HTML page ──

class TestHTMLPage:

    def test_root_returns_html(self, server):
        with urllib.request.urlopen(f"{server}/", timeout=3) as resp:
            content = resp.read().decode()
        assert "<!DOCTYPE html>" in content

    def test_config_div_present(self, server):
        with urllib.request.urlopen(f"{server}/", timeout=3) as resp:
            content = resp.read().decode()
        assert 'id="config"' in content
        assert 'id="gm-input"' in content
        assert 'id="port-input"' in content
        assert 'id="connect-btn"' in content

    def test_setup_div_starts_hidden(self, server):
        with urllib.request.urlopen(f"{server}/", timeout=3) as resp:
            content = resp.read().decode()
        # The #setup div must carry display:none so config screen shows first
        assert 'id="setup" style="display:none"' in content

    def test_submitConnect_function_present(self, server):
        with urllib.request.urlopen(f"{server}/", timeout=3) as resp:
            content = resp.read().decode()
        assert "function submitConnect()" in content

    def test_config_status_element_present(self, server):
        with urllib.request.urlopen(f"{server}/", timeout=3) as resp:
            content = resp.read().decode()
        assert 'id="config-status"' in content
