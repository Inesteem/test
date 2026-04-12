"""HTTP server exposing game state for team clients to poll.

Runs in a daemon thread alongside the curses UI.

    GET  /state        → current game state as JSON
    POST /register     → register a client, get assigned team number
    POST /team_config  → submit team name+color (validated for uniqueness)
"""

import json
import re
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with SO_REUSEADDR so rebinds don't fail on restart."""
    allow_reuse_address = True
    daemon_threads = True  # per-request threads die with main process


class GameMasterHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/state"):
            state = self.server.game_state.snapshot()
            body = json.dumps(state)
            self._send(200, body)
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        try:
            length = min(int(self.headers.get("Content-Length", 0) or 0), 4096)
        except (ValueError, TypeError):
            length = 0
        body = self.rfile.read(length) if length > 0 else b"{}"

        if self.path.rstrip("/") == "/register":
            self._handle_register(body)
        elif self.path.rstrip("/") == "/team_config":
            self._handle_team_config(body)
        else:
            self._send(404, '{"error":"not found"}')

    def _handle_register(self, body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send(400, '{"error":"invalid json"}')
            return

        callback_url = str(data.get("callback_url", "")).strip()
        if not callback_url:
            self._send(400, '{"error":"callback_url required"}')
            return

        with self.server.registration_lock:
            state = self.server.game_state.snapshot()
            registered = state.get("registered_clients", {})

            # Idempotent: if this URL already registered, return same team_num
            for num, url in registered.items():
                if url == callback_url:
                    self._send(200, json.dumps({"team_num": num}))
                    return

            max_teams = self.server.max_teams
            if max_teams and len(registered) >= max_teams:
                self._send(409, '{"error":"all team slots full"}')
                return

            team_num = len(registered) + 1
            registered[team_num] = callback_url
            self.server.game_state.update(registered_clients=registered)

        self._send(200, json.dumps({"team_num": team_num}))

    def _handle_team_config(self, body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send(400, '{"error":"invalid json"}')
            return

        team_num = data.get("team_num")
        name = str(data.get("name", "")).strip()[:15]
        color = str(data.get("color", "")).strip()
        color_name = str(data.get("color_name", "")).strip()[:20]

        if not name or not _HEX_COLOR_RE.match(color):
            self._send(400, '{"error":"invalid name or color"}')
            return

        with self.server.registration_lock:
            state = self.server.game_state.snapshot()
            registered = state.get("registered_clients", {})

            # team_num could be int or string from JSON round-trip
            if isinstance(team_num, str) and team_num.isdigit():
                team_num = int(team_num)
            if team_num not in registered:
                self._send(400, '{"error":"team not registered"}')
                return

            configs = state.get("team_configs", {})
            claimed = state.get("claimed_colors", [])

            # Check color uniqueness (allow re-submission by same team)
            existing_color = None
            if team_num in configs:
                existing_color = configs[team_num].get("color")

            if color in claimed and color != existing_color:
                self._send(409, json.dumps({
                    "error": "color already taken",
                    "claimed_colors": claimed,
                }))
                return

            # Update claimed colors
            if existing_color and existing_color in claimed:
                claimed.remove(existing_color)
            if color not in claimed:
                claimed.append(color)

            configs[team_num] = {
                "name": name,
                "color": color,
                "color_name": color_name,
            }
            self.server.game_state.update(
                team_configs=configs,
                claimed_colors=claimed,
            )

        self._send(200, json.dumps({
            "ok": True,
            "claimed_colors": claimed,
        }))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send(self, status, body):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        pass  # silent — don't interfere with curses


def start_game_master_server(game_state, port=9000, max_teams=None):
    """Start the game master HTTP server in a daemon thread. Returns the server."""
    server = ReusableThreadingHTTPServer(("0.0.0.0", port), GameMasterHandler)
    server.game_state = game_state
    server.max_teams = max_teams
    server.registration_lock = threading.Lock()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
