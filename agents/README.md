# AI Agent Definitions

Drop `.json` files in this directory to add AI-powered insult personalities to the quiz game. Each agent uses Claude (via the `claude` CLI in headless mode) with a custom system prompt that defines its character.

Agents appear in the settings page after the static insult packs, prefixed with "AI:".

## Format

```json
{
  "name": "Agent Display Name",
  "description": "Brief description shown in documentation",
  "system_prompt": "You are... [full system prompt defining personality and output rules]"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Display name shown in settings (e.g., "Gordon Ramsay") |
| `description` | string | yes | One-line description of the personality |
| `system_prompt` | string | yes | Full system prompt sent to Claude. This is the entire personality definition. |

## Writing a good system prompt

The system prompt must include these elements:

1. **Character identity** — Who is the AI? ("You are Gordon Ramsay", "You are a drill sergeant")
2. **Context** — "...commentating a quiz buzzer game for software engineers"
3. **Output format** — Always include: "STRICT LIMIT: 60 characters max, one short sentence."
4. **Output rules** — Always include: "Output ONLY the comment — no quotes, no explanation, no preamble."
5. **Character traits** — Specific catchphrases, vocabulary, stylistic quirks
6. **Correct answer handling** — How to react when someone gets it right (backhanded praise works well)

The game sends prompts like:
```
Event: wrong
Question: What is 2+2?
Team: Team Potato
Their answer: 5
Correct answer: 4
WRONG answer. Destroy them.
```

The AI should respond with just the insult text, nothing else.

## Tips

- **Max 60 characters** keeps insults readable on the terminal and fits on a single line. The shipped agents enforce this with "STRICT LIMIT: 60 characters max" in their system prompts. Add a gentle threat like "If your response exceeds 60 characters, you have failed" — Haiku takes rules more seriously when framed as failure conditions.
- **"Never repeat yourself"** is important — the model maintains conversation history across the game.
- **Test your agent** with `./setup_insult_ai.sh` or by running a game with the ai-bait question pack.
- **Capitalize emphasis** works great in terminal UI ("It's WRONG! Get out!")
- **Stay PG-13** unless your audience is specifically okay with stronger language.

## Existing agents

| Agent | Style |
|-------|-------|
| `roast-master.json` | Classic comedy roast — savage burns and backhanded compliments |
| `gordon-ramsay.json` | Hell's Kitchen energy — screaming chef |
| `disappointed-parent.json` | Passive-aggressive guilt trips |
| `drill-sergeant.json` | Full Metal Jacket — military screaming |
| `shakespeare.json` | Elizabethan insults in iambic contempt |

## Requirements

- `claude` CLI must be installed and authenticated (`claude /login`)
- Uses Haiku model for fast responses (~3-8 seconds per insult)
- No API key needed — uses existing Claude Code auth
