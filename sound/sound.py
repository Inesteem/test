"""
Quiz game sound effects using sox (play).

Generates tones programmatically — no audio files needed.
Install sox: sudo apt install sox

Usage:
    from sound import Sound

    snd = Sound()
    snd.correct()              # blocking
    snd.wrong()
    snd.play("countdown")      # by name

    snd.jeopardy_thinking()    # long, run in background:
    handle = snd.jeopardy_thinking(background=True)
    handle.stop()              # cut it short
"""

import subprocess
import shutil
import threading
from dataclasses import dataclass

# Note frequencies (Hz), octave 4 unless suffixed
NOTES = {
    "C3": 130.81, "D3": 146.83, "Eb3": 155.56, "E3": 164.81, "F3": 174.61,
    "F#3": 185.00, "G3": 196.00, "Ab3": 207.65, "A3": 220.00,
    "Bb3": 233.08, "B3": 246.94,
    "C4": 261.63, "Db4": 277.18, "D4": 293.66, "Eb4": 311.13,
    "E4": 329.63, "F4": 349.23, "F#4": 369.99, "Gb4": 369.99, "G4": 392.00,
    "Ab4": 415.30, "A4": 440.00, "Bb4": 466.16, "B4": 493.88,
    "C5": 523.25, "Db5": 554.37, "D5": 587.33, "Eb5": 622.25,
    "E5": 659.25, "F5": 698.46, "F#5": 739.99, "G5": 783.99,
    "Ab5": 830.61, "A5": 880.00, "Bb5": 932.33, "B5": 987.77,
    "C6": 1046.50, "D6": 1174.66,
}

# Rest pseudo-frequency — sox won't produce audible output at 1Hz
REST = 1


def n(name: str, duration: float = 0.3) -> tuple[float, float]:
    """Shorthand: n("E4", 0.5) -> (329.63, 0.5)"""
    return (NOTES[name], duration)


def rest(duration: float = 0.3) -> tuple[float, float]:
    return (REST, duration)


# ---------------------------------------------------------------------------
# Melodies
# ---------------------------------------------------------------------------

MELODIES: dict[str, list[tuple[float, float]]] = {}


def _jeopardy_thinking() -> list[tuple[float, float]]:
    """The Jeopardy 'Think!' music — key of F major, ~120 BPM.

    Based on https://gist.github.com/pyropeter/671426 (transposed +1 octave).
    Played twice: first pass ends on the chromatic descent,
    second pass resolves down to the tonic.
    """
    q = 0.50   # quarter note
    e = 0.25   # eighth note
    h = 1.00   # half note
    t = 0.67   # 2/3 note (triplet feel, matches Arduino dur=3)

    # -- First pass --
    # Measures 1-2: C-F-C-A opening motif (first C is octave-low for weight)
    m1 = [n("C3", q), n("F4", q), n("C4", q), n("A3", q)]
    m2 = [n("C4", q), n("F4", q), n("C4", h)]
    # Measures 3-4: Motif into signature descending chromatic run
    m3 = [n("C4", q), n("F4", q), n("C4", q), n("F4", q)]
    m4 = [n("Bb4", t), n("G4", e), n("F4", e), n("E4", e), n("D4", e), n("Db4", e)]

    # Measures 5-6: Motif repeat
    m5 = [n("C4", q), n("F4", q), n("C4", q), n("A3", q)]
    m6 = [n("C4", q), n("F4", q), n("C4", h)]
    # Measures 7-8: Second descent with rest
    m7 = [n("Bb4", q), rest(e), n("G4", e), n("F4", q), n("E4", q)]
    m8 = [n("D4", q), n("Db4", q), n("C4", q)]

    # -- Second pass (repeat to fill 30 s) --
    m9  = [n("C3", q), n("F4", q), n("C4", q), n("A3", q)]
    m10 = [n("C4", q), n("F4", q), n("C4", h)]
    m11 = [n("C4", q), n("F4", q), n("C4", q), n("F4", q)]
    m12 = [n("Bb4", t), n("G4", e), n("F4", e), n("E4", e), n("D4", e), n("Db4", e)]

    m13 = [n("C4", q), n("F4", q), n("C4", q), n("A3", q)]
    m14 = [n("C4", q), n("F4", q), n("C4", h)]
    # Final descent resolving to tonic
    m15 = [n("Bb4", q), rest(e), n("G4", e), n("F4", q), n("E4", q)]
    m16 = [n("D4", q), n("Db4", q), n("C4", h), rest(q)]

    return (m1 + m2 + m3 + m4 + m5 + m6 + m7 + m8
            + m9 + m10 + m11 + m12 + m13 + m14 + m15 + m16)


def _final_countdown() -> list[tuple[float, float]]:
    """The Final Countdown intro riff (Europe) — F# minor, 118 BPM."""
    # At 118 BPM: eighth = ~0.254s, quarter = ~0.508s
    e = 0.25   # eighth note
    q = 0.51   # quarter note
    h = 1.02   # half note

    return [
        # --- First phrase (Db5-B4-Db5-F#4 motif) ---
        n("Db5", e), n("B4", e), n("Db5", q), n("F#4", h),
        rest(0.1),
        n("D5", e), n("Db5", e), n("D5", q), n("Db5", q), n("B4", h),
        rest(0.1),
        n("D5", e), n("Db5", e), n("D5", q), n("F#4", h),
        rest(0.1),
        n("Ab4", e), n("A4", e), n("Ab4", e), n("A4", e),
        n("Ab4", e), n("F#4", e), n("Ab4", h),
        rest(0.3),
        # --- Second phrase (repeat) ---
        n("Db5", e), n("B4", e), n("Db5", q), n("F#4", h),
        rest(0.1),
        n("D5", e), n("Db5", e), n("D5", q), n("Db5", q), n("B4", h),
        rest(0.1),
        n("D5", e), n("Db5", e), n("D5", q), n("F#4", h),
        rest(0.1),
        n("Ab4", e), n("A4", e), n("Ab4", e), n("A4", e),
        n("Ab4", e), n("F#4", e), n("Ab4", q),
        rest(0.2),
        # --- Fill/closing phrase ---
        n("Ab4", e), n("A4", e), n("B4", e), n("A4", e),
        n("B4", e), n("Db5", e), n("B4", e), n("A4", e),
        n("Ab4", e), n("F#4", h),
    ]


def _correct() -> list[tuple[float, float]]:
    """Happy ascending major arpeggio."""
    return [
        n("C5", 0.12), n("E5", 0.12), n("G5", 0.35),
    ]


def _wrong() -> list[tuple[float, float]]:
    """Descending 'wah wah' buzzer."""
    return [
        n("Eb4", 0.35), n("D4", 0.35), n("Db4", 0.35), n("C4", 0.7),
    ]


def _times_up() -> list[tuple[float, float]]:
    """Urgent three-beep time's up signal."""
    return [
        n("A5", 0.15), rest(0.08),
        n("A5", 0.15), rest(0.08),
        n("A5", 0.5),
    ]


def _dramatic_sting() -> list[tuple[float, float]]:
    """Dun dun DUNNN reveal moment."""
    return [
        n("G3", 0.3), rest(0.1),
        n("G3", 0.3), rest(0.1),
        n("Eb3", 0.9),
    ]


def _tick() -> list[tuple[float, float]]:
    """Single tick for countdown timers."""
    return [n("A5", 0.05)]


def _suspense() -> list[tuple[float, float]]:
    """Low rumbling suspense — building tension while waiting."""
    e = 0.25
    return [
        n("C3", e), rest(0.15),
        n("Db4", e), rest(0.15),
        n("C3", e), rest(0.15),
        n("Db4", e), rest(0.15),
        n("C3", e), rest(0.15),
        n("D4", e), rest(0.15),
        n("C3", e), rest(0.15),
        n("Eb3", 0.5),
    ]


def _mystery_game() -> list[tuple[float, float]]:
    """A famous video game theme — can you guess which?

    Based on https://github.com/robsoncouto/arduino-songs (tempo 144 BPM).
    """
    # 144 BPM: whole = 1.667s
    q = 0.42   # quarter  (1667/4)
    e = 0.21   # eighth   (1667/8)
    h = 0.83   # half     (1667/2)
    w = 1.67   # whole    (1667/1)
    dq = 0.63  # dotted quarter

    # -- Section A: the iconic melody --
    a1 = [
        n("E5", q), n("B4", e), n("C5", e), n("D5", q), n("C5", e), n("B4", e),
        n("A4", q), n("A4", e), n("C5", e), n("E5", q), n("D5", e), n("C5", e),
        n("B4", dq), n("C5", e), n("D5", q), n("E5", q),
        n("C5", q), n("A4", q), n("A4", q), rest(q),
    ]
    a2 = [
        rest(e), n("D5", q), n("F5", e), n("A5", q), n("G5", e), n("F5", e),
        n("E5", dq), n("C5", e), n("E5", q), n("D5", e), n("C5", e),
        n("B4", q), n("B4", e), n("C5", e), n("D5", q), n("E5", q),
        n("C5", q), n("A4", q), n("A4", q), rest(q),
    ]

    # -- Section B: slower, broader phrases --
    b = [
        n("E5", h), n("C5", h),
        n("D5", h), n("B4", h),
        n("C5", h), n("A4", h),
        n("B4", w),
        n("E5", h), n("C5", h),
        n("D5", h), n("B4", h),
        n("C5", q), n("E5", q), n("A5", h),
        n("Ab5", w),
    ]

    return a1 + a2 + b


def _mystery_game_2() -> list[tuple[float, float]]:
    """Another famous video game theme — guess which!

    Based on https://github.com/robsoncouto/arduino-songs (tempo 88 BPM).
    """
    # 88 BPM: wholenote = 2727ms
    dh = 2.05   # dotted half
    h = 1.36    # half
    q = 0.68    # quarter
    dq = 1.02   # dotted quarter
    e = 0.34    # eighth
    de = 0.51   # dotted eighth
    s = 0.17    # sixteenth
    w = 2.73    # whole

    # -- Intro: atmospheric opening --
    intro = [
        n("Bb4", dh),
        n("F4", e), n("F4", e), n("Bb4", e), n("Ab4", s), n("F#4", s),
        n("Ab4", dh),
        n("Bb4", dh),
        n("F#4", e), n("F#4", e), n("Bb4", e), n("A4", s), n("G4", s),
        n("A4", dh),
        rest(w),
    ]

    # -- Main melody --
    theme = [
        n("Bb4", q), n("F4", dq), n("Bb4", e),
        n("Bb4", s), n("C5", s), n("D5", s), n("Eb5", s),
        n("F5", h),
        n("F5", e), n("F5", e), n("F5", e), n("F#5", s), n("Ab5", s),
        n("Bb5", dh),
        n("Bb5", e), n("Bb5", e), n("Ab5", e), n("F#5", s),
        n("Ab5", de), n("F#5", s),
        n("F5", h),
        n("F5", q), n("Eb5", de), n("F5", s),
        n("F#5", h),
        n("F5", e), n("Eb5", e), n("Db5", de), n("Eb5", s),
        n("F5", h),
        n("Eb5", e), n("Db5", e), n("C5", de), n("D5", s),
        n("E5", h),
        n("G5", e), n("F5", s),
    ]

    # -- Rhythmic transition --
    bridge = [
        n("F4", s), n("F4", s), n("F4", s), n("F4", s),
        n("F4", s), n("F4", s), n("F4", s),
        n("F4", e), n("F4", s), n("F4", e),
    ]

    return intro + theme + bridge


MELODIES["jeopardy_thinking"] = _jeopardy_thinking()
MELODIES["final_countdown"] = _final_countdown()
MELODIES["correct"] = _correct()
MELODIES["wrong"] = _wrong()
MELODIES["times_up"] = _times_up()
MELODIES["dramatic_sting"] = _dramatic_sting()
MELODIES["tick"] = _tick()
MELODIES["suspense"] = _suspense()
MELODIES["mystery_game"] = _mystery_game()
MELODIES["mystery_game_2"] = _mystery_game_2()


def _metal_gear() -> list[tuple[float, float]]:
    """Metal Gear Solid Main Theme (TAPPY) — key of A minor, ~92 BPM.

    Reconstructed from piano lead-sheet transcriptions.
    """
    q = 0.65   # quarter
    e = 0.33   # eighth
    h = 1.30   # half
    dh = 1.96  # dotted half
    dq = 0.98  # dotted quarter

    # -- Opening: the iconic E-D-C --
    opening = [
        n("E5", h), n("D5", h),
        n("C5", dh), rest(q),
    ]

    # -- Response: D-E … E-D --
    response = [
        n("D5", e), n("E5", dq),
        n("E5", h), n("D5", dh), rest(q),
    ]

    # -- Second phrase: ascending C-D-E, descending A-G-E-C --
    second = [
        n("C5", e), n("D5", e), n("E5", dh), rest(q),
        n("A5", e), n("G5", e), n("E5", e), n("C5", dq), rest(q),
        n("D5", dh), rest(q),
    ]

    # -- Climax: ascending to C6, reaching D6 --
    climax = [
        n("E5", e), n("A5", e), n("C6", dh),
        n("C6", e), n("D6", e), n("C6", dh),
    ]

    # -- Descending resolution --
    descent = [
        n("B5", e), n("C6", e), n("D6", e), n("C6", dq),
        n("A5", q), n("G5", e), n("A5", e), n("B5", dq),
        n("C6", e), n("B5", e), n("A5", q),
        n("G5", e), n("A5", dh), rest(q),
    ]

    return opening + response + second + climax + descent


MELODIES["metal_gear"] = _metal_gear()


# ---------------------------------------------------------------------------
# Playback handle (for background sounds)
# ---------------------------------------------------------------------------

@dataclass
class PlaybackHandle:
    """Returned by background playback — call .stop() to cut the sound."""
    _thread: threading.Thread
    _stop_event: threading.Event

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2)

    @property
    def playing(self) -> bool:
        return self._thread.is_alive()


# ---------------------------------------------------------------------------
# Sound player
# ---------------------------------------------------------------------------

class Sound:
    def __init__(self, volume: float = 0.5):
        """
        Args:
            volume: 0.0 – 1.0, controls sox output gain.
        """
        if not shutil.which("play"):
            raise RuntimeError(
                "sox is not installed. Install it with: sudo apt install sox"
            )
        self.volume = max(0.0, min(1.0, volume))

    def _play_note(self, freq: float, duration: float):
        """Play a single tone via sox."""
        cmd = [
            "play", "-qn",
            "synth", str(duration),
            "sine", str(freq),
            "vol", str(self.volume),
            "fade", "0.01", str(duration), "0.01",
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _play_sequence(
        self,
        notes: list[tuple[float, float]],
        stop_event: threading.Event | None = None,
        loop: bool = False,
    ):
        while True:
            for freq, dur in notes:
                if stop_event and stop_event.is_set():
                    return
                self._play_note(freq, dur)
            if not loop:
                return

    def play(self, name: str, *, background: bool = False, loop: bool = False) -> PlaybackHandle | None:
        """
        Play a named melody.

        Args:
            name: one of the registered melody names.
            background: if True, returns a PlaybackHandle immediately.
        """
        if name not in MELODIES:
            raise ValueError(
                f"Unknown melody {name!r}. "
                f"Available: {', '.join(sorted(MELODIES))}"
            )
        notes = MELODIES[name]

        if not background:
            self._play_sequence(notes, loop=loop)
            return None

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._play_sequence,
            args=(notes, stop_event, loop),
            daemon=True,
        )
        thread.start()
        return PlaybackHandle(_thread=thread, _stop_event=stop_event)

    # -- Convenience methods --------------------------------------------------

    def correct(self, **kw) -> PlaybackHandle | None:
        return self.play("correct", **kw)

    def wrong(self, **kw) -> PlaybackHandle | None:
        return self.play("wrong", **kw)

    def jeopardy_thinking(self, **kw) -> PlaybackHandle | None:
        return self.play("jeopardy_thinking", **kw)

    def final_countdown(self, **kw) -> PlaybackHandle | None:
        return self.play("final_countdown", **kw)

    def times_up(self, **kw) -> PlaybackHandle | None:
        return self.play("times_up", **kw)

    def dramatic_sting(self, **kw) -> PlaybackHandle | None:
        return self.play("dramatic_sting", **kw)

    def tick(self, **kw) -> PlaybackHandle | None:
        return self.play("tick", **kw)

    def suspense(self, **kw) -> PlaybackHandle | None:
        return self.play("suspense", **kw)

    def mystery_game(self, **kw) -> PlaybackHandle | None:
        return self.play("mystery_game", **kw)

    def mystery_game_2(self, **kw) -> PlaybackHandle | None:
        return self.play("mystery_game_2", **kw)

    def metal_gear(self, **kw) -> PlaybackHandle | None:
        return self.play("metal_gear", **kw)

    def list_melodies(self) -> list[str]:
        return sorted(MELODIES.keys())
