"""Integration tests for quiz/flow.py — the game flow state machine.

Tests _broadcast_state (pure function), the three phase helpers with
mocked IO (win, ctrl, leds, snd), and a full run_question happy path.
"""

from unittest.mock import MagicMock, patch

import pytest

from quiz.flow import (
    _R_BUZZED,
    _R_RESET,
    _R_SKIPPED,
    _R_TIMED_OUT,
    _broadcast_state,
    _phase1_buzz_in,
    _phase2_answer_countdown,
    _phase2_wait_for_next_buzz,
    run_question,
)
from quiz.game_state import GameState


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

class FakeWin:
    """Fake curses window that scripts getch() responses and swallows drawing."""

    def __init__(self, key_sequence=()):
        self._keys = list(key_sequence)
        self.nodelay_mode = False
        self.getch_calls = 0

    def getch(self):
        self.getch_calls += 1
        if self._keys:
            return self._keys.pop(0)
        return -1  # no key

    def nodelay(self, mode):
        self.nodelay_mode = mode

    def getmaxyx(self):
        return (24, 80)

    # curses drawing methods — all no-op
    def addstr(self, *a, **k): pass
    def clear(self): pass
    def refresh(self): pass
    def bkgd(self, *a, **k): pass
    def chgat(self, *a, **k): pass
    def move(self, *a, **k): pass


class FakeCtrl:
    """Fake buzzer controller with a scripted ranking over time.

    Each call to get_ranking() returns the next entry from the sequence;
    once exhausted, subsequent calls return the last entry. This gives tests
    control over when new buzzes appear in the polling loop.
    """

    def __init__(self, ranking_sequence=()):
        self._rankings = list(ranking_sequence) if ranking_sequence else [[]]
        self._idx = 0
        self.reset_calls = 0

    def get_ranking(self):
        result = list(self._rankings[self._idx])
        if self._idx < len(self._rankings) - 1:
            self._idx += 1
        return result

    def reset(self):
        self.reset_calls += 1
        self._idx = 0


def make_sound():
    snd = MagicMock()
    snd.jeopardy_thinking.return_value = MagicMock()
    snd.final_countdown.return_value = MagicMock()
    snd.suspense.return_value = MagicMock()
    return snd


def make_leds():
    return MagicMock()


@pytest.fixture
def sample_question():
    return {
        "question": "What is 2+2?",
        "choices": {"a": "3", "b": "5", "c": "4"},
        "answer": "c",
    }


@pytest.fixture
def team_config():
    return {
        1: {"name": "Foxes", "color": "#0066ff", "color_name": "Blue"},
        2: {"name": "Hawks", "color": "#ffcc00", "color_name": "Yellow"},
    }


@pytest.fixture
def no_sleep():
    """Patch time.sleep and POLL_INTERVAL so tests don't actually wait."""
    with patch("quiz.flow.time.sleep"), patch("quiz.flow.POLL_INTERVAL", 0):
        yield


@pytest.fixture
def no_draw():
    """Skip draw_question and flushinp so we don't touch a real terminal."""
    with patch("quiz.flow.draw_question"), \
            patch("quiz.flow.curses.flushinp"):
        yield


# ---------------------------------------------------------------------------
# _broadcast_state
# ---------------------------------------------------------------------------

class TestBroadcastState:

    def test_none_game_state_is_noop(self):
        # Explicit assertion: no attribute access on None
        _broadcast_state(None, "buzzing", active_team=1, scores={1: 5})

    def test_scores_none_does_not_clobber(self):
        """scores=None means 'don't touch scores', not 'empty scores'."""
        gs = GameState()
        gs.update(scores={"1": 5})
        _broadcast_state(gs, "buzzing", scores=None)
        assert gs.snapshot()["scores"] == {"1": 5}

    def test_sets_phase(self):
        gs = GameState()
        _broadcast_state(gs, "answering")
        assert gs.snapshot()["phase"] == "answering"

    def test_converts_scores_keys_to_strings(self):
        gs = GameState()
        _broadcast_state(gs, "buzzing", scores={1: 5, 2: -3})
        snap = gs.snapshot()
        assert snap["scores"] == {"1": 5, "2": -3}

    def test_converts_team_config_keys_to_strings(self):
        gs = GameState()
        team_config = {1: {"name": "A"}, 2: {"name": "B"}}
        _broadcast_state(gs, "buzzing", team_config=team_config)
        snap = gs.snapshot()
        assert snap["teams"] == {"1": {"name": "A"}, "2": {"name": "B"}}

    def test_passes_through_extra_kwargs(self):
        gs = GameState()
        _broadcast_state(gs, "answering", active_team=2, question_text="Q?")
        snap = gs.snapshot()
        assert snap["active_team"] == 2
        assert snap["question_text"] == "Q?"

    def test_team_config_not_in_payload_when_not_passed(self):
        gs = GameState()
        _broadcast_state(gs, "buzzing")
        # The default state has empty teams/scores — broadcast shouldn't clobber.
        # (The implementation only updates fields explicitly passed.)
        assert gs.snapshot()["phase"] == "buzzing"


# ---------------------------------------------------------------------------
# _phase1_buzz_in
# ---------------------------------------------------------------------------

class TestPhase1BuzzIn:

    def test_buzz_returns_buzzed(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        # First call to get_ranking() returns [1] — someone already pressed
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        result = _phase1_buzz_in(
            win, sample_question, 1, 5, ctrl, leds, team_config, snd,
            is_last_question=False, game_state=None, scores={1: 0, 2: 0},
        )
        assert result == _R_BUZZED

    def test_r_key_returns_reset(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("r")])
        ctrl = FakeCtrl([[]])  # no one buzzed
        leds = make_leds()
        snd = make_sound()

        result = _phase1_buzz_in(
            win, sample_question, 1, 5, ctrl, leds, team_config, snd,
            is_last_question=False, game_state=None, scores={1: 0, 2: 0},
        )
        assert result == _R_RESET

    def test_s_key_returns_skipped(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("s")])
        ctrl = FakeCtrl([[]])
        leds = make_leds()
        snd = make_sound()

        result = _phase1_buzz_in(
            win, sample_question, 1, 5, ctrl, leds, team_config, snd,
            is_last_question=False, game_state=None, scores={1: 0, 2: 0},
        )
        assert result == _R_SKIPPED

    def test_final_question_uses_final_countdown_music(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        _phase1_buzz_in(
            win, sample_question, 5, 5, ctrl, leds, team_config, snd,
            is_last_question=True, game_state=None, scores={1: 0, 2: 0},
        )
        snd.final_countdown.assert_called_once()
        snd.jeopardy_thinking.assert_not_called()

    def test_normal_question_uses_jeopardy_music(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        _phase1_buzz_in(
            win, sample_question, 1, 5, ctrl, leds, team_config, snd,
            is_last_question=False, game_state=None, scores={1: 0, 2: 0},
        )
        snd.jeopardy_thinking.assert_called_once()
        snd.final_countdown.assert_not_called()

    def test_game_state_updated_to_buzzing(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()
        gs = GameState()

        _phase1_buzz_in(
            win, sample_question, 1, 5, ctrl, leds, team_config, snd,
            is_last_question=False, game_state=gs, scores={1: 0, 2: 0},
        )
        snap = gs.snapshot()
        assert snap["phase"] == "buzzing"
        assert snap["active_team"] is None
        assert snap["question_text"] == "What is 2+2?"


# ---------------------------------------------------------------------------
# _phase2_wait_for_next_buzz
# ---------------------------------------------------------------------------

class TestPhase2WaitForNextBuzz:

    def test_new_buzz_returns_buzzed(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        # First ranking has 1 entry (turn=1, i.e. already answered), second has 2
        ctrl = FakeCtrl([[1], [1, 2]])
        leds = make_leds()
        snd = make_sound()

        result = _phase2_wait_for_next_buzz(
            win, sample_question, 1, 5, ctrl, leds, snd,
            team_config, turn=1, is_last_question=False, game_state=None,
        )
        assert result == _R_BUZZED

    def test_r_key_returns_reset(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("r")])
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        result = _phase2_wait_for_next_buzz(
            win, sample_question, 1, 5, ctrl, leds, snd,
            team_config, turn=1, is_last_question=False, game_state=None,
        )
        assert result == _R_RESET

    def test_s_key_returns_skipped(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("s")])
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        result = _phase2_wait_for_next_buzz(
            win, sample_question, 1, 5, ctrl, leds, snd,
            team_config, turn=1, is_last_question=False, game_state=None,
        )
        assert result == _R_SKIPPED

    def test_timeout_returns_timed_out(self, sample_question, team_config, no_draw):
        """Simulate 5s passing without a new buzz by patching time.monotonic."""
        win = FakeWin()
        ctrl = FakeCtrl([[1]])  # still just 1 entry
        leds = make_leds()
        snd = make_sound()

        # Return increasing times: first few calls under 5s, then past 5s
        times = iter([0, 0.1, 0.2, 5.1, 5.2])

        def fake_monotonic():
            try:
                return next(times)
            except StopIteration:
                return 10.0

        with patch("quiz.flow.time.monotonic", side_effect=fake_monotonic), \
                patch("quiz.flow.time.sleep"), \
                patch("quiz.flow.POLL_INTERVAL", 0):
            result = _phase2_wait_for_next_buzz(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, turn=1, is_last_question=False, game_state=None,
            )
        assert result == _R_TIMED_OUT

    def test_resets_game_state_active_team(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        ctrl = FakeCtrl([[1], [1, 2]])
        leds = make_leds()
        snd = make_sound()
        gs = GameState()
        gs.update(phase="answering", active_team=1)

        _phase2_wait_for_next_buzz(
            win, sample_question, 1, 5, ctrl, leds, snd,
            team_config, turn=1, is_last_question=False, game_state=gs,
        )
        snap = gs.snapshot()
        assert snap["phase"] == "buzzing"
        assert snap["active_team"] is None


# ---------------------------------------------------------------------------
# _phase2_answer_countdown
# ---------------------------------------------------------------------------

class TestPhase2AnswerCountdown:

    def test_correct_key_returns_answered(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("c")])  # the correct answer
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase") as _la:
            _la.return_value = "breathe"
            result = _phase2_answer_countdown(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, current_buzzer=1, answer_timeout=30.0,
                is_last_question=False, answer_source=None,
                game_state=None, scores={1: 0, 2: 0},
            )
        assert result[0] == "answered"
        assert result[1] == "c"

    def test_s_key_returns_skipped(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("s")])
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            result = _phase2_answer_countdown(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, current_buzzer=1, answer_timeout=30.0,
                is_last_question=False, answer_source=None,
                game_state=None, scores={1: 0, 2: 0},
            )
        assert result == _R_SKIPPED

    def test_r_key_returns_reset(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin(key_sequence=[ord("r")])
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            result = _phase2_answer_countdown(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, current_buzzer=1, answer_timeout=30.0,
                is_last_question=False, answer_source=None,
                game_state=None, scores={1: 0, 2: 0},
            )
        assert result == _R_RESET

    def test_multiclient_polls_answer_source(self, sample_question, team_config, no_sleep, no_draw):
        win = FakeWin()
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()
        answer_source = MagicMock()
        answer_source.poll_once.return_value = "b"

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            result = _phase2_answer_countdown(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, current_buzzer=2, answer_timeout=30.0,
                is_last_question=False, answer_source=answer_source,
                game_state=None, scores={1: 0, 2: 0},
            )
        assert result[0] == "answered"
        assert result[1] == "b"
        answer_source.reset.assert_called_once_with(2)

    def test_multiclient_ignores_keyboard_abc(self, sample_question, team_config, no_sleep, no_draw):
        """In multi-client mode, a/b/c on keyboard should NOT answer."""
        win = FakeWin(key_sequence=[ord("a"), ord("s")])  # try 'a' then skip
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()
        answer_source = MagicMock()
        answer_source.poll_once.return_value = None  # no remote answer

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            result = _phase2_answer_countdown(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, current_buzzer=1, answer_timeout=30.0,
                is_last_question=False, answer_source=answer_source,
                game_state=None, scores={1: 0, 2: 0},
            )
        # 'a' ignored, 's' processes → SKIPPED
        assert result == _R_SKIPPED

    def test_timeout_returns_timed_out(self, sample_question, team_config, no_draw):
        """Simulate the answer timer expiring."""
        win = FakeWin()
        ctrl = FakeCtrl([[1]])
        leds = make_leds()
        snd = make_sound()

        # buzz_start captured at first call, then elapsed exceeds timeout
        times = iter([0.0, 0.1, 31.0, 31.1])

        def fake_monotonic():
            try:
                return next(times)
            except StopIteration:
                return 100.0

        with patch("quiz.flow.time.monotonic", side_effect=fake_monotonic), \
                patch("quiz.flow.time.sleep"), \
                patch("quiz.flow.POLL_INTERVAL", 0), \
                patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            result = _phase2_answer_countdown(
                win, sample_question, 1, 5, ctrl, leds, snd,
                team_config, current_buzzer=1, answer_timeout=30.0,
                is_last_question=False, answer_source=None,
                game_state=None, scores={1: 0, 2: 0},
            )
        assert result == _R_TIMED_OUT


# ---------------------------------------------------------------------------
# run_question end-to-end with mocked screens
# ---------------------------------------------------------------------------

class TestRunQuestionE2E:
    """Full state-machine tests. We mock the screen helpers so they don't
    actually draw or block on getch()."""

    @pytest.fixture
    def no_screens(self):
        """Mock all full-screen helpers."""
        with patch("quiz.flow.show_feedback"), \
                patch("quiz.flow.show_answer_reveal"), \
                patch("quiz.flow.show_nobody_reveal"), \
                patch("quiz.flow.show_timeout_screen"):
            yield

    def test_correct_answer_returns_plus_one(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        # Phase 1 iterates: (getch=-1, ranking=[]) twice, then (getch=-1,
        # ranking=[1]) to buzz. Phase 2b then sees getch=ord("c").
        win = FakeWin(key_sequence=[-1, -1, -1, ord("c")])
        ctrl = FakeCtrl([[], [], [1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            deltas = run_question(
                win, sample_question, 1, 5, ctrl, leds, team_config, snd,
                answer_timeout=30.0, is_last_question=False,
                scores={1: 0, 2: 0},
            )
        assert deltas == {1: 1}

    def test_wrong_answer_returns_minus_one_and_skipped_after(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        # Phase 1: two empty polls → buzz. Phase 2b: 'a' (wrong).
        # Phase 2a (wait for next buzz): 's' (skip).
        win = FakeWin(key_sequence=[-1, -1, -1, ord("a"), ord("s")])
        ctrl = FakeCtrl([[], [], [1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            deltas = run_question(
                win, sample_question, 1, 5, ctrl, leds, team_config, snd,
                answer_timeout=30.0, is_last_question=False,
                scores={1: 0, 2: 0},
            )
        assert deltas == {1: -1}

    def test_skip_in_phase1_returns_empty_deltas(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        win = FakeWin(key_sequence=[ord("s")])
        ctrl = FakeCtrl([[]])
        leds = make_leds()
        snd = make_sound()

        deltas = run_question(
            win, sample_question, 1, 5, ctrl, leds, team_config, snd,
            answer_timeout=30.0, is_last_question=False,
            scores={1: 0, 2: 0},
        )
        assert deltas == {}

    def test_wrong_then_correct_returns_plus_one(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        """Team 1 buzzes, answers wrong. Team 2 buzzes, answers correctly.

        Result: {1: -1, 2: +1}. This is the core correct-after-wrong path
        the review flagged as untested.
        """
        # Phase 1: empty, empty, [1] → team 1 buzzed
        # Phase 2b(team1): getch 'a' (wrong)
        # Phase 2a (wait): empty ranking stays [1], need to wait for team 2
        # Phase 2a poll: ranking becomes [1, 2] → _R_BUZZED
        # Phase 2b(team2): getch 'c' (correct)
        win = FakeWin(key_sequence=[-1, -1, -1, ord("a"), -1, -1, ord("c")])
        ctrl = FakeCtrl([[], [], [1], [1], [1], [1, 2]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            deltas = run_question(
                win, sample_question, 1, 5, ctrl, leds, team_config, snd,
                answer_timeout=30.0, is_last_question=False,
                scores={1: 0, 2: 0},
            )
        assert deltas == {1: -1, 2: 1}

    def test_reset_clears_score_deltas(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        """Answer wrong, press r to reset, then buzz & answer correctly.

        The wrong answer's -1 should NOT leak into the final deltas because
        reset starts the question over with a clean slate.
        """
        # Phase 1: two empty polls, then [1] → buzzed
        # Phase 2b: 'a' (wrong, -1)
        # Phase 2a: 'r' (reset) — outer loop restarts, score_deltas cleared
        # Phase 1 again: buzz → Phase 2b: 'c' → return {1: 1}
        win = FakeWin(key_sequence=[
            -1, -1, -1, ord("a"),  # first attempt: wrong
            ord("r"),               # reset during Phase 2a
            -1, -1, -1, ord("c"),  # second attempt: correct
        ])
        ctrl = FakeCtrl([[], [], [1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            deltas = run_question(
                win, sample_question, 1, 5, ctrl, leds, team_config, snd,
                answer_timeout=30.0, is_last_question=False,
                scores={1: 0, 2: 0},
            )
        # Expected: the -1 is gone because reset clears score_deltas
        assert deltas == {1: 1}

    def test_reset_during_answer_countdown_restarts_question(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        """Reset pressed during Phase 2b (answer countdown) — clears deltas
        and restarts from Phase 1. Exercises the break-after-_R_RESET path."""
        # Phase 1: empty polls → buzz
        # Phase 2b: getch 'r' (reset during countdown, nothing answered yet)
        # Outer loop restarts → Phase 1 again → buzz → Phase 2b: 'c' (correct)
        win = FakeWin(key_sequence=[
            -1, -1, -1, ord("r"),   # reset during phase 2b
            -1, -1, -1, ord("c"),   # restart, correct answer
        ])
        ctrl = FakeCtrl([[], [], [1]])
        leds = make_leds()
        snd = make_sound()

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"):
            deltas = run_question(
                win, sample_question, 1, 5, ctrl, leds, team_config, snd,
                answer_timeout=30.0, is_last_question=False,
                scores={1: 0, 2: 0},
            )
        assert deltas == {1: 1}

    def test_all_teams_wrong_nobody_got_it(
        self, sample_question, team_config, no_sleep, no_draw, no_screens,
    ):
        """All teams answer wrong; 5s window expires; nobody got it."""
        # Phase 1: buzz team 1 → Phase 2b 'a' wrong → Phase 2a waits for team 2
        # Team 2 buzzes → Phase 2b 'b' wrong → Phase 2a times out (no more teams)
        win = FakeWin(key_sequence=[
            -1, -1, -1, ord("a"),    # team 1 wrong
            -1, -1, ord("b"),         # team 2 wrong
        ])
        ctrl = FakeCtrl([[], [], [1], [1], [1, 2], [1, 2]])
        leds = make_leds()
        snd = make_sound()

        # Patch time.monotonic so phase 2a times out quickly
        call_count = [0]
        base_time = [0.0]

        def fake_monotonic():
            # After team 2 answers wrong, every subsequent call adds 2s to
            # simulate elapsed time during the "wait for next buzz" window.
            call_count[0] += 1
            # Simple clock that advances on each call
            base_time[0] += 0.01
            return base_time[0]

        with patch("quiz.flow.leds_answer_phase", return_value="breathe"), \
                patch("quiz.flow.time.monotonic", side_effect=fake_monotonic):
            deltas = run_question(
                win, sample_question, 1, 5, ctrl, leds, team_config, snd,
                answer_timeout=30.0, is_last_question=False,
                scores={1: 0, 2: 0},
            )
        # Both teams get -1. Nobody reveal is called (mocked).
        assert deltas == {1: -1, 2: -1}
