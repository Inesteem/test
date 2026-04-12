"""Thread-safe game state shared between the UI and the HTTP server."""

import copy
import threading


class GameState:
    """Thread-safe dict-like store for current game state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "phase": "idle",
            "active_team": None,
            "question_num": 0,
            "question_total": 0,
            "question_text": "",
            "choices": {},
            "time_remaining": None,
            "answer_timeout": 30,
            "led_mode": "off",
            "scores": {},
            "teams": {},
            "registered_clients": {},
            "team_configs": {},
            "claimed_colors": [],
        }

    def update(self, **kwargs):
        with self._lock:
            self._state.update(kwargs)

    def snapshot(self):
        """Return a deep copy of the current state.

        Deep copy (not dict()) because several values — scores, teams,
        choices — are themselves dicts. A shallow copy would let callers
        accidentally mutate the underlying storage.
        """
        with self._lock:
            return copy.deepcopy(self._state)
