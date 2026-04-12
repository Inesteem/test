"""Tests for quiz/team_setup.py — mostly about the palette exhaustion guard.

Full interactive testing would need a real curses terminal. These focus on
the edge cases that are deterministic.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from quiz.constants import COLOR_PALETTE


class FakeWin:
    def __init__(self, key_sequence=()):
        self._keys = list(key_sequence)

    def getch(self):
        if self._keys:
            return self._keys.pop(0)
        return -1

    def getmaxyx(self):
        return (24, 80)

    def bkgd(self, *a, **k): pass
    def clear(self): pass
    def refresh(self): pass
    def addstr(self, *a, **k): pass
    def nodelay(self, *a, **k): pass


@pytest.fixture(autouse=True)
def stub_curses():
    """Patch curses primitives that need an initialized terminal."""
    import curses

    with patch("quiz.team_setup.curses.color_pair", return_value=0), \
            patch("quiz.team_setup.curses.A_BOLD", 0), \
            patch("quiz.team_setup.curses.A_DIM", 0), \
            patch("quiz.team_setup.curses.A_REVERSE", 0), \
            patch("quiz.team_setup.curses.curs_set"), \
            patch("quiz.team_setup.curses.KEY_UP", curses.KEY_UP), \
            patch("quiz.team_setup.curses.KEY_DOWN", curses.KEY_DOWN), \
            patch("quiz.team_setup.curses.KEY_ENTER", curses.KEY_ENTER), \
            patch("quiz.drawing.curses.color_pair", return_value=0), \
            patch("quiz.drawing.curses.A_BOLD", 0), \
            patch("quiz.drawing.curses.A_DIM", 0), \
            patch("quiz.drawing.curses.A_REVERSE", 0), \
            patch("quiz.drawing.curses.error", Exception):
        yield


class TestPickColorExhaustedPalette:
    """MEDIUM #8: pick_color must not crash when all 12 colors are used."""

    def test_all_colors_used_falls_back_to_full_palette(self):
        from quiz.team_setup import pick_color

        # Use up every color in the palette
        used = {c for c, _ in COLOR_PALETTE}
        assert len(used) == 12

        # Press Enter immediately — should pick the first fallback color
        win = FakeWin(key_sequence=[10])  # Enter
        leds = MagicMock()

        # Should not raise IndexError
        color_hex, color_name = pick_color(win, 13, used, leds)
        # Fallback gives us whatever's first in COLOR_PALETTE
        assert (color_hex, color_name) == COLOR_PALETTE[0]

    def test_normal_usage_filters_used_colors(self):
        from quiz.team_setup import pick_color

        used = {COLOR_PALETTE[0][0]}  # skip the first color
        win = FakeWin(key_sequence=[10])  # Enter immediately
        leds = MagicMock()

        color_hex, _ = pick_color(win, 1, used, leds)
        # The first available color is COLOR_PALETTE[1], not [0]
        assert color_hex == COLOR_PALETTE[1][0]


# ── assign_buzzers tests ──

TEAM_CONFIG = {
    1: {"name": "Alpha", "color": "#ff0000", "color_name": "Red"},
    2: {"name": "Beta",  "color": "#0000ff", "color_name": "Blue"},
}


class FakeCtrl:
    """Fake RemoteBuzzerController whose ranking sequence is scripted.

    Raises RuntimeError if reset() is called more times than queues provided,
    so tests fail fast on misconfigured fixtures instead of hanging forever.
    """

    def __init__(self, rankings_per_team):
        """rankings_per_team: list of iterables, one per team assignment call."""
        self._queues = [list(q) for q in rankings_per_team]
        self._call_index = 0
        self._current_queue = iter([])

    def reset(self):
        if self._call_index >= len(self._queues):
            raise RuntimeError(
                f"FakeCtrl.reset() called {self._call_index + 1} times "
                f"but only {len(self._queues)} queues were provided"
            )
        self._current_queue = iter(self._queues[self._call_index])
        self._call_index += 1

    def get_ranking(self):
        return next(self._current_queue, [])


class TestAssignBuzzers:
    def test_happy_path_two_teams(self):
        """Both teams press distinct buzzers; mapping is recorded correctly."""
        from quiz.team_setup import assign_buzzers

        # Team 1 gets buzzer 2 on first poll, team 2 gets buzzer 1 on first poll
        ctrl = FakeCtrl([
            [[], [2]],   # slot 1: empty then buzzer 2 pressed
            [[], [1]],   # slot 2: empty then buzzer 1 pressed
        ])
        win = FakeWin()  # no keys → never aborts
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        assert result == {1: 2, 2: 1}
        # LEDs should have flashed each team's actual color
        leds.set_color.assert_any_call("#ff0000")
        leds.set_color.assert_any_call("#0000ff")
        assert leds.set_color.call_count == 2
        assert leds.off.call_count == 2

    def test_duplicate_buzzer_ignored(self):
        """If team 2 presses the buzzer already claimed by team 1, keep polling."""
        from quiz.team_setup import assign_buzzers

        # slot 1 claims buzzer 3; slot 2 first reports only buzzer 3
        # (already taken — even scanning all entries finds nothing),
        # then reports [3, 4] — scanning finds unclaimed 4.
        ctrl = FakeCtrl([
            [[3]],                  # slot 1 immediately gets 3
            [[3], [3], [3, 4]],     # slot 2: stale-only twice, then new entry
        ])
        win = FakeWin()
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        assert result == {1: 3, 2: 4}

    def test_escape_falls_back_to_identity(self):
        """Pressing Escape mid-assignment produces identity mapping for remaining slots."""
        from quiz.team_setup import assign_buzzers

        # Team 1 hasn't pressed yet; user hits Escape
        ctrl = FakeCtrl([
            [[]],  # slot 1: empty; escape fires before next poll
        ])
        # Feed escape on first getch
        win = FakeWin(key_sequence=[27])
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        # Both slots fall back to identity
        assert result == {1: 1, 2: 2}

    def test_game_state_updated(self):
        """game_state.update() is called with correct phase/team info and reset to idle."""
        from quiz.team_setup import assign_buzzers

        ctrl = FakeCtrl([[[10]], [[20]]])
        win = FakeWin()
        leds = MagicMock()
        game_state = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=game_state)

        calls = game_state.update.call_args_list
        # First call: assign team 1 (no teams assigned yet)
        assert calls[0].kwargs["phase"] == "buzzer_assign"
        assert calls[0].kwargs["assign_team"] == 1
        assert calls[0].kwargs["assign_team_name"] == "Alpha"
        assert calls[0].kwargs["assigned_teams"] == {}
        # After team 1 assigned, broadcast includes progress
        assert calls[1].kwargs["assigned_teams"]["1"]["buzzer_num"] == 10
        # Penultimate call: assign team 2 with team 1 done
        assert calls[2].kwargs["assign_team"] == 2
        assert calls[2].kwargs["assign_team_name"] == "Beta"
        # Last call: reset to idle
        assert calls[-1] == call(phase="idle", assign_team=None,
                                 assign_team_name=None, assigned_teams=None)

    def test_game_state_none_does_not_crash(self):
        """game_state=None is allowed (single-player path guard)."""
        from quiz.team_setup import assign_buzzers

        ctrl = FakeCtrl([[[1]], [[2]]])
        win = FakeWin()
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        assert result == {1: 1, 2: 2}

    def test_single_team(self):
        """Works with just one team."""
        from quiz.team_setup import assign_buzzers

        config = {1: {"name": "Solo", "color": "#00ff00", "color_name": "Green"}}
        ctrl = FakeCtrl([[[5]]])
        win = FakeWin()
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, config, ctrl, leds, game_state=None)

        assert result == {1: 5}

    def test_empty_team_config(self):
        """Empty team_config returns empty mapping immediately."""
        from quiz.team_setup import assign_buzzers

        ctrl = FakeCtrl([])
        win = FakeWin()
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, {}, ctrl, leds, game_state=None)

        assert result == {}

    def test_three_teams(self):
        """Three teams all get distinct buzzers; progress accumulates."""
        from quiz.team_setup import assign_buzzers

        config = {
            1: {"name": "A", "color": "#ff0000", "color_name": "Red"},
            2: {"name": "B", "color": "#00ff00", "color_name": "Green"},
            3: {"name": "C", "color": "#0000ff", "color_name": "Blue"},
        }
        ctrl = FakeCtrl([[[10]], [[20]], [[30]]])
        win = FakeWin()
        leds = MagicMock()
        game_state = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, config, ctrl, leds, game_state=game_state)

        assert result == {1: 10, 2: 20, 3: 30}
        # Final broadcast before idle should have all 3 teams in progress
        all_calls = game_state.update.call_args_list
        # The last assign broadcast (after team 3 matched) should show 3 done
        last_assign = [c for c in all_calls
                       if c.kwargs.get("phase") == "buzzer_assign"][-1]
        assert len(last_assign.kwargs["assigned_teams"]) == 3

    def test_escape_after_partial_assignment(self):
        """Escape after first team assigned: first keeps mapping, rest get fallback."""
        from quiz.team_setup import assign_buzzers

        ctrl = FakeCtrl([
            [[3]],  # team 1 succeeds
            [[]],   # team 2: empty, then escape fires
        ])
        # Keys: -1 during team 1 polls, then escape on team 2
        win = FakeWin(key_sequence=[-1, -1, 27])
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        assert result[1] == 3    # team 1 got buzzer 3
        assert result[2] != 3    # team 2 fallback must not collide

    def test_fallback_avoids_collision(self):
        """Identity fallback skips buzzer numbers already claimed."""
        from quiz.team_setup import assign_buzzers

        # slot 1 claims buzzer 2 (which is also the identity of slot 2)
        ctrl = FakeCtrl([
            [[2]],  # slot 1 → buzzer 2
            [[]],   # slot 2 never pressed (escape)
        ])
        win = FakeWin(key_sequence=[-1, 27])
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            result = assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        assert result[1] == 2
        # slot 2's identity (2) collides, so fallback must pick something else
        assert result[2] != 2
        # Both values must be unique
        assert len(set(result.values())) == len(result)

    def test_nodelay_restored(self):
        """win.nodelay(False) is called before returning."""
        from quiz.team_setup import assign_buzzers

        ctrl = FakeCtrl([[[1]], [[2]]])
        win = MagicMock()
        win.getch.return_value = -1
        win.getmaxyx.return_value = (24, 80)
        leds = MagicMock()

        with patch("quiz.team_setup.time.sleep"):
            assign_buzzers(win, TEAM_CONFIG, ctrl, leds, game_state=None)

        # Last nodelay call should be False (restore)
        nodelay_calls = win.nodelay.call_args_list
        assert nodelay_calls[-1] == call(False)
