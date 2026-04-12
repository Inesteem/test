# Team 3: Game UI

You own the game itself -- the display, the game loop, and the quiz experience. The game master runs it on a laptop; the audience sees it on a projector via a browser in Chrome kiosk mode.

## The Challenge

Build a browser-based game master display that runs in Chrome kiosk mode on a projector. The game engine runs in Python and pushes state to the browser via Server-Sent Events (SSE). The game master controls the flow with keyboard shortcuts. Teams interact via their own devices (phones/laptops running `team_client.py`).

**Why browser instead of terminal?** A curses terminal looks crude on a projector -- limited colors, fixed-width text, no smooth animations. A browser gives you full CSS animations, team-colored UI, responsive layout, and a professional quiz-show feel. The game engine stays in Python (sound and LEDs are local hardware), but the rendering moves to HTML/CSS/JS.

## Architecture

```
Python game server (quiz/web_ui.py)
  ├── Game engine (flow.py, feedback.py)
  ├── Sound (sox) -- plays on GM laptop speakers
  ├── LEDs (USB) -- drives GM laptop LED strip
  └── HTTP server (game_master_server.py)
       ├── GET /gm           -- serves gm.html
       ├── GET /gm/events    -- SSE stream (screen state push)
       ├── POST /gm/command  -- keyboard commands from browser
       ├── GET /state         -- game state for team clients
       ├── POST /register     -- client registration
       └── POST /team_config  -- team name/color submission

Chrome kiosk (static/gm.html)
  ├── EventSource('/gm/events') -- receives screen state
  ├── POST /gm/command          -- sends keyboard events
  └── Renders: question, feedback, scores, timer, fire effects
```

### The Display Protocol

The game engine never touches the browser directly. It calls methods on a `Display` protocol:

```python
class Display(Protocol):
    def draw_question(self, q, question_num, total, *, status_line, elapsed, timeout, is_final, ...): ...
    def draw_feedback(self, correct, team_name, *, insult, question_text, correct_answer): ...
    def draw_scores(self, scores, team_config, *, final): ...
    def draw_answer_reveal(self, q, *, title, insult): ...
    def draw_timeout(self, team_name, *, insult): ...
    def animate_falling_text(self, text, style, duration): ...
    def draw_ready(self, team_config): ...
    def draw_waiting(self, title, subtitle, items, status): ...
    def get_command(self, timeout=0) -> str | None: ...
    def wait_for_key(self) -> str | None: ...
    def flush_input(self): ...
```

`WebDisplay` implements this by pushing JSON state dicts over SSE and reading commands from a queue fed by `POST /gm/command`.

Each `draw_*` method serializes screen state as JSON and pushes it to connected browsers. The browser renders based on the `screen` field:

```json
{"screen": "question", "question": "What is 2+2?", "choices": {"a": "3", "b": "4", "c": "5"}, ...}
{"screen": "feedback", "correct": true, "team_name": "Foxes", "insult": "Even a clock is right twice a day", ...}
{"screen": "scores", "scores": {"1": 3, "2": -1}, "team_config": {...}, "final": false}
```

## What You Consume

You depend on modules from Team 1 and Team 2. You won't have their code for most of the hackathon, so **start by building mock/stub versions** of their interfaces (see `contracts.md`).

```python
from buzzers.buzzer_remote import RemoteBuzzerController
from leds.klopfklopf import LEDController
from sound.sound import Sound
```

Simple mocks to get you started:

- `RemoteBuzzerController`: hardcode `get_buzzers()` returning `[1, 2]`, have `get_ranking()` return a list you can manipulate with keyboard input
- `LEDController`: use `NoOpLEDController` from `leds/stub.py` (already exists)
- `Sound`: mock with `MagicMock()` or just print the sound name

## What You Need to Build

### Game Engine (Python)

The game engine runs the question loop and orchestrates sound + LEDs:

1. **Wait for buzz-in**: poll `ctrl.get_ranking()`, play background music, animate LEDs
2. **Answer countdown**: the buzzed team has N seconds to answer (via their device or GM keyboard)
3. **Feedback**: correct/wrong/timeout -- play sound, flash LEDs, resolve insult, push to display
4. **Scores**: between rounds and final reveal

The engine calls `display.draw_*()` for rendering and `display.get_command()` for input. It never touches HTML or the browser directly.

### Browser Display (HTML/CSS/JS)

A single-page app (`static/gm.html`) that connects via SSE and renders each screen type. Design for a projector:

- **Large text** (2-3em for questions, 4em+ for feedback)
- **High contrast** (dark background, bold white text)
- **Team colors** everywhere (progress bars, score bars, feedback backgrounds)
- **CSS animations** instead of frame-by-frame updates:
  - Progress bar: `requestAnimationFrame` loop driven by `elapsed`/`timeout`, re-syncs on each SSE message
  - Fire border for final question: CSS `@keyframes`
  - Falling text: CSS drop animation
  - Score bars: CSS `width` transition
- **Keyboard capture**: `document.addEventListener('keydown', ...)` sends `POST /gm/command` with `{cmd: "a"}` etc.

Screen types to handle:

| Screen | Data | Visual |
|--------|------|--------|
| `question` | question text, choices, elapsed/timeout, is_final | Centered card, A/B/C pills, progress bar, fire border on final |
| `feedback` | correct/wrong, team_name, insult, question_text | Full-screen green/red, large check/X, insult text |
| `answer_reveal` | question, correct answer, title, insult | Yellow screen, "The answer was: ..." |
| `timeout` | team_name, insult | Red screen, "TIME'S UP!" |
| `scores` | scores dict, team_config, final flag | Horizontal bar chart with team colors, winner highlight |
| `falling_text` | text, style, duration | Text drops from top to center (CSS animation) |
| `ready` | team_config | Title + team name/color list, "Press any key" |
| `waiting` | title, subtitle, items, status | Registration/config progress screen |
| `buzzer_assign` | current_name, assigned teams | "Press your buzzer!" prompt |

### Multi-client Infrastructure

Teams connect from their own devices. The flow:

1. Client runs `team_client.py` → registers with `POST /register` → gets `team_num`
2. Client shows color/name picker → submits `POST /team_config` with `{team_num, name, color}`
3. Game master waits for all teams, shows progress on display
4. Buzzer assignment: each team presses their physical buzzer
5. Game starts: clients poll `GET /state`, show A/B/C buttons when it's their turn

### Question Bank

Write 15-25 quiz questions. Each has a question string, three choices (a/b/c), and a correct answer. Make them fun:

- CS/algorithms trivia (the kind that sparks debate)
- Tech industry lore
- Programming language gotchas
- "Gotcha" questions where the obvious answer is wrong
- Pop culture meets tech

## Things to Think About

- SSE reconnection: the browser should auto-reconnect and get the current screen state on connect
- Sound must come from the game master laptop (sox), not the browser -- keep sound calls in Python
- The progress bar should animate smoothly at 60fps in the browser, not depend on 100ms SSE updates
- The `wait_for_key()` call blocks the Python game thread -- the browser must send a command to unblock it
- Use `time.sleep()` for timing in Python; use `requestAnimationFrame` for animation in the browser
- Keep the browser app self-contained in one HTML file (inline CSS + JS) for easy deployment

## Stretch Goals

- Animated SVG check/cross instead of text
- Confetti particle effect on winner reveal
- Sound effects from the browser via Web Audio (in addition to sox)
- An on-screen control panel for touch devices (large R/S/Enter buttons)
- OBS overlay mode (transparent background, just the question/timer)
- Mobile spectator view at a separate URL
