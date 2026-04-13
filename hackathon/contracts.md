# Interface Contracts

These are the agreed APIs between modules. Code against these, not against each other's implementations. Build mocks of the interfaces you consume so you can develop independently.

---

## Buzzer Server (runs on RPi)

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/` | `{"buzzers": [1, 2, 3], "ranking": [2, 1]}` |
| `POST` | `/reset` | `{"ok": true}` |

- `buzzers`: list of connected buzzer numbers (stable across requests)
- `ranking`: ordered list of buzzer numbers in press order (since last reset)
- After `POST /reset`, ranking is empty until someone presses again

---

## Game Master Server (runs on laptop)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/state` | Current game state as JSON (polled by team clients) |
| `POST` | `/register` | Register a team client: `{callback_url}` -> `{team_num}` |
| `POST` | `/team_config` | Submit team name+color: `{team_num, name, color, color_name}` |

The game master may also serve a browser-based display (your design choice).

---

## Team Client (runs on each team's device)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Team web UI |
| `GET` | `/answer` | Current answer: `{answer: "a"}` or `{answer: null}` |
| `POST` | `/submit` | Team submits answer: `{answer: "a"}` |
| `POST` | `/reset` | Clear stored answer (called by game master between rounds) |

---

## LED Controller

The LED controller should support at minimum:

- **Set a fixed color** (hex string like `"#ff0000"` or RGB tuple)
- **Turn off**
- **Animated modes** that run in the background: rainbow, pulse, strobe, breathe
- **Stop** any running animation
- A **no-op stub** for when hardware isn't present

---

## Sound Engine

Procedural sounds generated via `sox` (no audio files). At minimum:

| Sound | Vibe | When |
|-------|------|------|
| correct | Happy ascending | Right answer |
| wrong | Descending "wah wah" | Wrong answer |
| jeopardy_thinking | Thinking music | During answer countdown |
| times_up | Urgent beeps | Timer expired |
| dramatic_sting | "Dun dun DUNNN" | Score reveal |
| tick | Single click | Countdown (last seconds) |

Should support both blocking playback and background playback with a way to stop early.

---

## Question Format

```json
{
    "question": "What does the B in B-tree stand for?",
    "choices": {"a": "Binary", "b": "Balanced", "c": "Nobody knows for sure"},
    "answer": "c",
    "difficulty": 7
}
```

- Exactly 3 choices: `a`, `b`, `c`
- `difficulty` (1-10) is optional; the hardest question is saved for last
- Aim for 15-25 questions
