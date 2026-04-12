# Buzzers — Terminal Quiz Game with Hardware

A multiplayer quiz game for teams with physical USB buzzers, an RGB LED light show, procedurally generated sound effects, and optional AI-powered insults.

Runs in a terminal via curses. Teams buzz in on physical buttons, the game master reads the question, and the room lights up and sounds off with every correct answer, wrong guess, and dramatic timeout.

## What's in the box

- **`quiz/`** — The curses game UI, split into focused modules:
  - `ui.py` — entry point (`python3 -m quiz.ui`)
  - `settings.py` — settings screen + team IP picker
  - `team_setup.py` — color picker, team name entry
  - `drawing.py` — curses primitives + question render
  - `feedback.py` — feedback / answer reveal / scoreboard screens
  - `flow.py` — `run_question` state machine + phase helpers
  - `led_show.py` — LED choreography
  - `insults.py` — static insult pack loader + fallback resolver
  - `insult_ai.py` — AI agent via Claude CLI headless mode
  - `questions.py` — question bundle loader with shuffling
  - `game_state.py` + `game_master_server.py` + `team_answer_source.py` — multi-client infrastructure
- **`buzzers/`** — USB buzzer detection (evdev) and HTTP server that runs on a Raspberry Pi
- **`leds/`** — KlopfKlopf USB LED strip controller with animation modes (rainbow, pulse, strobe, breathe, candle)
- **`sound/`** — Procedural sound engine using `sox` — no audio files needed
- **`questions/`** — JSON question bundles ([see questions/README.md](questions/README.md))
- **`insults/`** — JSON static insult packs ([see insults/README.md](insults/README.md))
- **`agents/`** — AI insult personality definitions ([see agents/README.md](agents/README.md))
- **`team_client.py`** — Standalone phone/laptop client for multi-client mode
- **`tests/`** — Unit tests (261 tests — see "Running tests" below)
- **`hackathon/`** — Historical hackathon specs (frozen reference)

## Quick start (single-player mode)

In single-player mode, the game master controls answers from the keyboard. You need a Raspberry Pi with USB buzzers plugged in, and the game laptop with the LED strip.

### 1. Set up the Raspberry Pi

Plug USB buzzers into the RPi and deploy the buzzer server:

```bash
./setup_rpi.sh
```

See [buzzers/RPI_SETUP.md](buzzers/RPI_SETUP.md) for details. The script copies the latest code, starts the server on port 8888, and verifies it's reachable.

### 2. Install local dependencies (macOS)

```bash
brew install libusb sox
python3 -m venv venv
venv/bin/pip install pyusb
```

On Linux, use `apt install libusb-1.0-0 sox` and `pip install pyusb`.

### 3. Run the game

```bash
venv/bin/python3 -m quiz.ui
```

You'll get a settings screen. Pick a question bundle, set the timeout, confirm the RPi address, and hit Enter to start. The game master uses `A`/`B`/`C` to submit answers, `R` to reset buzzers, and `S` to skip a question.

## Multi-client mode

In multi-client mode, teams answer on their own devices (phones, laptops) via a web interface instead of the game master pressing A/B/C. Useful when the game master can't see every team clearly, or when you want teams to read the choices on their own screen.

### Setup

**Game master** (same laptop as single-player):
1. In the settings screen, toggle "Game mode" to `Multi-Client (HTTP)`
2. After buzzer discovery, a team IP editor appears — set one IP:port per buzzer
3. The game master HTTP server starts automatically on port 9000 (configurable)

**Each team** (phone or laptop):

```bash
python3 team_client.py --game-master 10.0.0.2:9000 --port 7777
```

Open `http://<device-ip>:7777/?team=N` in a browser (where N is the buzzer number). The page shows the current game state and turns into three big A/B/C buttons when it's the team's turn.

### Architecture

```
┌────────────┐       HTTP        ┌─────────────────┐       HTTP        ┌───────────────┐
│ Raspberry  │ ──────────────── │  Game Master    │ ──────────────── │ Team Client   │
│ Pi         │   GET / (buzzer   │  (laptop)       │   GET /state      │ (phone/lap)   │
│ (buzzers)  │    ranking)       │                 │   (polling)       │               │
└────────────┘                   │                 │ <──────────────── │               │
                                 │                 │   GET /answer     │               │
                                 │                 │    (polling)      │               │
                                 └─────────────────┘                   └───────────────┘
                                        │
                                        │ USB
                                        ▼
                                  ┌──────────┐
                                  │ LED strip│
                                  └──────────┘
```

- **RPi** hosts buzzer state (`GET /`, `POST /reset`)
- **Game master** hosts live game state (`GET /state`) — phase, active team, question, choices, scores
- **Team clients** host their answer (`GET /answer`, `POST /submit`, `POST /reset`)
- Team clients poll the game master for state, render the UI, and submit answers
- Game master polls team clients for their answers in place of keyboard A/B/C

See [quiz/game_master_server.py](quiz/game_master_server.py), [quiz/team_answer_source.py](quiz/team_answer_source.py), and [team_client.py](team_client.py) for the implementation.

### Why multi-client?

A team of engineers can't plug physical buzzers into corp laptops (USB HID policy), so the buzzers sit on a Raspberry Pi. But in multi-client mode, the answer input also moves off the game master, enabling remote/distributed quiz nights.

## Game features

- **25+ questions per bundle** with difficulty ratings (1-10)
- **Answer shuffling** — the correct answer isn't always 'b'
- **Question order randomized**, hardest question always saved for last
- **Final question** gets animated ASCII fire columns on both sides
- **Sound choreography:** Jeopardy theme during buzz-in, Final Countdown for the last question, tick during answer, dramatic sting on reveal
- **LED choreography:** 3-phase answer timer (breathe → pulse → strobe), team-color feedback, candle suspense on reveal
- **Minus points** for wrong answers, visible as red bars in the scoreboard
- **Skip** any question with `s`, **reset** buzzers with `r`
- **"SAVAGE!" / "LAME!"** falling text animations for fast answers / nobody got it
- **Insult mode** (optional) — static roast packs or AI-generated insults via Claude Haiku

## AI insult agents

Set `claude` CLI up with your account (`claude /login`), then pick an AI agent in the settings screen. Each agent has a custom personality (Gordon Ramsay, Drill Sergeant, Shakespeare, etc.). See [agents/README.md](agents/README.md) for how to write your own.

Fallback chain: AI → static pack → hardcoded texts. If the AI times out, the game still shows a roast.

## Running tests

```bash
python3 -m pytest tests/ -q
```

All 261 tests run on any platform. `tests/conftest.py` provides evdev
and usb.core stubs so macOS can run the Linux-flavored tests too.

## Configuration

### Environment variables

- `BUZZER_RPI_HOST` — default RPi IP (fallback: `10.0.0.1`)
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
