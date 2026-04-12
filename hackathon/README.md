# Quiz Buzzer Game -- Hackathon Brief

Build a multiplayer quiz game with physical USB buzzers, an LED light show, procedural sound effects, and a browser-based game master display for projectors.

Teams buzz in with physical buttons, pick their name and color on their own device, and the room lights up and sounds off with every correct answer, wrong guess, and dramatic timeout.

## The Setup

You have three pieces of hardware:

1. **Two USB buzzer buttons** -- big satisfying buttons that players smash to buzz in
2. **A USB RGB LED strip** -- mounted visibly for the audience, reacts to the game (optional -- game runs fine without it)
3. **A Raspberry Pi 4** -- on the local WiFi network, needed because of a constraint (see below)

And one important constraint:

**The buzzers cannot be plugged into corp laptops.** They're USB HID devices that present as keyboards, and corp security policy blocks unrecognized HID devices. The RPi has no such restriction. So the buzzers go into the RPi, and the game laptop talks to the RPi over the network to get buzzer state.

The LED strip plugs directly into the game laptop (it's not a HID device, so corp policy doesn't block it). Each team device can optionally have its own LED strip too.

## The Game

A game master runs the app on a laptop. The audience display is a browser page projected via Chrome kiosk mode. The flow:

1. **Start the game master server**: `python3 -m quiz.web_ui --gm-port 9000`
2. **Open Chrome kiosk on the projector**: `google-chrome --kiosk --app=http://localhost:9000/gm`
3. **Teams connect** by running `team_client.py` on their device and opening a browser
4. **Team setup** -- each team picks a name and color on their own device's web UI
5. **Buzzer assignment** -- each team presses their physical buzzer to claim it
6. **Question loop:**
   - Question and three choices (A/B/C) appear on the projector display
   - LEDs animate while waiting for a buzz
   - First team to buzz sees A/B/C buttons on their device -- they tap to answer
   - Correct: celebration lights + sound, team scores a point
   - Wrong: sad lights + sound, next team in buzz order gets a turn
   - Timeout: dramatic failure sequence
   - Game master can press R on the keyboard to reset buzzers, S to skip
7. **Scores** between rounds, dramatic final scoreboard with winner celebration

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

The game engine talks to a **Display protocol** (`quiz/display.py`) that abstracts all rendering and input. Two implementations:

- **WebDisplay** (recommended) -- pushes state via Server-Sent Events to a browser, reads commands via HTTP POST
- **CursesDisplay** (legacy) -- renders in a terminal via curses

## Five Modules

The game has a clean architecture with five independent layers:

```
quiz/
  display.py               -- Display protocol (abstract interface)
  curses_display.py         -- CursesDisplay backend (deprecated)
  web_display.py            -- WebDisplay backend (SSE + HTTP)
  web_ui.py                 -- Web entry point
  ui.py                     -- Curses entry point (deprecated)
  flow.py                   -- Game state machine (run_question)
  feedback.py               -- Feedback/reveal/score orchestration
  settings.py               -- Curses settings screen
  team_setup.py             -- Registration, config, buzzer assignment
  game_state.py             -- Thread-safe shared state
  game_master_server.py     -- HTTP server (state, registration, SSE, commands)
  team_answer_source.py     -- Polls team clients for answers
  led_show.py               -- LED choreography
  insults.py + insult_ai.py -- Insult system (static + AI)
  questions.py              -- Question loader + shuffler
static/
  gm.html                   -- Browser game master UI (HTML+CSS+JS)
buzzers/
  buzzer.py                 -- RPi buzzer detection (evdev)
  buzzer_server.py          -- RPi HTTP server
  buzzer_remote.py          -- Laptop-side client
leds/
  klopfklopf.py             -- LED strip controller
  stub.py                   -- No-op LED stub
sound/
  sound.py                  -- Procedural audio (sox)
team_client.py              -- Team device (web UI + LED driver)
```

## Timeline

| Time | Phase |
|------|-------|
| 0:00 | Kickoff. Read specs, agree on contracts, ask questions. |
| 0:15 | Start coding. Build stubs/mocks of other modules' interfaces so you can test independently. |
| 1:00 | Quick sync. "Can you curl the buzzer server? Do LEDs light up? Does the browser display render?" |
| 2:00 | Integration. Swap mocks for real implementations. Debug together. |
| 2:30 | Play the game! Fix what breaks under real use. |

## Resources

- **RPi**: `user@<ip>` (key-based SSH, IP will be announced)
- **Buzzer vendor/product**: `0x2341:0xC036`
- **LED strip vendor/product**: `0x18d1:0x5035` (the device name is a hint -- investigate it)
- **Python 3.10+** on all machines
- `pip install pyusb evdev` (as needed per module)
- `sox` for audio (`brew install sox` / `apt install sox`)
