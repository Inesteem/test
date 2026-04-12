#!/usr/bin/env python3
"""HTTP server exposing buzzer state as JSON.

Run on the Raspberry Pi where buzzers are plugged in.
Serves two endpoints:

    GET  /          → {"buzzers": [1, 2], "ranking": [2, 1]}
    POST /reset     → {"ok": true}

Usage:
    python3 buzzer_server.py [--host 0.0.0.0] [--port 8888]
"""

import argparse
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from buzzer import BuzzerController, find_buzzers


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class BuzzerHandler(BaseHTTPRequestHandler):
    """Minimal JSON API for buzzer state."""

    def do_GET(self):
        if self.path.rstrip("/") == "":
            ctrl = self.server.buzzer_ctrl
            body = json.dumps({
                "buzzers": self.server.buzzer_nums,
                "ranking": ctrl.get_ranking(),
            })
            self._respond(200, body)
        else:
            self._respond(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path.rstrip("/") == "/reset":
            self.server.buzzer_ctrl.reset()
            self._respond(200, json.dumps({"ok": True}))
        else:
            self._respond(404, json.dumps({"error": "not found"}))

    def _respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        # Keep logs quiet — one-liner per request
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Buzzer HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8888)
    args = parser.parse_args()

    buzzers = find_buzzers()
    if not buzzers:
        print("No buzzers found. Are they plugged in?")
        return

    print(f"Found {len(buzzers)} buzzer(s):")
    for num, dev in buzzers:
        print(f"  Buzzer {num}: {dev.phys}")

    ctrl = BuzzerController(buzzers)
    ctrl.start()

    server = ReusableThreadingHTTPServer((args.host, args.port), BuzzerHandler)
    server.buzzer_ctrl = ctrl
    server.buzzer_nums = [num for num, _ in buzzers]

    print(f"\nServing on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        ctrl.stop()
        server.server_close()


if __name__ == "__main__":
    main()
