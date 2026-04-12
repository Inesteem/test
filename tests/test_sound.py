"""Tests for sound/sound.py — procedural sound engine.

Mocks shutil.which and subprocess.run so no real sox calls happen.
"""

import threading
from unittest.mock import patch

import pytest

from sound.sound import (
    MELODIES,
    NOTES,
    REST,
    PlaybackHandle,
    Sound,
    n,
    rest,
)


# ---------------------------------------------------------------------------
# Pure data: NOTES, MELODIES, shorthand helpers
# ---------------------------------------------------------------------------

class TestNotes:

    def test_a4_is_440hz(self):
        assert NOTES["A4"] == 440.0

    def test_c4_middle_c_frequency(self):
        assert abs(NOTES["C4"] - 261.63) < 0.01

    def test_all_notes_are_numeric(self):
        for name, freq in NOTES.items():
            assert isinstance(freq, (int, float)), f"{name} is {type(freq)}"
            assert freq > 0, f"{name} has non-positive freq {freq}"

    def test_rest_is_not_audible(self):
        # REST is used as a pseudo-frequency that sox won't make noise from
        assert REST == 1


class TestNoteShorthand:

    def test_n_returns_freq_duration_tuple(self):
        result = n("A4", 0.5)
        assert result == (440.0, 0.5)

    def test_n_default_duration(self):
        result = n("A4")
        assert result[0] == 440.0
        assert result[1] == 0.3  # default

    def test_n_raises_on_unknown_note(self):
        with pytest.raises(KeyError):
            n("Z9", 0.3)

    def test_rest_returns_rest_duration(self):
        result = rest(0.25)
        assert result == (REST, 0.25)

    def test_rest_default_duration(self):
        assert rest()[1] == 0.3


class TestMelodies:

    def test_all_expected_melodies_exist(self):
        expected = {
            "jeopardy_thinking", "final_countdown", "correct", "wrong",
            "times_up", "dramatic_sting", "tick", "suspense",
        }
        assert set(MELODIES.keys()) >= expected

    def test_every_melody_is_a_list_of_tuples(self):
        for name, notes in MELODIES.items():
            assert isinstance(notes, list), f"{name} is {type(notes)}"
            assert len(notes) > 0, f"{name} is empty"
            for note in notes:
                assert isinstance(note, tuple), f"{name} has non-tuple note"
                assert len(note) == 2, f"{name} note wrong arity"
                freq, dur = note
                assert freq >= REST, f"{name} has negative freq"
                assert dur > 0, f"{name} has non-positive duration"

    def test_correct_is_short(self):
        # Correct jingle should be under 2 seconds total
        total = sum(dur for _, dur in MELODIES["correct"])
        assert total < 2.0

    def test_jeopardy_is_long(self):
        # Jeopardy thinking is meant to be ~30s
        total = sum(dur for _, dur in MELODIES["jeopardy_thinking"])
        assert total > 15.0  # allow some slack


# ---------------------------------------------------------------------------
# Sound.__init__
# ---------------------------------------------------------------------------

class TestSoundInit:

    def test_init_raises_when_play_not_installed(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="sox"):
                Sound()

    def test_init_succeeds_when_play_is_available(self):
        with patch("shutil.which", return_value="/usr/bin/play"):
            snd = Sound()
        assert snd.volume == 0.5

    def test_volume_clamped_below_zero(self):
        with patch("shutil.which", return_value="/usr/bin/play"):
            snd = Sound(volume=-1.0)
        assert snd.volume == 0.0

    def test_volume_clamped_above_one(self):
        with patch("shutil.which", return_value="/usr/bin/play"):
            snd = Sound(volume=2.0)
        assert snd.volume == 1.0

    def test_volume_mid_range_unchanged(self):
        with patch("shutil.which", return_value="/usr/bin/play"):
            snd = Sound(volume=0.75)
        assert snd.volume == 0.75


# ---------------------------------------------------------------------------
# Sound._play_note — invokes subprocess
# ---------------------------------------------------------------------------

@pytest.fixture
def snd():
    with patch("shutil.which", return_value="/usr/bin/play"):
        yield Sound(volume=0.5)


class TestPlayNote:

    def test_play_note_calls_sox(self, snd):
        with patch("sound.sound.subprocess.run") as m:
            snd._play_note(440.0, 0.3)
        m.assert_called_once()
        cmd = m.call_args[0][0]
        assert cmd[0] == "play"
        assert "synth" in cmd
        assert "440.0" in cmd
        assert "0.3" in cmd

    def test_play_note_includes_volume(self, snd):
        with patch("sound.sound.subprocess.run") as m:
            snd._play_note(440.0, 0.3)
        cmd = m.call_args[0][0]
        assert "vol" in cmd
        assert "0.5" in cmd


# ---------------------------------------------------------------------------
# Sound._play_sequence — loop + stop_event
# ---------------------------------------------------------------------------

class TestPlaySequence:

    def test_plays_all_notes_in_order(self, snd):
        notes = [(440.0, 0.1), (880.0, 0.2)]
        with patch.object(snd, "_play_note") as m:
            snd._play_sequence(notes)
        assert m.call_count == 2
        assert m.call_args_list[0][0] == (440.0, 0.1)
        assert m.call_args_list[1][0] == (880.0, 0.2)

    def test_stop_event_interrupts(self, snd):
        notes = [(440.0, 0.1), (880.0, 0.1), (1760.0, 0.1)]
        stop = threading.Event()
        stop.set()  # already set
        with patch.object(snd, "_play_note") as m:
            snd._play_sequence(notes, stop_event=stop)
        assert m.call_count == 0  # immediately stops

    def test_loop_repeats_until_stop(self, snd):
        notes = [(440.0, 0.01)]
        stop = threading.Event()
        call_count = [0]

        def count_and_maybe_stop(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 3:
                stop.set()

        with patch.object(snd, "_play_note", side_effect=count_and_maybe_stop):
            snd._play_sequence(notes, stop_event=stop, loop=True)

        assert call_count[0] == 3

    def test_non_loop_plays_once(self, snd):
        notes = [(440.0, 0.01), (880.0, 0.01)]
        with patch.object(snd, "_play_note") as m:
            snd._play_sequence(notes, loop=False)
        assert m.call_count == 2  # doesn't repeat


# ---------------------------------------------------------------------------
# Sound.play — foreground and background modes
# ---------------------------------------------------------------------------

class TestPlay:

    def test_play_unknown_raises(self, snd):
        with pytest.raises(ValueError, match="Unknown melody"):
            snd.play("nonexistent")

    def test_play_foreground_blocks_and_returns_none(self, snd):
        with patch.object(snd, "_play_sequence") as m:
            result = snd.play("correct")
        assert result is None
        m.assert_called_once()

    def test_play_background_returns_handle(self, snd):
        with patch.object(snd, "_play_note"):  # fast mock
            handle = snd.play("correct", background=True)
        assert handle is not None
        assert isinstance(handle, PlaybackHandle)

    def test_background_handle_can_stop(self, snd):
        with patch.object(snd, "_play_note"):
            handle = snd.play("jeopardy_thinking", background=True)
            handle.stop()
        assert not handle.playing


# ---------------------------------------------------------------------------
# Convenience methods dispatch to play()
# ---------------------------------------------------------------------------

class TestConvenienceMethods:

    @pytest.mark.parametrize("method_name,melody_name", [
        ("correct", "correct"),
        ("wrong", "wrong"),
        ("jeopardy_thinking", "jeopardy_thinking"),
        ("final_countdown", "final_countdown"),
        ("times_up", "times_up"),
        ("dramatic_sting", "dramatic_sting"),
        ("tick", "tick"),
        ("suspense", "suspense"),
    ])
    def test_convenience_method_calls_play_with_correct_name(self, snd, method_name, melody_name):
        with patch.object(snd, "play") as m:
            getattr(snd, method_name)()
        m.assert_called_once_with(melody_name)

    def test_convenience_method_forwards_kwargs(self, snd):
        with patch.object(snd, "play") as m:
            snd.correct(background=True, loop=True)
        m.assert_called_once_with("correct", background=True, loop=True)


class TestListMelodies:

    def test_returns_sorted_list(self, snd):
        melodies = snd.list_melodies()
        assert melodies == sorted(melodies)

    def test_includes_all_registered_melodies(self, snd):
        assert set(snd.list_melodies()) == set(MELODIES.keys())


# ---------------------------------------------------------------------------
# PlaybackHandle
# ---------------------------------------------------------------------------

class TestPlaybackHandle:

    def test_playing_true_while_thread_alive(self):
        stop = threading.Event()
        thread = threading.Thread(target=lambda: stop.wait(10))
        thread.daemon = True
        thread.start()
        handle = PlaybackHandle(_thread=thread, _stop_event=stop)
        try:
            assert handle.playing is True
        finally:
            stop.set()
            thread.join(timeout=1)

    def test_playing_false_after_stop(self):
        stop = threading.Event()
        thread = threading.Thread(target=lambda: stop.wait(10))
        thread.daemon = True
        thread.start()
        handle = PlaybackHandle(_thread=thread, _stop_event=stop)
        handle.stop()
        assert handle.playing is False

    def test_stop_sets_event(self):
        stop = threading.Event()
        thread = threading.Thread(target=lambda: stop.wait(10), daemon=True)
        thread.start()
        handle = PlaybackHandle(_thread=thread, _stop_event=stop)
        handle.stop()
        assert stop.is_set()
