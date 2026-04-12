"""Tests for quiz/feedback.py — feedback, reveal, and scoreboard screens.

All rendering is mocked via a FakeDisplay that records draw calls without
touching curses. AI and sound effects are patched out.
"""

from unittest.mock import MagicMock, patch

import pytest

from quiz.feedback import (
    _feedback_event,
    _score_summary,
    show_answer_reveal,
    show_feedback,
    show_nobody_reveal,
    show_scores,
    show_timeout_screen,
)
from quiz.game_state import GameState


# ---------------------------------------------------------------------------
# Test fakes
# ---------------------------------------------------------------------------

class FakeDisplay:
    """Minimal Display implementation that records calls without rendering."""

    def __init__(self, command_sequence=()):
        # Commands to return from get_command / wait_for_key, in order.
        self._commands = list(command_sequence)
        self.draw_feedback_calls = []
        self.draw_answer_reveal_calls = []
        self.draw_timeout_calls = []
        self.draw_scores_calls = []
        self.draw_continue_prompt_calls = []
        self.animate_falling_text_calls = []
        self.wait_for_key_count = 0
        self.flush_input_count = 0
        self.get_command_calls = []

    # ── Rendering ──

    def draw_question(self, *a, **kw): pass

    def draw_feedback(self, correct, team_name, *, question_text="",
                      correct_answer="", insult=""):
        self.draw_feedback_calls.append(dict(
            correct=correct, team_name=team_name,
            question_text=question_text, correct_answer=correct_answer,
            insult=insult,
        ))

    def draw_continue_prompt(self, text="Press Enter to continue"):
        self.draw_continue_prompt_calls.append(text)

    def draw_answer_reveal(self, q, *, title="NOBODY GOT IT!", insult=""):
        self.draw_answer_reveal_calls.append(dict(q=q, title=title, insult=insult))

    def draw_timeout(self, team_name, *, insult=""):
        self.draw_timeout_calls.append(dict(team_name=team_name, insult=insult))

    def draw_scores(self, scores, team_config, *, final=False):
        self.draw_scores_calls.append(dict(scores=scores, team_config=team_config,
                                           final=final))

    def animate_falling_text(self, text, style, duration=1.5):
        self.animate_falling_text_calls.append(dict(text=text, style=style,
                                                    duration=duration))

    def draw_ready(self, team_config): pass
    def draw_waiting(self, *a, **kw): pass
    def draw_buzzer_assign(self, *a, **kw): pass
    def draw_error(self, *a, **kw): pass

    # ── Input ──

    def get_command(self, timeout=0):
        self.get_command_calls.append(timeout)
        if self._commands:
            return self._commands.pop(0)
        return None

    def wait_for_key(self):
        self.wait_for_key_count += 1
        if self._commands:
            return self._commands.pop(0)
        return "enter"

    def flush_input(self):
        self.flush_input_count += 1

    # ── Helper for tests that check rendered text ──

    def all_text(self):
        """Collect all text passed to draw calls as a single string."""
        parts = []
        for c in self.draw_feedback_calls:
            parts += [c["team_name"], c["question_text"],
                      c["correct_answer"], c["insult"]]
        for c in self.draw_answer_reveal_calls:
            parts += [c["title"], c["insult"]]
        for c in self.draw_timeout_calls:
            parts += [c["team_name"], c["insult"]]
        for c in self.animate_falling_text_calls:
            parts.append(c["text"])
        return " ".join(parts)


@pytest.fixture
def fake_display():
    return FakeDisplay(command_sequence=["enter"])


@pytest.fixture
def no_sleep():
    """Patch sleep and monotonic so time doesn't advance during tests."""
    t = [0.0]

    def fake_monotonic():
        t[0] += 0.01
        return t[0]

    with patch("quiz.feedback.time.sleep"), \
            patch("quiz.feedback.time.monotonic", side_effect=fake_monotonic):
        yield


@pytest.fixture
def mock_effects():
    """Mock the LED and sound effect helpers so they don't call hardware."""
    with patch("quiz.feedback.leds_correct"), \
            patch("quiz.feedback.leds_wrong"), \
            patch("quiz.feedback.leds_times_up"):
        yield


@pytest.fixture
def team_config():
    return {
        1: {"name": "Foxes", "color": "#0066ff", "color_name": "Blue"},
        2: {"name": "Hawks", "color": "#ffcc00", "color_name": "Yellow"},
    }


@pytest.fixture
def sample_question():
    return {
        "question": "What is 2+2?",
        "choices": {"a": "3", "b": "5", "c": "4"},
        "answer": "c",
    }


# ---------------------------------------------------------------------------
# _feedback_event
# ---------------------------------------------------------------------------

class TestFeedbackEvent:

    def test_fast_correct_is_correct_fast(self):
        assert _feedback_event(True, 1.5) == "correct_fast"

    def test_exact_3s_is_slow(self):
        # 3.0 is NOT < 3.0, so it counts as slow
        assert _feedback_event(True, 3.0) == "correct_slow"

    def test_slow_correct_is_correct_slow(self):
        assert _feedback_event(True, 10.0) == "correct_slow"

    def test_correct_with_none_time_is_slow(self):
        assert _feedback_event(True, None) == "correct_slow"

    def test_wrong_always_wrong(self):
        assert _feedback_event(False, 1.0) == "wrong"
        assert _feedback_event(False, 30.0) == "wrong"
        assert _feedback_event(False, None) == "wrong"


# ---------------------------------------------------------------------------
# _score_summary
# ---------------------------------------------------------------------------

class TestScoreSummary:

    def test_maps_buzzer_to_team_name(self, team_config):
        scores = {1: 3, 2: -1}
        result = _score_summary(scores, team_config)
        assert result == {"Foxes": 3, "Hawks": -1}

    def test_empty_scores(self, team_config):
        assert _score_summary({}, team_config) == {}

    def test_none_scores(self, team_config):
        assert _score_summary(None, team_config) == {}

    def test_skips_unknown_buzzer_nums(self, team_config):
        scores = {1: 3, 99: 5}  # 99 not in team_config
        result = _score_summary(scores, team_config)
        assert result == {"Foxes": 3}


# ---------------------------------------------------------------------------
# show_feedback — insult fallback chain
# ---------------------------------------------------------------------------

class TestShowFeedback:

    def _call(self, display, correct, team_config, answer_time=2.0,
              insult_pack=None, insult_ai_obj=None, game_state=None):
        snd = MagicMock()
        snd.correct.return_value = None
        snd.wrong.return_value = None
        leds = MagicMock()
        show_feedback(
            display, leds, snd, correct=correct, name="Foxes",
            team_config=team_config, buzzer_num=1,
            answer_time=answer_time, insult_pack=insult_pack,
            insult_ai_obj=insult_ai_obj, question_text="Q?",
            given_answer="A", correct_answer="C",
            scores={1: 0, 2: 0}, game_state=game_state,
        )

    def test_no_insult_mode_calls_draw_feedback(self, fake_display, team_config,
                                                no_sleep, mock_effects):
        self._call(fake_display, correct=True, team_config=team_config)
        assert len(fake_display.draw_feedback_calls) >= 1

    def test_static_pack_wrong_answer_insult_drawn(self, team_config, no_sleep,
                                                   mock_effects):
        display = FakeDisplay()
        pack = {
            "wrong": ["Terrible."],
            "correct_fast": [],
            "correct_slow": [],
            "timeout": [],
            "nobody": [],
        }
        self._call(display, correct=False, team_config=team_config, insult_pack=pack)
        assert "Terrible" in display.all_text()

    def test_ai_mode_gets_result(self, team_config, mock_effects, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        ai = MagicMock()
        ai.get_result.return_value = "AI INSULT"
        self._call(display, correct=False, team_config=team_config, insult_ai_obj=ai)
        assert "AI INSULT" in display.all_text()
        ai.get_result.assert_called_once()
        # generate_async must be called BEFORE get_result, with the event name
        ai.generate_async.assert_called_once()
        first_arg = ai.generate_async.call_args[0][0]
        assert first_arg == "wrong"

    def test_ai_mode_shows_continue_prompt(self, team_config, mock_effects, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        ai = MagicMock()
        ai.get_result.return_value = "Some insult"
        self._call(display, correct=False, team_config=team_config, insult_ai_obj=ai)
        assert len(display.draw_continue_prompt_calls) == 1
        assert display.wait_for_key_count == 1

    def test_non_ai_mode_uses_get_command_timeout(self, team_config, mock_effects, no_sleep):
        display = FakeDisplay()
        self._call(display, correct=True, team_config=team_config)
        # Non-AI mode: get_command(timeout=5.0), not wait_for_key
        assert any(t == 5.0 for t in display.get_command_calls)
        assert display.wait_for_key_count == 0

    def test_ai_timeout_falls_back_to_pack(self, team_config, mock_effects, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        ai = MagicMock()
        ai.get_result.return_value = ""  # simulated timeout
        pack = {
            "wrong": ["Static fallback."],
            "correct_fast": [], "correct_slow": [], "timeout": [], "nobody": [],
        }
        self._call(display, correct=False, team_config=team_config,
                   insult_ai_obj=ai, insult_pack=pack)
        assert "Static fallback" in display.all_text()

    def test_ai_timeout_no_pack_falls_back_to_hardcoded(self, team_config, mock_effects, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        ai = MagicMock()
        ai.get_result.return_value = ""
        self._call(display, correct=False, team_config=team_config, insult_ai_obj=ai)
        # Should show one of the LAME_TEXTS
        from quiz.constants import LAME_TEXTS
        assert any(t in display.all_text() for t in LAME_TEXTS)

    def test_updates_game_state_to_feedback_phase(self, fake_display, team_config,
                                                  no_sleep, mock_effects):
        gs = GameState()
        self._call(fake_display, correct=True, team_config=team_config, game_state=gs)
        assert gs.snapshot()["phase"] == "feedback"
        assert gs.snapshot()["active_team"] is None

    def test_suspense_handle_none_does_not_crash(self, team_config, mock_effects, no_sleep):
        """Sound.suspense() may return None; stop() must be guarded."""
        display = FakeDisplay(command_sequence=["enter"])
        snd = MagicMock()
        snd.suspense.return_value = None  # simulate no handle
        snd.correct.return_value = None
        snd.wrong.return_value = None
        leds = MagicMock()
        ai = MagicMock()
        ai.get_result.return_value = "some insult"

        # Should not raise AttributeError
        show_feedback(
            display, leds, snd, correct=True, name="Foxes",
            team_config=team_config, buzzer_num=1,
            answer_time=1.0, insult_ai_obj=ai,
            question_text="Q?", scores={1: 0, 2: 0},
        )

    def test_draw_feedback_called_with_question_and_answer(self, team_config,
                                                           no_sleep, mock_effects):
        """question_text and correct_answer are always forwarded to draw_feedback."""
        display = FakeDisplay()
        self._call(display, correct=True, team_config=team_config)
        assert any(c["question_text"] == "Q?" for c in display.draw_feedback_calls)
        assert any(c["correct_answer"] == "C" for c in display.draw_feedback_calls)


# ---------------------------------------------------------------------------
# show_answer_reveal
# ---------------------------------------------------------------------------

class TestShowAnswerReveal:

    def test_reveal_without_insult_sleeps(self, sample_question, no_sleep):
        display = FakeDisplay()
        leds = MagicMock()
        snd = MagicMock()

        show_answer_reveal(display, leds, snd, sample_question, title="TEST", insult="")
        assert len(display.draw_answer_reveal_calls) == 1
        call = display.draw_answer_reveal_calls[0]
        assert call["title"] == "TEST"
        assert call["insult"] == ""
        snd.dramatic_sting.assert_called_once()

    def test_reveal_with_insult_waits_for_key(self, sample_question, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()

        show_answer_reveal(display, leds, snd, sample_question,
                           title="NOBODY GOT IT!", insult="Embarrassing")
        call = display.draw_answer_reveal_calls[0]
        assert call["insult"] == "Embarrassing"
        assert display.flush_input_count == 1
        assert display.wait_for_key_count == 1

    def test_reveal_without_insult_does_not_wait_for_key(self, sample_question, no_sleep):
        display = FakeDisplay()
        leds = MagicMock()
        snd = MagicMock()

        show_answer_reveal(display, leds, snd, sample_question, title="TEST", insult="")
        assert display.wait_for_key_count == 0
        assert display.flush_input_count == 0


# ---------------------------------------------------------------------------
# show_timeout_screen
# ---------------------------------------------------------------------------

class TestShowTimeoutScreen:

    def test_timeout_with_pack(self, sample_question, team_config, no_sleep):
        display = FakeDisplay()
        leds = MagicMock()
        snd = MagicMock()
        pack = {
            "timeout": ["Too slow!"],
            "correct_fast": [], "correct_slow": [], "wrong": [], "nobody": [],
        }
        with patch("quiz.feedback.leds_times_up"):
            show_timeout_screen(
                display, leds, snd, sample_question, name="Foxes",
                current_buzzer=1, team_config=team_config,
                insult_pack=pack, insult_ai_obj=None, scores={1: 0, 2: 0},
            )
        assert any(c["team_name"] == "Foxes" for c in display.draw_timeout_calls)
        assert "Too slow" in display.all_text()

    def test_timeout_initial_draw_has_no_insult(self, sample_question, team_config, no_sleep):
        """First draw_timeout call (before resolution) should have empty insult."""
        display = FakeDisplay()
        leds = MagicMock()
        snd = MagicMock()
        pack = {"timeout": ["Late!"], "correct_fast": [], "correct_slow": [],
                "wrong": [], "nobody": []}
        with patch("quiz.feedback.leds_times_up"):
            show_timeout_screen(
                display, leds, snd, sample_question, name="Foxes",
                current_buzzer=1, team_config=team_config,
                insult_pack=pack, insult_ai_obj=None, scores={1: 0, 2: 0},
            )
        first_call = display.draw_timeout_calls[0]
        assert first_call["insult"] == ""


# ---------------------------------------------------------------------------
# show_nobody_reveal
# ---------------------------------------------------------------------------

class TestShowNobodyReveal:

    def test_nobody_with_pack(self, sample_question, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        pack = {
            "nobody": ["Sad."],
            "correct_fast": [], "correct_slow": [], "wrong": [], "timeout": [],
        }
        show_nobody_reveal(
            display, leds, snd, sample_question,
            insult_pack=pack, insult_ai_obj=None,
            scores={1: 0, 2: 0}, team_config=team_config,
        )
        assert any(c["title"] == "NOBODY GOT IT!" for c in display.draw_answer_reveal_calls)
        assert len(display.animate_falling_text_calls) == 1
        assert display.animate_falling_text_calls[0]["style"] == "wrong"

    def test_nobody_falling_text_uses_resolved_insult(self, sample_question,
                                                       team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        pack = {"nobody": ["Shameful."], "correct_fast": [], "correct_slow": [],
                "wrong": [], "timeout": []}
        show_nobody_reveal(
            display, leds, snd, sample_question,
            insult_pack=pack, insult_ai_obj=None,
            scores={1: 0, 2: 0}, team_config=team_config,
        )
        ft = display.animate_falling_text_calls[0]
        assert ft["text"] == "Shameful."
        assert ft["duration"] == 2.0


# ---------------------------------------------------------------------------
# show_scores
# ---------------------------------------------------------------------------

class TestShowScores:

    def test_mid_game_scores_calls_draw_scores(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: 3, 2: -1}

        show_scores(display, leds, snd, scores, team_config, final=False)
        assert len(display.draw_scores_calls) == 1
        call = display.draw_scores_calls[0]
        assert call["final"] is False
        assert call["scores"] == scores

    def test_final_scores_passes_final_flag(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: 5, 2: 2}

        show_scores(display, leds, snd, scores, team_config, final=True)
        call = display.draw_scores_calls[0]
        assert call["final"] is True

    def test_final_scores_strobe_winner_led(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: 5, 2: 2}

        show_scores(display, leds, snd, scores, team_config, final=True)
        leds.strobe.assert_called_once()
        leds.breathe.assert_called()

    def test_mid_game_breathes_leader_color(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: 3, 2: -1}

        show_scores(display, leds, snd, scores, team_config, final=False)
        leds.breathe.assert_called_once()
        leds.strobe.assert_not_called()

    def test_waits_for_key(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()

        show_scores(display, leds, snd, {1: 3, 2: -1}, team_config, final=False)
        assert display.wait_for_key_count == 1

    def test_updates_game_state_to_scores(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        gs = GameState()

        show_scores(display, leds, snd, {1: 3, 2: 1}, team_config,
                    final=False, game_state=gs)
        assert gs.snapshot()["phase"] == "scores"

    def test_final_updates_game_state_to_final_scores(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        gs = GameState()

        show_scores(display, leds, snd, {1: 5, 2: 2}, team_config,
                    final=True, game_state=gs)
        assert gs.snapshot()["phase"] == "final_scores"

    def test_empty_scores_does_not_crash(self, team_config, no_sleep):
        display = FakeDisplay(command_sequence=["enter"])
        leds = MagicMock()
        snd = MagicMock()
        show_scores(display, leds, snd, {}, {}, final=False)
