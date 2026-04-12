"""Tests for quiz/game_state.py — thread-safe state container."""

import threading

from quiz.game_state import GameState


class TestGameState:

    def test_initial_phase_is_idle(self):
        gs = GameState()
        assert gs.snapshot()["phase"] == "idle"

    def test_initial_snapshot_has_expected_keys(self):
        gs = GameState()
        snap = gs.snapshot()
        for key in ("phase", "active_team", "question_num", "question_text",
                    "choices", "time_remaining", "answer_timeout", "scores", "teams"):
            assert key in snap

    def test_update_sets_fields(self):
        gs = GameState()
        gs.update(phase="buzzing", active_team=2, question_num=3)
        snap = gs.snapshot()
        assert snap["phase"] == "buzzing"
        assert snap["active_team"] == 2
        assert snap["question_num"] == 3

    def test_update_preserves_unset_fields(self):
        gs = GameState()
        gs.update(phase="answering", active_team=1)
        gs.update(question_num=5)
        snap = gs.snapshot()
        assert snap["phase"] == "answering"
        assert snap["active_team"] == 1
        assert snap["question_num"] == 5

    def test_snapshot_returns_copy_not_reference(self):
        gs = GameState()
        gs.update(phase="buzzing")
        snap = gs.snapshot()
        snap["phase"] = "tampered"
        assert gs.snapshot()["phase"] == "buzzing"

    def test_concurrent_updates_dont_crash(self):
        gs = GameState()
        errors = []

        def writer(i):
            try:
                for _ in range(100):
                    gs.update(question_num=i, active_team=i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    snap = gs.snapshot()
                    assert "phase" in snap
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_update_with_nested_dict(self):
        gs = GameState()
        gs.update(scores={"1": 3, "2": -1})
        assert gs.snapshot()["scores"] == {"1": 3, "2": -1}

    def test_update_with_none_values(self):
        gs = GameState()
        gs.update(active_team=2)
        gs.update(active_team=None)
        assert gs.snapshot()["active_team"] is None
