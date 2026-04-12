# Insult Packs

Drop `.json` files in this directory and they'll appear in the game's settings page as selectable insult styles. When enabled, players get roasted after every answer, timeout, and failure.

## Format

Each file is a JSON object with a display name and five category arrays:

```json
{
  "name": "My Roast Style",
  "correct_fast": [
    "Lucky guess.",
    "Even a stopped clock..."
  ],
  "correct_slow": [
    "Took you long enough."
  ],
  "wrong": [
    "That was embarrassing."
  ],
  "timeout": [
    "Anyone awake?"
  ],
  "nobody": [
    "All of you failed."
  ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | no | Display name in settings. Defaults to the file name if omitted. |
| `correct_fast` | array of strings | no | Shown when a team answers correctly within 3 seconds. Should be backhanded compliments or cynical praise. |
| `correct_slow` | array of strings | no | Shown when a team answers correctly but took their time. Impatient jabs. |
| `wrong` | array of strings | no | Shown when a team answers incorrectly. Savage burns. |
| `timeout` | array of strings | no | Shown when a team's answer timer expires. Passive-aggressive commentary. |
| `nobody` | array of strings | no | Shown as falling text when no team gets the answer. Collective shame. Displayed in a dramatic falling animation before the answer reveal. |

All categories are optional — if a category is missing or empty, no insult is shown for that event.

## When insults appear

| Game moment | Category used | How it's shown |
|---|---|---|
| Correct answer in <3s | `correct_fast` | Dimmed text below the "CORRECT!" message |
| Correct answer (slow) | `correct_slow` | Dimmed text below the "CORRECT!" message |
| Wrong answer | `wrong` | Dimmed text below the "WRONG!" message |
| Answer timer expires | `timeout` | Dimmed text below the "TIME'S UP!" message |
| Nobody gets the answer | `nobody` | Falls from top of screen before the answer reveal |

## What changes in insult mode

- The "SAVAGE!" / "LIGHTNING!" falling text animation on fast correct answers is **suppressed** — replaced by the cynical insult text instead.
- Everything else (LEDs, sounds, scoring) works the same.

## Tips for writing insult packs

- **Stay in character.** The best packs have a consistent voice (drill sergeant, disappointed parent, Gordon Ramsay, passive-aggressive coworker).
- **Vary length.** Mix short punchy lines ("Pathetic.") with longer ones for variety.
- **`correct_fast` is the trickiest category.** The team just got it right AND was fast — the insult needs to acknowledge their success while undercutting it. Backhanded compliments work best.
- **`nobody` lines should be collective.** They address the whole room, not one team.
- **6-8 lines per category** gives enough variety that repeats are rare in a 25-question game.
- **Test your pack** — select it in settings and play through a few rounds to feel the timing.

## Existing packs

- `default.json` — General-purpose roasts, workplace-friendly cynicism
- `gordon-ramsay.json` — Hell's Kitchen energy ("You absolute donut.")
