"""Remote buzzer controller that polls the RPi HTTP server.

Drop-in replacement for BuzzerController — same public interface
(get_ranking, reset, start, stop) but fetches state over HTTP.
"""

import json
import urllib.request
import urllib.error


class RemoteBuzzerController:
    """Polls a remote buzzer_server.py instance for ranking data."""

    def __init__(self, base_url):
        # Normalize: strip trailing slash
        self._base_url = base_url.rstrip("/")
        self._buzzers = []

    def start(self):
        """Fetch the initial buzzer list from the server."""
        data = self._get()
        if data is not None:
            self._buzzers = data.get("buzzers", [])

    def stop(self):
        """No-op — nothing to clean up on the client side."""
        pass

    def reset(self):
        """Tell the remote server to reset its ranking."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/reset", method="POST",
                data=b"", headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2):
                pass
        except (urllib.error.URLError, OSError):
            pass  # best-effort; next poll will pick up current state

    def get_ranking(self):
        """Fetch the current ranking from the remote server."""
        data = self._get()
        if data is not None:
            return data.get("ranking", [])
        return []

    def get_buzzers(self):
        """Return the buzzer numbers discovered at start()."""
        return list(self._buzzers)

    def _get(self):
        """GET / and parse JSON. Returns dict or None on failure."""
        try:
            with urllib.request.urlopen(self._base_url + "/", timeout=2) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
            return None
