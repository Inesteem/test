# Buzzers — Quiz Game with Hardware and Browser Display

A multiplayer quiz game for teams with physical USB buzzers, an RGB LED light show, procedurally generated sound effects, and optional AI-powered insults.

Two display modes: a browser-based UI for projectors (Chrome kiosk), or a legacy curses terminal UI. Teams answer on their own devices via a web interface. The room lights up and sounds off with every correct answer, wrong guess, and dramatic timeout.

## What's in the box

- **`quiz/`** — Game engine and display layer:
  - `display.py` — Display protocol (abstract interface for rendering + input)
  - `curses_display.py` — CursesDisplay (terminal backend, deprecated)
  - `web_display.py` — WebDisplay (browser backend via SSE)
  - `web_ui.py` — Web entry point (`python3 -m quiz.web_ui`)
  - `ui.py` — Curses entry point (`python3 -m quiz.ui`, deprecated)
  - `flow.py` — `run_question` state machine + phase helpers
  - `feedback.py` — feedback / answer reveal / scoreboard orchestration
  - `settings.py` — curses settings screen (used by curses entry point)
  - `team_setup.py` — client registration, team config, buzzer assignment
  - `drawing.py` — curses rendering primitives (used by CursesDisplay)
  - `led_show.py` — LED choreography
  - `insults.py` — static insult pack loader + fallback resolver
  - `insult_ai.py` — AI agent via Claude CLI headless mode
  - `questions.py` — question bundle loader with shuffling
  - `game_state.py` + `game_master_server.py` + `team_answer_source.py` — multi-client infrastructure
- **`static/`** — Browser game master UI (`gm.html`)
- **`buzzers/`** — USB buzzer detection (evdev) and HTTP server that runs on a Raspberry Pi
- **`leds/`** — KlopfKlopf USB LED strip controller with animation modes (rainbow, pulse, strobe, breathe, candle)
- **`sound/`** — Procedural sound engine using `sox` — no audio files needed
- **`questions/`** — JSON question bundles ([see questions/README.md](questions/README.md))
- **`insults/`** — JSON static insult packs ([see insults/README.md](insults/README.md))
- **`agents/`** — AI insult personality definitions ([see agents/README.md](agents/README.md))
- **`team_client.py`** — Team device client (web UI + optional LED strip)
- **`tests/`** — Unit tests (356 tests — see "Running tests" below)
- **`hackathon/`** — Historical hackathon specs (frozen reference)

## Architecture

```
┌────────────┐       HTTP        ┌─────────────────────────┐       HTTP        ┌───────────────┐
│ Raspberry  │ ──────────────── │  Game Master (laptop)   │ ──────────────── │ Team Client   │
│ Pi         │   GET / (buzzer   │                         │  POST /register   │ (phone/laptop)│
│ (buzzers)  │    ranking)       │  quiz/web_ui.py         │  POST /team_config│               │
└────────────┘                   │  ├── WebDisplay (SSE) ──┤  GET /state       │ team_client.py│
                                 │  ├── Sound (sox)        │  GET /answer      │ + optional    │
                                 │  └── LEDs (USB)         │   (polling)       │   LED strip   │
                                 │                         │                   │               │
                                 │  GET /gm ───────────── │──── Browser ────  │               │
                                 │  GET /gm/events (SSE)   │  (Chrome kiosk)   │               │
                                 │  POST /gm/command       │                   │               │
                                 └─────────────────────────┘                   └───────────────┘
```

The game engine (`flow.py`, `feedback.py`) talks to a **Display protocol**, not to a specific UI technology. Two implementations exist:

- **WebDisplay** — pushes screen state via Server-Sent Events to a browser. Commands come back via HTTP POST. Used by `web_ui.py`.
- **CursesDisplay** — wraps the legacy curses terminal rendering. Used by `ui.py` (deprecated).

## Quick start (browser mode — recommended)

### 1. Set up the Raspberry Pi

Plug USB buzzers into the RPi and deploy the buzzer server:

```bash
./setup_rpi.sh
```

See [buzzers/RPI_SETUP.md](buzzers/RPI_SETUP.md) for details.

### 2. Install local dependencies (macOS)

```bash
brew install libusb sox
python3 -m venv venv
venv/bin/pip install pyusb
```

On Linux, use `apt install libusb-1.0-0 sox` and `pip install pyusb`.

### LED strip (optional)

The RGB LED light show is optional — the game runs fine without it and will log a warning if no LED controller is detected.

If you do have the KlopfKlopf LED strip (`18d1:5035`) and want to use it:

- **macOS**: works out of the box with `brew install libusb`.
- **Linux**: raw USB devices are root-only by default. Run the udev setup script once to grant user-level access:

  ```bash
  ./leds/setup_udev.sh
  ```

  See the script itself for a full explanation. After running it, unplug and replug the LED strip.

### 3. Start the game master

```bash
venv/bin/python3 -m quiz.web_ui --gm-port 9000
```

### 4. Open the projector display

```bash
google-chrome --kiosk --app=http://localhost:9000/gm
```

Or just open `http://localhost:9000/gm` in any browser. The game master uses keyboard shortcuts: `A`/`B`/`C` to submit answers (single-player), `R` to reset buzzers, `S` to skip, `Enter` to advance.

### 5. Start team clients

On each team's device (phone, laptop, Raspberry Pi):

```bash
python3 team_client.py --game-master <GM_IP>:9000 --port 7777
```

Open `http://<device-ip>:7777` in a browser. The page shows a color/name picker, then switches to the quiz UI when the game starts. If a KlopfKlopf LED strip is attached to the client device, it lights up automatically.

### 6. Game flow

1. Team clients register with the game master automatically
2. Each team picks a name and color on their device
3. Each team presses their physical buzzer to claim it
4. Game starts — questions appear on the projector, teams buzz in and answer on their devices

## Quick start (curses mode — deprecated)

```bash
venv/bin/python3 -m quiz.ui
```

Curses mode supports both single-player (game master presses A/B/C) and multi-client. The settings screen lets you configure everything. This mode is preserved for backward compatibility but the browser mode is recommended for new setups.

## CLI options (web mode)

```
python3 -m quiz.web_ui [OPTIONS]

  --bundle N        Question bundle index (default: 0)
  --timeout N       Answer timeout in seconds (default: 30)
  --insult-pack N   Static insult pack index (omit for off)
  --insult-ai N     AI agent index (omit for off)
  --rpi-host HOST   Buzzer RPi host (default: $BUZZER_RPI_HOST or 192.168.178.41)
  --rpi-port PORT   Buzzer RPi port (default: $BUZZER_RPI_PORT or 8888)
  --gm-port PORT    Game master HTTP port (default: 9000)
```

## Game features

- **25+ questions per bundle** with difficulty ratings (1-10)
- **Answer shuffling** — the correct answer isn't always 'b'
- **Question order randomized**, hardest question always saved for last
- **Final question** gets fire effects (CSS animation in browser, ASCII columns in curses)
- **Sound choreography:** Jeopardy theme during buzz-in, Final Countdown for the last question, tick during answer, dramatic sting on reveal
- **LED choreography:** 3-phase answer timer (breathe → pulse → strobe), team-color feedback, candle suspense on reveal
- **Client-side LEDs:** each team device can optionally have its own LED strip showing team color and game phase effects
- **Minus points** for wrong answers, visible as red bars in the scoreboard
- **Skip** any question with `S`, **reset** buzzers with `R`
- **"SAVAGE!" / "LAME!"** falling text animations for fast answers / nobody got it
- **Insult mode** (optional) — static roast packs or AI-generated insults via Claude Haiku
- **Browser display** with 60fps progress bar, CSS animations, team-colored scoreboard
- **Automatic client registration** — no manual IP configuration needed

## AI insult agents

Set `claude` CLI up with your account (`claude /login`), then pass `--insult-ai N` to select an agent. Each agent has a custom personality (Gordon Ramsay, Drill Sergeant, Shakespeare, etc.). See [agents/README.md](agents/README.md) for how to write your own.

Fallback chain: AI → static pack → hardcoded texts. If the AI times out, the game still shows a roast.

## Running tests

```bash
python3 -m pytest tests/ -q
```

All 356 tests run on any platform. `tests/conftest.py` provides evdev and usb.core stubs so macOS can run the Linux-flavored tests too.

## Display protocol

The game engine is decoupled from the display via `quiz/display.py`:

```python
class Display(Protocol):
    def draw_question(self, q, question_num, total, **kw): ...
    def draw_feedback(self, correct, team_name, **kw): ...
    def draw_scores(self, scores, team_config, **kw): ...
    def draw_answer_reveal(self, q, **kw): ...
    def draw_timeout(self, team_name, **kw): ...
    def animate_falling_text(self, text, style, duration): ...
    def draw_ready(self, team_config): ...
    def draw_waiting(self, title, subtitle, items, status): ...
    def get_command(self, timeout=0) -> str | None: ...
    def wait_for_key(self) -> str | None: ...
    def flush_input(self): ...
```

To add a new display backend (e.g., OBS overlay, mobile spectator view), implement this protocol and wire it into a new entry point.

## Configuration

### Environment variables

- `BUZZER_RPI_HOST` — default RPi IP (fallback: `192.168.178.41`)
- `BUZZER_RPI_PORT` — default RPi port (fallback: `8888`)
- `ANTHROPIC_API_KEY` — not used; AI insults go through `claude` CLI

### Logs

Game events are written to `quiz.log` in the project root. Tail it while playing to debug:

```bash
tail -f quiz.log
```

## Module docs

- [buzzers/RPI_SETUP.md](buzzers/RPI_SETUP.md) — RPi deployment and the setup script
- [leds/README.md](leds/README.md) — LED controller API and USB protocol
- [sound/README.md](sound/README.md) — sound engine and melody list
- [questions/README.md](questions/README.md) — question bundle JSON format
- [insults/README.md](insults/README.md) — static insult pack JSON format
- [agents/README.md](agents/README.md) — AI agent personality format
- [hackathon/README.md](hackathon/README.md) — historical hackathon brief (frozen)

## Versioning

- `v1.0-single-player` — tagged before multi-client mode was added. Checkout to go back to pure single-player.
