> **⚠ Archived — historical snapshot.** This document was written for the original hackathon and is frozen at that point. For current project state, see the [root README](../README.md).

# Team 3: Game UI

You own the game itself -- a full-screen terminal application that ties together the buzzers, LEDs, and sounds into a multiplayer quiz experience.

## The Challenge

Build a curses-based terminal UI that a game master runs on a laptop (ideally connected to a projector). The game master controls the flow with the keyboard. Players interact by pressing physical buzzers.

## What You Consume

You depend on modules from Team 1 and Team 2. You won't have their code for most of the hackathon, so **start by building mock/stub versions** of their interfaces (see `contracts.md`).

```python
from buzzers.buzzer_remote import RemoteBuzzerController
from leds.klopfklopf import LEDController
from sound.sound import Sound
```

Simple mocks to get you started:

- `RemoteBuzzerController`: hardcode `get_buzzers()` returning `[1, 2]`, have `get_ranking()` return a list you can manipulate with keyboard input
- `LEDController`: print to stderr or just no-op
- `Sound`: print the sound name or just no-op

## What You Need to Build

### Settings Screen

A configuration screen at startup where the game master can set:

- RPi address and port (so Team 1's server can be found)
- Answer timeout (how many seconds a team has to answer after buzzing in)

### Team Setup

Each buzzer team picks a color from a palette. The selected color should be shown on the LEDs as feedback during selection.

### Question Loop

For each question:

1. **Display** the question and three choices (A/B/C) on screen
2. **Buzz-in phase**: animate LEDs while polling `get_ranking()` for the first press
3. **Answer phase**: the buzzed-in team's name is highlighted; game master presses A, B, or C on the keyboard
4. **Feedback**: correct/wrong/timeout -- show it visually, play the sound, light the LEDs
5. If wrong, the next team in buzz order gets a turn (until all teams have tried or someone gets it right)
6. The game master can press `R` at any time to reset buzzers and re-do the current question

### Sound + LED Choreography

Think about how to use LEDs and sound to build atmosphere:

- What plays/shows during the thinking time?
- How do you build tension as the timer counts down?
- What makes a correct answer feel like a celebration?
- What makes a timeout feel dramatic?

The LED controller has multiple animation modes (rainbow, pulse, strobe, breathe, candle) -- use them to tell a story across the game phases. The sound engine has background music (jeopardy, final countdown) that should play during the answer countdown and stop when someone answers.

### Score Tracking

Show scores between rounds. Make the final scoreboard dramatic -- this is the climax of the game.

### Question Bank

Write 15-25 quiz questions. Each has a question string, three choices (a/b/c), and a correct answer. Make them fun for the audience:

- CS/algorithms trivia (the kind that sparks debate)
- Google culture / tech industry lore
- Programming language gotchas
- "Gotcha" questions where the obvious answer is wrong
- Pop culture meets tech

The wrong answers should be plausible enough to cause arguments.

## Things to Think About

- `curses.wrapper(main)` handles init/cleanup for you
- `win.nodelay(True)` for non-blocking keyboard reads (returns -1 if no key)
- `curses.init_pair()` for color pairs, `curses.color_pair()` to use them
- Unicode box-drawing characters (`═`, `║`, `╔`, `╗`, etc.) make the UI look polished
- Poll the buzzer controller every ~100ms -- human reaction time makes this perfectly adequate
- The question text should be visually prominent (bold, highlighted, padded)
- Answer choices need breathing room -- don't cram them together
- A progress bar for the countdown timer adds urgency

## Stretch Goals

- Team name editing (not just "Team 1", "Team 2")
- Animated title screen
- Question categories or difficulty levels
- A "sudden death" final round
- Graceful degradation if LEDs or sound are unavailable (catch errors, run without them)
