"""HTTP server exposing game state for team clients to poll.

Runs in a daemon thread alongside the curses UI.

    GET  /state              → current game state as JSON
    POST /register           → register a client, get assigned team number
    POST /team_config        → submit team name+color (validated for uniqueness)
    GET  /gm                 → game master browser UI (gm.html)
    GET  /gm/static/<file>   → static files from the static/ directory
    GET  /gm/events          → SSE stream (WebDisplay state pushes)
    POST /gm/command         → receive a keyboard command from the browser GM UI
"""

import json
import os
import queue
import re
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Resolve the static/ directory relative to this file (quiz/../static/)
_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

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
        elif self.path == "/gm":
            self._serve_file("gm.html", "text/html")
        elif self.path.startswith("/gm/static/"):
            filename = self.path[len("/gm/static/"):]
            self._serve_file(filename, self._guess_content_type(filename))
        elif self.path == "/gm/events":
            self._handle_sse()
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
        elif self.path.rstrip("/") == "/gm/command":
            self._handle_gm_command(body)
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

    def _handle_gm_command(self, body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send(400, '{"error":"invalid json"}')
            return

        cmd = data.get("cmd", "")
        web_display = getattr(self.server, "web_display", None)
        if cmd and web_display is not None:
            web_display.push_command(cmd)
        self._send(200, '{"ok":true}')

    def _handle_sse(self):
        """Server-Sent Events stream for WebDisplay."""
        web_display = getattr(self.server, "web_display", None)
        if web_display is None:
            self._send(503, '{"error":"no web display"}')
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        client_queue = web_display.add_sse_client()
        try:
            while True:
                try:
                    data = client_queue.get(timeout=15)
                    msg = f"data: {json.dumps(data)}\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                except queue.Empty:
                    # Keepalive comment — keeps the connection alive through
                    # proxies and browser idle timeouts.
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            web_display.remove_sse_client(client_queue)

    def _serve_file(self, filename, content_type):
        filepath = os.path.join(_STATIC_DIR, filename)
        # Guard against path traversal
        try:
            filepath = os.path.realpath(filepath)
            static_real = os.path.realpath(_STATIC_DIR)
            if not filepath.startswith(static_real + os.sep) and filepath != static_real:
                self._send(403, '{"error":"forbidden"}')
                return
        except Exception:
            self._send(403, '{"error":"forbidden"}')
            return

        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self._send(404, '{"error":"not found"}')

    @staticmethod
    def _guess_content_type(filename):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "html": "text/html",
            "css":  "text/css",
            "js":   "application/javascript",
            "json": "application/json",
            "svg":  "image/svg+xml",
            "png":  "image/png",
            "ico":  "image/x-icon",
        }.get(ext, "application/octet-stream")

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


def start_game_master_server(game_state, port=9000, max_teams=None,
                             web_display=None):
    """Start the game master HTTP server in a daemon thread. Returns the server.

    web_display: optional WebDisplay instance.  When provided, the server
        will serve the GM browser UI at /gm, stream SSE at /gm/events, and
        accept keyboard commands at POST /gm/command.
    """
    server = ReusableThreadingHTTPServer(("0.0.0.0", port), GameMasterHandler)
    server.game_state = game_state
    server.max_teams = max_teams
    server.registration_lock = threading.Lock()
    server.web_display = web_display  # None if not using WebDisplay
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
