# Team 2: Lights + Sound

You own the output peripherals -- the RGB LED strip and sound effects. Two independent deliverables that can be split within your team.

## Part A: LED Strip

### The Problem

A USB LED strip needs to react to the game -- flash team colors, strobe during countdowns, celebrate wins.

### What You Know

- Vendor ID: `0x18d1`, Product ID: `0x5035`
- **The device name is a clue.** Read the USB descriptor -- it will help you find the protocol.

### What You Need to Build

A controller that supports:
- Fixed color and off
- Animated modes (rainbow, pulse, strobe, breathe) running in the background
- Clean switching between animations
- A no-op stub for when hardware isn't present

---

## Part B: Sound

### The Problem

Build sound effects for the game -- correct/wrong jingles, thinking music, countdown tick, dramatic reveals. Up to you how to generate or source them.

### What You Need to Build

Named sounds the game engine can trigger, with both blocking and background playback and a way to stop early.

| Sound | When |
|-------|------|
| correct | Right answer |
| wrong | Wrong answer |
| thinking music | During answer countdown |
| times up | Timer expired |
| dramatic sting | Score reveal |
| tick | Countdown |

## Stretch Goals

- Additional LED modes (fire, candle, sparkle)
- Chords or layered audio
- A preview tool to audition sounds
