# Question Bundles

Drop `.json` files in this directory and they'll appear in the game's settings page as selectable question packs.

## Format

Each file is a JSON array of question objects:

```json
[
  {
    "question": "What is the meaning of life?",
    "choices": ["41", "42", "43"],
    "answer": 1,
    "difficulty": 7
  }
]
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | yes | The question text. Long questions wrap automatically. |
| `choices` | array of 3 strings | yes | Exactly three answer options. |
| `answer` | int (0, 1, or 2) | yes | Index of the correct choice in the `choices` array. |
| `difficulty` | int (1-10) | no | Difficulty rating. Defaults to 5 if omitted. The hardest question is always played last. |

## How it works

- **Question order** is randomized each game, except the highest-difficulty question which is always saved for last (the "final question" with fire animation and final countdown music).
- **Answer order** (A/B/C) is randomized per question each game, so memorizing "the answer is always B" doesn't work.
- The file name (minus `.json`) is shown in the settings page as the bundle name.

## Tips for writing good questions

- **Mix difficulty.** A few easy warm-ups (1-3), bulk in the middle (4-7), and a couple of brain-busters (8-10) for the finale.
- **Make wrong answers plausible.** The best questions are ones where all three choices seem reasonable. If one answer is obviously silly, it's less fun.
- **Keep questions concise** when possible. Very long questions wrap to multiple lines and are harder to read quickly under time pressure.
- **"Gotcha" questions** where the obvious answer is wrong are great for creating arguments and laughter (e.g., "What does the B in B-tree stand for?").
- **Audience knowledge matters.** Questions should match what the players might plausibly know (or argue about).

## Existing bundles

- `google-swe.json` — 25 questions for Google software engineers (CS trivia, Google culture, programming gotchas)
- `test-3.json` — 4 trivial questions for testing the game flow
