> **⚠ Archived — historical snapshot.** This document was written for the original hackathon and is frozen at that point. For current project state, see the [root README](../README.md).

# Team 2: Lights + Sound

You own the output peripherals -- the RGB LED strip and the procedural sound engine. Two independent sub-deliverables that can be split within your team.

## Part A: LED Strip

### The Challenge

There's a USB LED strip plugged into the game laptop. Your job is to figure out how to talk to it and build a controller library with animation support.

### What You Know

- Vendor ID: `0x18d1`, Product ID: `0x5035`
- You'll want `pyusb` to communicate with it
- **The device name is a hint.** Run `lsusb -v` (Linux) or use `pyusb` to read the device descriptor. The product name will point you toward existing source code or documentation within the company. Start there.

### What You Need to Build

An `LEDController` class that supports setting a fixed color, turning off, and several animation modes that run in background threads.

See `contracts.md` for the exact class interface.

### Things to Think About

- Each animated mode should run in its own daemon thread
- Starting a new animation should cleanly stop the previous one (no zombie threads, no flicker)
- Color parsing: support both hex strings (`"#ff0000"`) and RGB tuples `(255, 0, 0)`
- `open()` may need to handle kernel driver detachment on Linux (not needed on macOS)
- Context manager support (`with LEDController() as leds:`) is nice to have for clean resource management

### Stretch Goals

- Color interpolation utilities (lerp between two colors)
- More animation modes (fire, sparkle, color wipe)
- Gamma correction for perceptually smooth brightness curves

---

## Part B: Sound Engine

### The Challenge

Build a procedural sound effects library using `sox`. All sounds are generated from sine waves -- no audio files.

### What You Know

- `sox` provides a `play` command that can synthesize tones: `play -qn synth <duration> sine <freq>`
- A melody is a sequence of `(frequency_hz, duration_seconds)` tuples
- `subprocess.run` for blocking playback, `threading.Thread` for background playback
- Note frequencies: A4 = 440 Hz, C4 = 261.63 Hz, etc. (look up a note frequency table)

### What You Need to Build

A `Sound` class with named melodies and both blocking and background playback.

See `contracts.md` for the exact class interface.

### The Melodies

You need at least these seven sounds. The names and vibes:

| Name | Duration | Vibe | When it plays |
|------|----------|------|---------------|
| `correct` | <1s | Happy ascending arpeggio | Right answer |
| `wrong` | ~1.5s | Descending "wah wah" | Wrong answer |
| `jeopardy_thinking` | ~30s | The classic Jeopardy thinking music | During answer countdown |
| `final_countdown` | ~20s | Dramatic countdown riff | Last question only |
| `times_up` | ~1s | Urgent beeps | Timer expired |
| `dramatic_sting` | ~1.5s | "Dun dun DUNNN" | Score reveal |
| `tick` | <0.1s | Single click/beep | Countdown (last 10s) |

Compose these from sine waves. They don't need to be perfect reproductions -- they need to be recognizable and fun.

### Things to Think About

- Background playback: spawn a daemon thread, return a handle with a `stop()` method
- The stop mechanism needs to interrupt a melody mid-note (use a `threading.Event`)
- `sox` may not be installed -- raise a clear error in `__init__` if `play` isn't on PATH
- Volume control: sox supports `vol <float>` in the effects chain
- Fade in/out on each note prevents clicking artifacts: `fade 0.01 <duration> 0.01`

### Stretch Goals

- Chords (multiple simultaneous frequencies)
- Different waveforms (square, sawtooth)
- A CLI tool (`python3 -m sound correct`) to preview sounds
