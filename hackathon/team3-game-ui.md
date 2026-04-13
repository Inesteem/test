# Team 3: Game UI + Engine

You own the game itself -- the display, the game loop, the quiz experience, and the multi-client infrastructure. The game master runs it on a laptop; the audience sees it on a projector.

## The Problem

Build a quiz game that coordinates buzzers, LEDs, sound, and multiple team devices into a smooth game show experience. The audience display should look great on a projector -- suggest using Chrome kiosk mode with a browser-based UI.

## What You Consume

You depend on modules from Team 1 and Team 2. You won't have their code early on, so **start with mocks** of their interfaces (see `contracts.md`):

- **Buzzers**: mock `get_ranking()` to return a list you control via keyboard
- **LEDs**: use a no-op stub that logs calls
- **Sound**: mock with print statements or `MagicMock()`

## What You Need to Build

### Game Engine

The state machine that runs each question round:

1. Wait for a buzz-in (poll buzzer ranking, play background music, animate LEDs)
2. Answer countdown (the buzzed team has N seconds to answer via their device)
3. Feedback (correct/wrong/timeout -- trigger sound + LEDs, show result)
4. Scores between rounds, dramatic final reveal

The engine should orchestrate sound and LEDs but never touch the display directly -- use an abstraction so the display can be swapped.

### Display

Design for a projector. Key principles:
- **Large text** -- readable from the back of the room
- **High contrast** -- dark background, bold colors
- **Team colors everywhere** -- score bars, feedback, buttons
- **Smooth animations** -- progress bars, transitions, celebrations

Chrome kiosk mode (`chromium --kiosk http://...`) is a good way to make it fullscreen and clean.

Screens to support: question + choices, answer feedback (correct/wrong), timeout, score board, team setup, buzzer assignment.

### Multi-Client Flow

Teams play from their own devices (phones, laptops). The flow:

1. Team device connects to the game master and gets a team number
2. Team picks a name and color (colors should be unique across teams)
3. Each team presses their physical buzzer to claim it
4. During the game, the team's device shows A/B/C buttons when it's their turn

### Question Bank

Write 15-25 quiz questions. Make them fun -- CS trivia, tech lore, gotcha questions where the obvious answer is wrong. See `contracts.md` for the format.

## Things to Think About

- How does the projector display stay in sync with the game engine?
- The progress bar should animate smoothly, not in discrete jumps
- Sound comes from the game master's speakers, not the browser
- What happens when a team device disconnects mid-game?
- How does the game master control the flow (reset buzzers, skip questions)?

## Stretch Goals

- Animated effects (confetti on winner, fire border on final question)
- An insult system that roasts teams on wrong answers (static text or AI-generated)
- A touch-friendly control panel for the game master
- Spectator mode at a separate URL
