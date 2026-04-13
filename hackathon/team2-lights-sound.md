# Team 2: Lights + Sound

You own the output peripherals -- the RGB LED strip and the procedural sound engine. These are two independent sub-deliverables that can be split within your team.

## Part A: LED Strip

### The Problem

There's a USB LED strip that needs to react to the game -- flash team colors on correct answers, strobe urgently during countdowns, celebrate on wins.

### What You Know

- Vendor ID: `0x18d1`, Product ID: `0x5035`
- **The device name is a clue.** Read the USB descriptor -- the product name will help you find documentation or source code for the protocol.
- The strip can be plugged into the game master laptop or team devices

### What You Need to Build

A controller library with:
- Fixed color and off
- Animated modes: rainbow, pulse, strobe, breathe (running in the background)
- Clean switching between animations (no flicker, no zombie threads)
- A no-op stub for when the hardware isn't present

See `contracts.md` for the interface.

### Stretch Goals

- Color interpolation (smooth transitions between colors)
- Additional modes (fire, candle, sparkle)

---

## Part B: Sound Engine

### The Problem

Build a procedural sound effects library. All sounds are generated from sine waves using `sox` -- no audio files needed.

### What You Know

- `sox` can synthesize tones from the command line
- A melody is a sequence of frequencies and durations
- Sound plays on the game master's speakers, not in the browser

### What You Need to Build

A sound library with named effects (correct, wrong, thinking music, timeout, dramatic sting, tick) that supports both blocking and background playback with a way to stop early.

See `contracts.md` for the sounds needed.

### Things to Think About

- How do you stop a melody mid-playback?
- How do you prevent audio clicks/pops between notes?
- What if `sox` isn't installed?

### Stretch Goals

- Chords (multiple simultaneous frequencies)
- A CLI preview tool to audition sounds
- Different waveforms (square, sawtooth)
