"""Tests for quiz/web_display.py — WebDisplay protocol implementation."""

import queue
import threading
import time

import pytest

from quiz.web_display import WebDisplay


# ── Helpers ────────────────────────────────────────────────────────────────────

SAMPLE_Q = {
    "question": "What is 2+2?",
    "choices": {"a": "3", "b": "4", "c": "5"},
    "answer": "b",
}

SAMPLE_TC = {
    1: {"name": "Red Team", "color": "#ff0000", "color_name": "Red"},
    2: {"name": "Blue Team", "color": "#0000ff", "color_name": "Blue"},
}


# ── WebDisplay.push / SSE client ───────────────────────────────────────────────

class TestSSEClients:

    def test_add_client_returns_queue(self):
        wd = WebDisplay()
        q = wd.add_sse_client()
        assert isinstance(q, queue.Queue)

    def test_new_client_receives_current_screen_immediately(self):
        wd = WebDisplay()
        wd.draw_question(SAMPLE_Q, 1, 5)
        q = wd.add_sse_client()
        data = q.get_nowait()
        assert data["screen"] == "question"
        assert data["question"] == SAMPLE_Q["question"]

    def test_new_client_gets_nothing_when_no_screen_yet(self):
        wd = WebDisplay()
        q = wd.add_sse_client()
        assert q.empty()

    def test_push_delivers_to_all_clients(self):
        wd = WebDisplay()
        q1 = wd.add_sse_client()
        q2 = wd.add_sse_client()
        wd.draw_scores({1: 3, 2: 1}, SAMPLE_TC)
        assert q1.get_nowait()["screen"] == "scores"
        assert q2.get_nowait()["screen"] == "scores"

    def test_remove_client_stops_delivery(self):
        wd = WebDisplay()
        q = wd.add_sse_client()
        wd.remove_sse_client(q)
        wd.draw_timeout("Red Team")
        assert q.empty()

    def test_push_copies_dict_so_mutations_do_not_alias(self):
        wd = WebDisplay()
        q = wd.add_sse_client()
        wd.draw_question(SAMPLE_Q, 1, 5)
        payload = q.get_nowait()
        # Mutate the received copy — should not affect current_screen
        payload["question"] = "MUTATED"
        q2 = wd.add_sse_client()
        fresh = q2.get_nowait()
        assert fresh["question"] == SAMPLE_Q["question"]


# ── Draw methods push correct screen type ─────────────────────────────────────

class TestDrawMethods:

    def _drain(self, wd):
        q = wd.add_sse_client()
        return q.get_nowait()

    def test_draw_question(self):
        wd = WebDisplay()
        wd.draw_question(SAMPLE_Q, 3, 10, status_line="Buzz!", is_final=True,
                         elapsed=5.0, timeout=30.0)
        d = self._drain(wd)
        assert d["screen"] == "question"
        assert d["question_num"] == 3
        assert d["total"] == 10
        assert d["status_line"] == "Buzz!"
        assert d["is_final"] is True
        assert d["elapsed"] == 5.0
        assert d["timeout"] == 30.0
        assert d["choices"] == SAMPLE_Q["choices"]

    def test_draw_feedback_correct(self):
        wd = WebDisplay()
        wd.draw_feedback(True, "Red Team", insult="Not bad!")
        d = self._drain(wd)
        assert d["screen"] == "feedback"
        assert d["correct"] is True
        assert d["team_name"] == "Red Team"
        assert d["insult"] == "Not bad!"

    def test_draw_feedback_wrong(self):
        wd = WebDisplay()
        wd.draw_feedback(False, "Blue Team")
        d = self._drain(wd)
        assert d["screen"] == "feedback"
        assert d["correct"] is False

    def test_draw_continue_prompt_overlays_current_screen(self):
        wd = WebDisplay()
        wd.draw_feedback(True, "Red Team")
        wd.draw_continue_prompt("Press Enter to continue")
        d = self._drain(wd)
        # Should carry the continue_prompt field AND retain the screen type
        assert d["screen"] == "feedback"
        assert d["continue_prompt"] == "Press Enter to continue"

    def test_draw_answer_reveal(self):
        wd = WebDisplay()
        wd.draw_answer_reveal(SAMPLE_Q, title="SKIPPED!", insult="Oops")
        d = self._drain(wd)
        assert d["screen"] == "answer_reveal"
        assert d["title"] == "SKIPPED!"
        assert d["answer"] == "b"
        assert d["insult"] == "Oops"

    def test_draw_timeout(self):
        wd = WebDisplay()
        wd.draw_timeout("Blue Team", insult="Too slow!")
        d = self._drain(wd)
        assert d["screen"] == "timeout"
        assert d["team_name"] == "Blue Team"
        assert d["insult"] == "Too slow!"

    def test_draw_scores_serialises_keys(self):
        wd = WebDisplay()
        wd.draw_scores({1: 3, 2: -1}, SAMPLE_TC, final=True)
        d = self._drain(wd)
        assert d["screen"] == "scores"
        assert d["final"] is True
        # Integer keys must be string after serialisation
        assert "1" in d["scores"]
        assert d["scores"]["1"] == 3
        assert "1" in d["team_config"]

    def test_draw_ready(self):
        wd = WebDisplay()
        wd.draw_ready(SAMPLE_TC)
        d = self._drain(wd)
        assert d["screen"] == "ready"
        assert "1" in d["team_config"]
        assert d["team_config"]["1"]["name"] == "Red Team"

    def test_draw_waiting(self):
        wd = WebDisplay()
        items = [("Team 1: connected", True), ("Team 2: waiting", False)]
        wd.draw_waiting("WAITING", "Connect clients", items, "1/2 connected")
        d = self._drain(wd)
        assert d["screen"] == "waiting"
        assert d["title"] == "WAITING"
        assert len(d["items"]) == 2
        assert d["items"][0]["done"] is True
        assert d["items"][1]["done"] is False
        assert d["status"] == "1/2 connected"

    def test_draw_buzzer_assign(self):
        wd = WebDisplay()
        assigned = {1: {"name": "Red Team", "color": "#ff0000", "buzzer_num": 2}}
        wd.draw_buzzer_assign("Blue Team", "#0000ff", assigned, SAMPLE_TC)
        d = self._drain(wd)
        assert d["screen"] == "buzzer_assign"
        assert d["current_name"] == "Blue Team"
        assert d["current_color"] == "#0000ff"
        assert "1" in d["assigned"]

    def test_draw_error(self):
        wd = WebDisplay()
        wd.draw_error("Something went wrong", "detail here")
        d = self._drain(wd)
        assert d["screen"] == "error"
        assert d["message"] == "Something went wrong"
        assert d["detail"] == "detail here"


# ── animate_falling_text ───────────────────────────────────────────────────────

class TestAnimateFallingText:

    def test_pushes_falling_text_screen(self):
        wd = WebDisplay()
        # Run in a thread so we don't block the test for 1.5 s
        t = threading.Thread(target=wd.animate_falling_text,
                             args=("SAVAGE!", "correct", 0.05))
        t.start()
        q = wd.add_sse_client()
        # Give it a moment to push
        d = q.get(timeout=1.0)
        t.join(timeout=0.5)
        assert d["screen"] == "falling_text"
        assert d["text"] == "SAVAGE!"
        assert d["style"] == "correct"

    def test_blocks_for_duration(self):
        wd = WebDisplay()
        start = time.monotonic()
        t = threading.Thread(target=wd.animate_falling_text,
                             args=("LAME!", "wrong", 0.1))
        t.start()
        t.join(timeout=1.0)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09  # at least ~duration


# ── Input methods ──────────────────────────────────────────────────────────────

class TestInputMethods:

    def test_push_command_then_get_nowait(self):
        wd = WebDisplay()
        wd.push_command("enter")
        assert wd.get_command() == "enter"

    def test_get_command_returns_none_when_empty(self):
        wd = WebDisplay()
        assert wd.get_command() is None

    def test_get_command_with_timeout_blocks_then_returns_none(self):
        wd = WebDisplay()
        start = time.monotonic()
        result = wd.get_command(timeout=0.1)
        elapsed = time.monotonic() - start
        assert result is None
        assert elapsed >= 0.08

    def test_get_command_with_timeout_returns_command(self):
        wd = WebDisplay()

        def deliver():
            time.sleep(0.05)
            wd.push_command("space")

        threading.Thread(target=deliver, daemon=True).start()
        result = wd.get_command(timeout=1.0)
        assert result == "space"

    def test_wait_for_key_blocks_and_returns(self):
        wd = WebDisplay()
        received = []

        def waiter():
            received.append(wd.wait_for_key())

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        time.sleep(0.05)
        wd.push_command("a")
        t.join(timeout=1.0)
        assert received == ["a"]

    def test_flush_input_clears_queue(self):
        wd = WebDisplay()
        wd.push_command("a")
        wd.push_command("b")
        wd.push_command("c")
        wd.flush_input()
        assert wd.get_command() is None


# ── Thread-safety smoke test ───────────────────────────────────────────────────

class TestThreadSafety:

    def test_concurrent_pushes_and_client_add(self):
        """Many writers + a reader joining mid-stream should not deadlock or crash."""
        wd = WebDisplay()
        errors = []

        def writer():
            for i in range(20):
                try:
                    wd.draw_question(SAMPLE_Q, i, 20)
                except Exception as e:
                    errors.append(e)

        def reader():
            for _ in range(5):
                try:
                    q = wd.add_sse_client()
                    try:
                        q.get(timeout=0.2)
                    except queue.Empty:
                        pass
                    wd.remove_sse_client(q)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert errors == []
