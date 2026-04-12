# Quiz Game Sound Effects

Command-line sound effects for a terminal-based quiz game, generated
programmatically with `sox` — no audio files needed.

## Setup

```bash
# Linux
sudo apt install sox

# macOS
brew install sox
```

## Usage

```bash
# From the buzzers/ directory:
python3 -m sound                      # list available sounds
python3 -m sound correct              # play a sound
python3 -m sound wrong --vol 0.3      # adjust volume (0.0-1.0)
python3 -m sound all                  # demo everything
```

From Python:

```python
from sound import Sound

snd = Sound(volume=0.6)
snd.correct()
handle = snd.jeopardy_thinking(background=True)
# ... later ...
handle.stop()
```

## Available Sounds and When They're Used

### `jeopardy_thinking`
The classic Jeopardy "Think!" melody (~30 seconds). Plays as background music
during the answer countdown after a team buzzes in. Stopped when the team
answers, times out, or the game master resets. Used for all questions except
the last one.

### `final_countdown`
The Europe intro riff (~20 seconds). Replaces `jeopardy_thinking` for the
**last question only**, creating a "boss level" feel. When the music ends at
~20s, the remaining countdown is pure silence + ticks, which builds tension.

### `correct`
Short ascending C-E-G arpeggio. Plays immediately after a correct answer,
paired with a green LED strobe burst.

### `wrong`
Descending "wah wah" buzzer. Plays after an incorrect answer, paired with
red LED strobe and candle "flames of failure" effect.

### `times_up`
Three urgent beeps. Plays when the answer timer expires. Distinct from
`wrong` — signals inaction, not a bad answer.

### `dramatic_sting`
"Dun dun DUNNN" low hit. Plays during the final score reveal, paired with
an amber candle LED effect for suspense.

### `tick`
Single short beep. Plays once per second during the **last 10 seconds** of
the answer countdown, layered on top of the background music. Creates
escalating urgency as time runs out.
