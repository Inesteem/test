# Interface Contracts

These are the agreed APIs between all modules. Code against these, not against each other's implementations. Build mocks/stubs of the interfaces you consume so you can develop independently.

## File Structure

```
buzzers/
  buzzer.py            -- Team 1: RPi-side buzzer detection
  buzzer_server.py     -- Team 1: RPi-side HTTP server
  buzzer_remote.py     -- Team 1: laptop-side client
leds/
  klopfklopf.py        -- Team 2: LED controller
  stub.py              -- No-op LED stub (for when hardware is absent)
sound/
  sound.py             -- Team 2: procedural audio engine
quiz/
  display.py           -- Display protocol (abstract interface)
  web_display.py       -- WebDisplay (browser via SSE)
  curses_display.py    -- CursesDisplay (terminal, deprecated)
  web_ui.py            -- Web entry point
  ui.py                -- Curses entry point (deprecated)
  flow.py              -- Game state machine
  feedback.py          -- Feedback/reveal/score screens
  game_master_server.py -- HTTP server + SSE
  game_state.py        -- Thread-safe shared state
  team_setup.py        -- Registration, config, buzzer assignment
  team_answer_source.py -- Polls team clients
  questions.py         -- Question bank
static/
  gm.html             -- Browser game master display
team_client.py         -- Team device client + web UI
```

## Import Paths

```python
from buzzers.buzzer_remote import RemoteBuzzerController
from leds.klopfklopf import LEDController
from leds.stub import NoOpLEDController
from sound.sound import Sound
from quiz.questions import QUESTIONS
from quiz.web_display import WebDisplay
from quiz.curses_display import CursesDisplay
```

---

## Buzzer Controller (Team 1 produces, Game Engine consumes)

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

## LED Controller (Team 2 produces, Game Engine + Team Client consume)

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
- `NoOpLEDController` (`leds/stub.py`) is a drop-in stub when hardware is absent -- all methods are no-ops

---

## Sound Engine (Team 2 produces, Game Engine consumes)

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
    def suspense(self, **kw) -> PlaybackHandle | None: ...

class PlaybackHandle:
    def stop(self) -> None: ...
    @property
    def playing(self) -> bool: ...
```

- `background=False` (default): blocks until the sound finishes
- `background=True`: returns a `PlaybackHandle` immediately; call `.stop()` to cut it short
- All convenience methods (`correct`, `wrong`, etc.) pass `**kw` through to `play()`
- Sound plays via `sox` on the game master machine -- the browser does NOT play sound

---

## Display Protocol (Game Engine produces, Display Backend consumes)

```python
class Display(Protocol):
    # Rendering (push screen state)
    def draw_question(self, q, question_num, total, *, status_line="", ranking_line="",
                      elapsed=None, timeout=None, is_final=False, fire_frame=0,
                      ripple_frame=-1) -> None: ...
    def draw_feedback(self, correct, team_name, *, question_text="",
                      correct_answer="", insult="") -> None: ...
    def draw_continue_prompt(self, text="Press Enter to continue") -> None: ...
    def draw_answer_reveal(self, q, *, title="", insult="") -> None: ...
    def draw_timeout(self, team_name, *, insult="") -> None: ...
    def draw_scores(self, scores, team_config, *, final=False) -> None: ...
    def animate_falling_text(self, text, style, duration=1.5) -> None: ...
    def draw_ready(self, team_config) -> None: ...
    def draw_waiting(self, title, subtitle, items, status) -> None: ...
    def draw_buzzer_assign(self, current_name, current_color, assigned, team_config) -> None: ...
    def draw_error(self, message, detail="") -> None: ...

    # Input (read commands from game master)
    def get_command(self, timeout=0) -> str | None: ...
    def wait_for_key(self) -> str | None: ...
    def flush_input(self) -> None: ...
```

- `draw_*` methods are pure rendering -- they push a screen state and return immediately
- `animate_falling_text` is the exception: it blocks for `duration` seconds
- `get_command(timeout=0)` is non-blocking; `get_command(timeout=5.0)` blocks up to 5s
- `wait_for_key()` blocks until any key/command is received
- Commands are strings: `"a"`, `"b"`, `"c"`, `"r"`, `"s"`, `"enter"`, `"escape"`, `"up"`, `"down"`, `"left"`, `"right"`, `"space"`, or `None`

---

## Game Master HTTP Server

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/state` | Current game state JSON (polled by team clients) |
| `POST` | `/register` | Register a team client, returns `{team_num}` |
| `POST` | `/team_config` | Submit team name+color (validated for uniqueness) |
| `GET` | `/gm` | Serve the browser game master UI (gm.html) |
| `GET` | `/gm/events` | SSE stream -- pushes WebDisplay screen state |
| `POST` | `/gm/command` | Receive keyboard command from browser GM: `{cmd: "a"}` |
| `GET` | `/gm/static/*` | Static files from the `static/` directory |

---

## Team Client HTTP Server

Each team device runs `team_client.py` which serves a web UI and exposes endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the team web UI (setup → game) |
| `GET` | `/answer` | Current answer (`{answer: "a"}` or `{answer: null}`) |
| `POST` | `/submit` | Team submits answer: `{answer: "a"}` |
| `POST` | `/reset` | Clear stored answer (called by GM between rounds) |
| `GET` | `/team_config` | Current team config (polled by GM during setup) |
| `POST` | `/team_config` | Submit name+color (forwarded to GM for validation) |
| `GET` | `/client_info` | Team number, config status |
| `GET` | `/proxy/state` | Proxies GM `/state` to the browser |

---

## Question Bank (Team 3 produces)

```python
QUESTIONS = [
    {
        "question": "What does the B in B-tree stand for?",
        "choices": {"a": "Binary", "b": "Balanced", "c": "Nobody knows for sure"},
        "answer": "c",
        "difficulty": 7,
    },
    ...
]
```

- Each question has exactly 3 choices keyed `"a"`, `"b"`, `"c"`
- `answer` is one of `"a"`, `"b"`, `"c"`
- `difficulty` (1-10) is optional, defaults to 5; the hardest question is always saved for last
- Aim for 15-25 questions, fun mix of CS trivia, tech culture, and gotcha questions
