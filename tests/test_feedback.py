"""Tests for quiz/feedback.py — feedback, reveal, and scoreboard screens.

All curses IO is mocked via a FakeWin that records calls without drawing.
AI and sound effects are patched out.
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

class FakeWin:
    """Minimal curses window that doesn't actually render anything."""

    def __init__(self, key_sequence=()):
        self._keys = list(key_sequence)
        self.nodelay_mode = False
        self.addstr_calls = []
        self.refresh_count = 0
        self.clear_count = 0

    def getch(self):
        if self._keys:
            return self._keys.pop(0)
        return -1

    def nodelay(self, mode):
        self.nodelay_mode = mode

    def getmaxyx(self):
        return (30, 100)

    def addstr(self, *args, **kwargs):
        self.addstr_calls.append((args, kwargs))

    def clear(self):
        self.clear_count += 1

    def refresh(self):
        self.refresh_count += 1

    def bkgd(self, *a, **k): pass
    def chgat(self, *a, **k): pass
    def move(self, *a, **k): pass


@pytest.fixture(autouse=True)
def stub_curses():
    """Patch curses.color_pair and related calls that need initscr()."""
    # color_pair returns integer-like values; A_BOLD etc. are already ints
    with patch("quiz.feedback.curses.color_pair", return_value=0), \
            patch("quiz.feedback.curses.flushinp"), \
            patch("quiz.feedback.curses.A_BOLD", 0), \
            patch("quiz.feedback.curses.A_DIM", 0), \
            patch("quiz.feedback.curses.A_REVERSE", 0), \
            patch("quiz.drawing.curses.color_pair", return_value=0), \
            patch("quiz.drawing.curses.A_BOLD", 0), \
            patch("quiz.drawing.curses.A_DIM", 0), \
            patch("quiz.drawing.curses.A_REVERSE", 0), \
            patch("quiz.drawing.curses.error", Exception):
        yield


@pytest.fixture
def fake_win():
    return FakeWin(key_sequence=[10])  # Enter key, so feedback advance doesn't hang


@pytest.fixture
def no_sleep():
    """Patch both sleep and monotonic so test time doesn't advance."""
    # monotonic gets patched so the 5s auto-advance deadline trips immediately
    # for any test that forgets to seed an Enter key.
    t = [0.0]

    def fake_monotonic():
        t[0] += 0.01
        return t[0]

    with patch("quiz.feedback.time.sleep"), \
            patch("quiz.feedback.time.monotonic", side_effect=fake_monotonic):
        yield


@pytest.fixture
def mock_effects():
    """Mock the LED and sound effect helpers so they don't sleep or call hardware."""
    with patch("quiz.feedback.leds_correct"), \
            patch("quiz.feedback.leds_wrong"), \
            patch("quiz.feedback.leds_times_up"), \
            patch("quiz.feedback.animate_falling_text"):
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

    def _call(self, win, correct, team_config, answer_time=2.0,
              insult_pack=None, insult_ai_obj=None, game_state=None):
        snd = MagicMock()
        snd.correct.return_value = None
        snd.wrong.return_value = None
        leds = MagicMock()
        show_feedback(
            win, leds, snd, correct=correct, name="Foxes",
            team_config=team_config, buzzer_num=1,
            answer_time=answer_time, insult_pack=insult_pack,
            insult_ai_obj=insult_ai_obj, question_text="Q?",
            given_answer="A", correct_answer="C",
            scores={1: 0, 2: 0}, game_state=game_state,
        )

    def test_no_insult_mode_no_insult_drawn(self, fake_win, team_config, no_sleep, mock_effects):
        self._call(fake_win, correct=True, team_config=team_config)
        # Should not call any AI stuff — no exceptions expected
        assert fake_win.refresh_count > 0

    def test_static_pack_wrong_answer(self, fake_win, team_config, no_sleep, mock_effects):
        pack = {
            "wrong": ["Terrible."],
            "correct_fast": [],
            "correct_slow": [],
            "timeout": [],
            "nobody": [],
        }
        self._call(fake_win, correct=False, team_config=team_config, insult_pack=pack)
        # The insult text should appear in at least one addstr call
        all_text = " ".join(str(c) for c in fake_win.addstr_calls)
        assert "Terrible" in all_text

    def test_ai_mode_gets_result(self, team_config, mock_effects, no_sleep):
        win = FakeWin(key_sequence=[10])  # Enter to advance
        ai = MagicMock()
        ai.get_result.return_value = "AI INSULT"
        self._call(win, correct=False, team_config=team_config, insult_ai_obj=ai)
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "AI INSULT" in all_text
        ai.get_result.assert_called_once()
        # generate_async must be called BEFORE get_result, with the event name
        ai.generate_async.assert_called_once()
        first_arg = ai.generate_async.call_args[0][0]
        assert first_arg == "wrong"

    def test_ai_timeout_falls_back_to_pack(self, team_config, mock_effects, no_sleep):
        win = FakeWin(key_sequence=[10])
        ai = MagicMock()
        ai.get_result.return_value = ""  # simulated timeout
        pack = {
            "wrong": ["Static fallback."],
            "correct_fast": [], "correct_slow": [], "timeout": [], "nobody": [],
        }
        self._call(win, correct=False, team_config=team_config,
                   insult_ai_obj=ai, insult_pack=pack)
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "Static fallback" in all_text

    def test_ai_timeout_no_pack_falls_back_to_hardcoded(self, team_config, mock_effects, no_sleep):
        win = FakeWin(key_sequence=[10])
        ai = MagicMock()
        ai.get_result.return_value = ""
        self._call(win, correct=False, team_config=team_config, insult_ai_obj=ai)
        # Should show one of the LAME_TEXTS
        all_text = " ".join(str(c) for c in win.addstr_calls)
        from quiz.constants import LAME_TEXTS
        assert any(t in all_text for t in LAME_TEXTS)

    def test_updates_game_state_to_feedback_phase(self, fake_win, team_config, no_sleep, mock_effects):
        gs = GameState()
        self._call(fake_win, correct=True, team_config=team_config, game_state=gs)
        assert gs.snapshot()["phase"] == "feedback"
        assert gs.snapshot()["active_team"] is None

    def test_suspense_handle_none_does_not_crash(self, team_config, mock_effects, no_sleep):
        """HIGH #2: Sound.suspense() may return None; stop() must be guarded."""
        win = FakeWin(key_sequence=[10])
        snd = MagicMock()
        snd.suspense.return_value = None  # simulate no handle
        snd.correct.return_value = None
        snd.wrong.return_value = None
        leds = MagicMock()
        ai = MagicMock()
        ai.get_result.return_value = "some insult"

        # Should not raise AttributeError
        show_feedback(
            win, leds, snd, correct=True, name="Foxes",
            team_config=team_config, buzzer_num=1,
            answer_time=1.0, insult_ai_obj=ai,
            question_text="Q?", scores={1: 0, 2: 0},
        )


# ---------------------------------------------------------------------------
# show_answer_reveal
# ---------------------------------------------------------------------------

class TestShowAnswerReveal:

    def test_reveal_without_insult_sleeps(self, sample_question, team_config, no_sleep):
        win = FakeWin()
        leds = MagicMock()
        snd = MagicMock()

        show_answer_reveal(win, leds, snd, sample_question, title="TEST", insult="")
        # Question text should appear
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "TEST" in all_text
        # Correct answer should appear
        assert "4" in all_text  # the answer to 2+2
        snd.dramatic_sting.assert_called_once()

    def test_reveal_with_insult_waits_for_key(self, sample_question, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])  # Enter
        leds = MagicMock()
        snd = MagicMock()

        show_answer_reveal(win, leds, snd, sample_question,
                           title="NOBODY GOT IT!", insult="Embarrassing")
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "Embarrassing" in all_text


# ---------------------------------------------------------------------------
# show_timeout_screen
# ---------------------------------------------------------------------------

class TestShowTimeoutScreen:

    def test_timeout_with_pack(self, sample_question, team_config, no_sleep):
        win = FakeWin()
        leds = MagicMock()
        snd = MagicMock()
        pack = {
            "timeout": ["Too slow!"],
            "correct_fast": [], "correct_slow": [], "wrong": [], "nobody": [],
        }
        with patch("quiz.feedback.leds_times_up"):
            show_timeout_screen(
                win, leds, snd, sample_question, name="Foxes",
                current_buzzer=1, team_config=team_config,
                insult_pack=pack, insult_ai_obj=None, scores={1: 0, 2: 0},
            )
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "TIME" in all_text.upper()
        assert "Too slow" in all_text


# ---------------------------------------------------------------------------
# show_nobody_reveal
# ---------------------------------------------------------------------------

class TestShowNobodyReveal:

    def test_nobody_with_pack(self, sample_question, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        pack = {
            "nobody": ["Sad."],
            "correct_fast": [], "correct_slow": [], "wrong": [], "timeout": [],
        }
        with patch("quiz.feedback.animate_falling_text"):
            show_nobody_reveal(
                win, leds, snd, sample_question,
                insult_pack=pack, insult_ai_obj=None,
                scores={1: 0, 2: 0}, team_config=team_config,
            )
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "NOBODY GOT IT" in all_text.upper()


# ---------------------------------------------------------------------------
# show_scores
# ---------------------------------------------------------------------------

class TestShowScores:

    def test_mid_game_scores_wait_for_key(self, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: 3, 2: -1}

        show_scores(win, leds, snd, scores, team_config, final=False)
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "Foxes" in all_text
        assert "Hawks" in all_text

    def test_final_scores_shows_winner(self, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: 5, 2: 2}

        show_scores(win, leds, snd, scores, team_config, final=True)
        all_text = " ".join(str(c) for c in win.addstr_calls)
        assert "FINAL" in all_text
        assert "Foxes wins" in all_text

    def test_negative_scores_render(self, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        scores = {1: -3, 2: -1}

        show_scores(win, leds, snd, scores, team_config, final=False)
        all_text = " ".join(str(c) for c in win.addstr_calls)
        # Negative scores rendered with explicit minus sign
        assert "-3" in all_text
        assert "-1" in all_text

    def test_updates_game_state_to_scores(self, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        gs = GameState()

        show_scores(win, leds, snd, {1: 3, 2: 1}, team_config,
                    final=False, game_state=gs)
        assert gs.snapshot()["phase"] == "scores"

    def test_final_updates_game_state_to_final_scores(self, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        gs = GameState()

        show_scores(win, leds, snd, {1: 5, 2: 2}, team_config,
                    final=True, game_state=gs)
        assert gs.snapshot()["phase"] == "final_scores"

    def test_empty_scores_does_not_crash(self, team_config, no_sleep):
        win = FakeWin(key_sequence=[10])
        leds = MagicMock()
        snd = MagicMock()
        show_scores(win, leds, snd, {}, {}, final=False)
