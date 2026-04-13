# Interface Contracts

These are the agreed APIs between modules. Code against these, not against each other's implementations.

---

## Buzzer Server (runs on RPi)

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/` | `{"buzzers": [1, 2, 3], "ranking": [2, 1]}` |
| `POST` | `/reset` | `{"ok": true}` |

- `buzzers`: connected buzzer numbers (stable across requests)
- `ranking`: press order since last reset

---

## Game Master Server (runs on laptop)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/state` | Current game state JSON (polled by team clients) |
| `POST` | `/register` | Register a team client: `{callback_url}` -> `{team_num}` |
| `POST` | `/team_config` | Submit team name+color: `{team_num, name, color, color_name}` |

---

## Team Client (runs on each team's device)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/answer` | Current answer: `{answer: "a"}` or `{answer: null}` |
| `POST` | `/submit` | Submit answer: `{answer: "a"}` |
| `POST` | `/reset` | Clear stored answer (called by game master between rounds) |

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

- 3 choices: `a`, `b`, `c`
- `difficulty` (1-10) optional; hardest question saved for last
- Aim for 15-25 questions
