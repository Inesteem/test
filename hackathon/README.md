# Quiz Buzzer Game -- Hackathon Brief

Build a multiplayer quiz game with physical USB buzzers, LED light effects, sound, and a display for a projector.

Teams buzz in with physical buttons, pick their name and color on their own device, and the room lights up and sounds off with every answer.

## What You Have

### Hardware

- **3 USB buzzer buttons** -- big satisfying buttons that players smash to buzz in
- **A USB RGB LED strip** -- reacts to the game (optional -- game runs fine without it)
- **A Raspberry Pi** -- on the local network, hosts the buzzers

### Why the RPi?

The buzzers are USB HID devices (they present as keyboards). Corp laptop security policy blocks unknown HID devices. The RPi has no such restriction -- so the buzzers plug into the RPi, and the game talks to it over the network.

The LED strip plugs into any machine. Each team device can optionally have its own LED strip too.

## The Game

A game master runs the app. The audience sees it on a projector (e.g. Chrome kiosk mode).

1. **Teams connect** from their own devices (phone, laptop) and pick a name and color
2. **Buzzer assignment** -- each team presses their physical buzzer to claim it
3. **Question rounds:**
   - Question + three choices (A/B/C) appear on the projector
   - LEDs animate while waiting for a buzz
   - First team to buzz sees answer buttons on their device
   - Correct: celebration lights + sound, team scores
   - Wrong: sad lights + sound, next team in buzz order gets a turn
   - Timeout: dramatic failure
4. **Scores** between rounds, dramatic final scoreboard

## Architecture

```
┌────────────┐       HTTP        ┌─────────────────┐       HTTP        ┌───────────────┐
│ Raspberry  │ ──────────────── │  Game Master    │ ──────────────── │ Team Client   │
│ Pi         │  buzzer state     │  (laptop)       │  register,       │ (phone/laptop)│
│ (buzzers)  │                   │                 │  answers, state   │               │
└────────────┘                   │  Display        │                   │  + optional   │
                                 │  Sound          │                   │    LED strip  │
                                 │  LEDs           │                   │               │
                                 └─────────────────┘                   └───────────────┘
                                        │
                                     Projector
```

Everything communicates over HTTP on the local network.

## Five Modules

| Module | What |
|--------|------|
| **Buzzers** | Detect presses on RPi, serve over HTTP |
| **LEDs** | Control the RGB strip with animations |
| **Sound** | Sound effects (procedural or otherwise) |
| **Game Engine** | Question loop, scoring, orchestration |
| **Display** | Projector UI + team device UI |

These can be built in parallel against agreed interfaces. See `contracts.md`.

## Timeline

| Time | Phase |
|------|-------|
| 0:00 | Kickoff. Read specs, agree on interfaces, ask questions. |
| 0:15 | Start coding. Build mocks of other teams' interfaces. |
| 1:00 | Quick sync. Can the pieces talk to each other? |
| 2:00 | Integration. Swap mocks for real implementations. |
| 2:30 | Play the game! |

## Resources

- **RPi**: `user@<ip>` (SSH, IP will be announced)
- **Buzzer vendor/product**: `0x2341:0xC036`
- **LED strip vendor/product**: `0x18d1:0x5035` (the device name is a clue)
