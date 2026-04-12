> **⚠ Archived — historical snapshot.** This document was written for the original hackathon and is frozen at that point. For current project state, see the [root README](../README.md).

# Interface Contracts

These are the agreed APIs between all three teams. Code against these, not against each other's implementations. Build mocks/stubs of the interfaces you consume so you can develop independently.

## File Structure

```
buzzers/
  buzzer.py            -- Team 1: RPi-side buzzer detection
  buzzer_server.py     -- Team 1: RPi-side HTTP server
  buzzer_remote.py     -- Team 1: laptop-side client
leds/
  klopfklopf.py        -- Team 2: LED controller
sound/
  sound.py             -- Team 2: procedural audio engine
quiz/
  ui.py                -- Team 3: game UI
  questions.py         -- Team 3: question bank
```

## Import Paths

```python
from buzzers.buzzer_remote import RemoteBuzzerController
from leds.klopfklopf import LEDController
from sound.sound import Sound
from quiz.questions import QUESTIONS
```

---

## Buzzer Controller (Team 1 produces, Team 3 consumes)

### HTTP Server (runs on RPi)

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/` | `{"buzzers": [1, 2], "ranking": [2, 1]}` |
| `POST` | `/reset` | `{"ok": true}` |

- `buzzers`: list of connected buzzer numbers (stable across requests)
- `ranking`: ordered list of buzzer numbers in the order they were pressed (since last reset)

### Python Client

```python
class RemoteBuzzerController:
    def __init__(self, base_url: str): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def reset(self) -> None: ...
    def get_ranking(self) -> list[int]: ...
    def get_buzzers(self) -> list[int]: ...
```

- `start()` connects and fetches the buzzer list
- `get_ranking()` returns the current press order (empty list if nobody has pressed, or on error)
- `reset()` clears the ranking on the server (best-effort, no crash on failure)
- All network errors should be swallowed gracefully -- return safe defaults, never raise

---

## LED Controller (Team 2 produces, Team 3 consumes)

```python
class LEDController:
    def open(self) -> None: ...
    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, *exc): ...

    def set_color(self, color: str | tuple[int,int,int]) -> None: ...
    def off(self) -> None: ...

    def rainbow(self, colors: list, period: float = 2.0) -> None: ...
    def pulse(self, colors: list, period: float = 1.5) -> None: ...
    def strobe(self, color, hz: float = 10.0) -> None: ...
    def breathe(self, color, period: float = 4.0) -> None: ...
    def candle(self, color = (255,147,41), intensity: float = 0.4) -> None: ...
    def stop(self) -> None: ...
```

- Colors: hex string (`"#ff0000"`, `"#f00"`) or RGB tuple `(255, 0, 0)`
- Animated modes (`rainbow`, `pulse`, `strobe`, `breathe`, `candle`) run in a background thread
- Calling any mode automatically stops the previous animation
- `stop()` halts the animation but keeps the last color showing
- `off()` is shorthand for `set_color((0, 0, 0))`

---

## Sound Engine (Team 2 produces, Team 3 consumes)

```python
class Sound:
    def __init__(self, volume: float = 0.5): ...
    def play(self, name: str, *, background: bool = False) -> PlaybackHandle | None: ...

    def correct(self, **kw) -> PlaybackHandle | None: ...
    def wrong(self, **kw) -> PlaybackHandle | None: ...
    def jeopardy_thinking(self, **kw) -> PlaybackHandle | None: ...
    def final_countdown(self, **kw) -> PlaybackHandle | None: ...
    def times_up(self, **kw) -> PlaybackHandle | None: ...
    def dramatic_sting(self, **kw) -> PlaybackHandle | None: ...
    def tick(self, **kw) -> PlaybackHandle | None: ...

class PlaybackHandle:
    def stop(self) -> None: ...
    @property
    def playing(self) -> bool: ...
```

- `background=False` (default): blocks until the sound finishes
- `background=True`: returns a `PlaybackHandle` immediately; call `.stop()` to cut it short
- All convenience methods (`correct`, `wrong`, etc.) pass `**kw` through to `play()`

---

## Question Bank (Team 3 produces)

```python
QUESTIONS = [
    {
        "question": "What does the B in B-tree stand for?",
        "choices": {"a": "Binary", "b": "Balanced", "c": "Nobody knows for sure"},
        "answer": "c",
    },
    ...
]
```

- Each question has exactly 3 choices keyed `"a"`, `"b"`, `"c"`
- `answer` is one of `"a"`, `"b"`, `"c"`
- Aim for 15-25 questions, fun mix of CS trivia, tech culture, and gotcha questions
