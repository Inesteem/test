"""WebDisplay — implements the Display protocol using Server-Sent Events.

State is pushed to connected browsers via SSE; commands arrive via HTTP POST.
Runs in the same process as the game engine (no extra process needed).
"""

import json
import queue
import threading
import time


class WebDisplay:
    """Display implementation that pushes state via SSE and reads commands via HTTP POST."""

    def __init__(self):
        self._command_queue = queue.Queue()
        self._current_screen = {}  # latest screen state dict
        self._screen_lock = threading.Lock()
        self._sse_clients = []  # list of queues, one per SSE connection
        self._sse_lock = threading.Lock()

    # ── SSE infrastructure ──

    def add_sse_client(self):
        """Register a new SSE client. Returns a queue that yields screen state dicts."""
        q = queue.Queue()
        with self._sse_lock:
            self._sse_clients.append(q)
        # Send current state immediately on connect
        with self._screen_lock:
            if self._current_screen:
                q.put(dict(self._current_screen))
        return q

    def remove_sse_client(self, q):
        with self._sse_lock:
            self._sse_clients = [c for c in self._sse_clients if c is not q]

    def _push(self, screen_data):
        """Push a screen state update to all SSE clients."""
        with self._screen_lock:
            self._current_screen = screen_data
        with self._sse_lock:
            for q in self._sse_clients:
                try:
                    q.put_nowait(dict(screen_data))
                except queue.Full:
                    pass  # slow client, skip

    def push_command(self, cmd):
        """Called by the HTTP handler when POST /gm/command arrives."""
        self._command_queue.put(cmd)

    # ── Display protocol implementation ──

    def draw_question(self, q, question_num, total, *, status_line="",
                      ranking_line="", elapsed=None, timeout=None,
                      is_final=False, fire_frame=0, ripple_frame=-1):
        self._push({
            "screen": "question",
            "question": q["question"],
            "choices": q.get("choices", {}),
            "answer": q.get("answer", ""),
            "question_num": question_num,
            "total": total,
            "status_line": status_line,
            "ranking_line": ranking_line,
            "elapsed": elapsed,
            "timeout": timeout,
            "is_final": is_final,
            "fire_frame": fire_frame,
            "ripple_frame": ripple_frame,
        })

    def draw_feedback(self, correct, team_name, *, question_text="",
                      correct_answer="", insult=""):
        self._push({
            "screen": "feedback",
            "correct": correct,
            "team_name": team_name,
            "question_text": question_text,
            "correct_answer": correct_answer,
            "insult": insult,
        })

    def draw_continue_prompt(self, text="Press Enter to continue"):
        # Overlay on current screen — send a delta-style update that the
        # browser merges with the existing rendered screen.
        with self._screen_lock:
            updated = dict(self._current_screen)
        updated["continue_prompt"] = text
        self._push(updated)

    def draw_answer_reveal(self, q, *, title="NOBODY GOT IT!", insult=""):
        self._push({
            "screen": "answer_reveal",
            "title": title,
            "question": q["question"],
            "answer": q.get("answer", ""),
            "choices": q.get("choices", {}),
            "insult": insult,
        })

    def draw_timeout(self, team_name, *, insult=""):
        self._push({
            "screen": "timeout",
            "team_name": team_name,
            "insult": insult,
        })

    def draw_scores(self, scores, team_config, *, final=False):
        # Normalise integer keys to strings for JSON
        self._push({
            "screen": "scores",
            "scores": {str(k): v for k, v in scores.items()},
            "team_config": {str(k): v for k, v in team_config.items()},
            "final": final,
        })

    def animate_falling_text(self, text, style, duration=1.5):
        self._push({
            "screen": "falling_text",
            "text": text,
            "style": style,
            "duration": duration,
        })
        # Block for the animation duration so the caller's timing assumptions hold
        time.sleep(duration)

    def draw_ready(self, team_config):
        self._push({
            "screen": "ready",
            "team_config": {str(k): v for k, v in team_config.items()},
        })

    def draw_waiting(self, title, subtitle, items, status):
        self._push({
            "screen": "waiting",
            "title": title,
            "subtitle": subtitle,
            "items": [{"label": label, "done": done} for label, done in items],
            "status": status,
        })

    def draw_buzzer_assign(self, current_name, current_color, assigned, team_config):
        self._push({
            "screen": "buzzer_assign",
            "current_name": current_name,
            "current_color": current_color,
            "assigned": {str(k): v for k, v in assigned.items()},
            "team_config": {str(k): v for k, v in team_config.items()},
        })

    def draw_error(self, message, detail=""):
        self._push({
            "screen": "error",
            "message": message,
            "detail": detail,
        })

    # ── Input ──

    def get_command(self, timeout=0):
        if timeout == 0:
            try:
                return self._command_queue.get_nowait()
            except queue.Empty:
                return None
        else:
            try:
                return self._command_queue.get(timeout=timeout)
            except queue.Empty:
                return None

    def wait_for_key(self):
        return self._command_queue.get()  # blocks forever

    def flush_input(self):
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
            except queue.Empty:
                break
