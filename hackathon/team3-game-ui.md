# Team 3: Game UI + Engine

You own the game itself -- the display, the game loop, and the multi-client infrastructure.

## The Problem

Build a quiz game that coordinates buzzers, LEDs, sound, and multiple team devices into a smooth game show experience. The audience watches on a projector.

## What You Consume

You depend on Team 1 (buzzers) and Team 2 (LEDs + sound). You won't have their code early on, so **start with mocks** of their interfaces (see `contracts.md`).

## What You Need to Build

### Game Engine

The state machine for each question round:

1. Wait for a buzz-in (poll buzzer ranking, trigger background music + LEDs)
2. Answer countdown (the buzzed team has N seconds)
3. Feedback (correct/wrong/timeout -- trigger sound + LEDs, show result)
4. Scores between rounds, dramatic final reveal

### Display

Design for a projector:
- Large text, high contrast, team colors everywhere
- Smooth animations (progress bars, transitions, celebrations)
- Screens: question + choices, feedback, timeout, scoreboard, team setup, buzzer assignment

### Multi-Client Flow

Teams play from their own devices:

1. Team device connects and gets a team number
2. Team picks a name and color (unique across teams)
3. Each team presses their physical buzzer to claim it
4. During the game, the team's device shows A/B/C buttons when it's their turn

### Question Bank

Write 15-25 quiz questions. Make them fun -- the kind that spark debate. See `contracts.md` for the format.

## Stretch Goals

- Animated effects (confetti, fire borders)
- An insult system that roasts wrong answers
- Spectator mode
