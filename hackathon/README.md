# Quiz Buzzer Game -- Hackathon Brief

Build a multiplayer quiz game with physical USB buzzers, LED light effects, procedural sound, and a browser-based display for a projector.

Teams buzz in with physical buttons, pick their name and color on their own device, and the room lights up and sounds off with every answer.

## What You Have

### Hardware

- **3 USB buzzer buttons** -- big satisfying buttons that players smash to buzz in
- **A USB RGB LED strip** -- reacts to the game (optional -- game runs fine without it)
- **A Raspberry Pi** -- on the local network, hosts the buzzers

### Why the RPi?

The buzzers are USB HID devices (they present as keyboards). Corp laptop security policy blocks unknown HID devices. The RPi has no such restriction -- so the buzzers plug into the RPi, and the game talks to it over the network.

The LED strip plugs into any machine (game master or team devices). Each team device can optionally have its own LED strip too.

### Software

- Python 3.10+ on all machines
- `sox` for procedural audio (`brew install sox` / `apt install sox`)
- A browser (Chrome kiosk mode recommended for the projector display)

## The Game

A game master runs the app on a laptop. The audience sees the game on a projector (suggest: Chrome kiosk mode pointing at the game master's web UI).

1. **Teams connect** from their own devices (phone, laptop) and pick a name and color
2. **Buzzer assignment** -- each team presses their physical buzzer to claim it
3. **Question rounds:**
   - Question + three choices (A/B/C) appear on the projector
   - LEDs animate while waiting for a buzz
   - First team to buzz sees answer buttons on their device
   - Correct: celebration lights + sound, team scores a point
   - Wrong: sad lights + sound, next team in buzz order gets a turn
   - Timeout: dramatic failure sequence
4. **Scores** between rounds, dramatic final scoreboard

## Architecture

```
┌────────────┐       HTTP        ┌─────────────────┐       HTTP        ┌───────────────┐
│ Raspberry  │ ──────────────── │  Game Master    │ ──────────────── │ Team Client   │
│ Pi         │  buzzer state     │  (laptop)       │  register,       │ (phone/laptop)│
│ (buzzers)  │                   │                 │  answers, state   │               │
└────────────┘                   │  Display (web)  │                   │  Web UI       │
                                 │  Sound (sox)    │                   │  + optional   │
                                 │  LEDs (USB)     │                   │    LED strip  │
                                 └─────────────────┘                   └───────────────┘
                                        │
                                     Browser
                                   (projector)
```

Everything communicates over HTTP on the local network. The game master is the central hub:
- Polls the RPi for buzzer presses
- Serves game state to team clients
- Pushes display updates to the projector browser
- Drives LEDs and sound locally

## Five Modules

The game breaks into five independent pieces that can be built in parallel:

| Module | What | Hardware |
|--------|------|----------|
| **Buzzers** | Detect button presses on RPi, serve over HTTP | USB buzzers + RPi |
| **LEDs** | Control the RGB strip with animations (rainbow, pulse, strobe, breathe) | USB LED strip |
| **Sound** | Procedural sound effects from sine waves via sox | Speakers |
| **Game Engine** | Question loop, scoring, state machine, orchestrates everything | -- |
| **Display** | Browser UI for the projector + team device web UI | Browser |

See the team specs and contracts for details on each.

## Timeline

| Time | Phase |
|------|-------|
| 0:00 | Kickoff. Read specs, agree on interfaces, ask questions. |
| 0:15 | Start coding. Build mocks of other teams' interfaces so you can work independently. |
| 1:00 | Quick sync. "Can you curl the buzzer server? Do LEDs light up? Does the display render?" |
| 2:00 | Integration. Swap mocks for real implementations. Debug together. |
| 2:30 | Play the game! Fix what breaks under real use. |

## Resources

- **RPi**: `user@<ip>` (SSH, IP will be announced)
- **Buzzer vendor/product**: `0x2341:0xC036`
- **LED strip vendor/product**: `0x18d1:0x5035` (the device name is a clue -- investigate it)
- Python 3.10+, `sox` for audio, `pyusb` and `evdev` as needed
