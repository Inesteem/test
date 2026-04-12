> **⚠ Archived — historical snapshot.** This document was written for the original hackathon and is frozen at that point. For current project state, see the [root README](../README.md).

# Quiz Buzzer Game -- Hackathon Brief

Build a multiplayer quiz game with physical USB buzzers, an LED light show, and procedural sound effects, all driven from a terminal.

Teams buzz in with physical buttons, a game master reads the question and accepts answers, and the room lights up and sounds off with every correct answer, wrong guess, and dramatic timeout.

## The Setup

You have three pieces of hardware:

1. **Two USB buzzer buttons** -- big satisfying buttons that players smash to buzz in
2. **A USB RGB LED strip** -- mounted visibly for the audience, reacts to the game
3. **A Raspberry Pi 4** -- on the local WiFi network, needed because of a constraint (see below)

And one important constraint:

**The buzzers cannot be plugged into corp laptops.** They're USB HID devices that present as keyboards, and corp security policy blocks unrecognized HID devices. The RPi has no such restriction. So the buzzers go into the RPi, and the game laptop talks to the RPi over the network to get buzzer state.

The LED strip plugs directly into the game laptop (it's not a HID device, so corp policy doesn't block it).

## The Game

A game master runs the app on a laptop connected to a projector. The flow:

1. **Settings** -- configure answer timeout, RPi address
2. **Team setup** -- each buzzer team picks a color (shown on the LEDs)
3. **Question loop:**
   - Question and three choices (A/B/C) appear on screen
   - LEDs animate while waiting for a buzz
   - First team to buzz gets to answer -- game master presses A, B, or C
   - Correct: celebration lights + sound, team scores a point
   - Wrong: sad lights + sound, next team in buzz order gets a turn
   - Timeout: dramatic failure sequence
   - Game master can press R at any time to reset buzzers
4. **Scores** between rounds, dramatic final scoreboard with winner celebration

## Three Teams, Three Modules

The game has a clean architecture with three independent modules that integrate through agreed interfaces. Each team owns one module. You work in parallel for ~2 hours, then integrate in the final stretch.

```
hackathon/
  team1-buzzers.md     -- RPi server + client library
  team2-lights-sound.md -- LED strip + procedural audio
  team3-game-ui.md     -- terminal game UI + questions
  contracts.md         -- the interface contracts all teams code against
```

**Read your team's spec and `contracts.md` first.** The contracts define how your module talks to the others. Code against the contracts, not against the other teams' implementations -- you won't have their code until integration time.

## Timeline

| Time | Phase |
|------|-------|
| 0:00 | Kickoff. Read specs, agree on contracts, ask questions. |
| 0:15 | Start coding. Build stubs/mocks of other teams' interfaces so you can test independently. |
| 1:00 | Quick sync. "Can you curl the buzzer server? Do LEDs light up? Does the UI work with mocks?" |
| 2:00 | Integration. Swap mocks for real implementations. Debug together. |
| 2:30 | Play the game! Fix what breaks under real use. |

## Resources

- **RPi**: `user@<ip>` (key-based SSH, IP will be announced)
- **Buzzer vendor/product**: `0x2341:0xC036`
- **LED strip vendor/product**: `0x18d1:0x5035` (the device name is a hint -- investigate it)
- **Python 3.10+** on all machines
- `pip install pyusb evdev` (as needed per team)
- `sox` for audio (`brew install sox` / `apt install sox`)
