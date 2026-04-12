# KlopfKlopf LED Controller

Python library for the KlopfKlopf USB LED strip (`18d1:5035`, ATmega32-based).

## Prerequisites

- Python 3.10+
- [PyUSB](https://pyusb.github.io/pyusb/) (`pip install pyusb`)
- libusb backend (`apt install libusb-1.0-0` on Linux, `brew install libusb` on macOS)

## Setup

### Linux

The device requires a udev rule to be accessible without root. Run the included setup script once:

```bash
./setup_udev.sh
```

This creates `/etc/udev/rules.d/99-klopfklopf.rules` granting access to the `plugdev` group. You may need to unplug and replug the device afterward.

### macOS

No special setup needed beyond `brew install libusb`. The `detach_kernel_driver` call is automatically skipped on macOS where it is not supported.

## Quick start

```python
from leds.klopfklopf import LEDController

with LEDController() as leds:
    leds.set_color("#ff0000")   # solid red
    leds.set_color((0, 255, 0)) # solid green via RGB tuple

    leds.rainbow(["#ff0000", "#00ff00", "#0000ff"], period=3.0)
    # ... runs in background until the next call

    leds.off()
```

## Color format

All methods that accept a color take either:

- **Hex string**: `"#ff0000"`, `"#f00"` (3-char shorthand), `"ff0000"` (no `#`)
- **RGB tuple**: `(255, 0, 0)` — values are clamped to 0-255

## How the quiz game uses LEDs

The quiz UI choreographs all 6 LED modes across the game flow:

| Game moment | LED mode | Details |
|---|---|---|
| Color picker | `breathe` | Preview color with gentle breathing (period 2s) |
| Buzz-in wait | `rainbow` | Cycles team colors (period 3s) |
| Answer timer (early) | `breathe` | Calm, team color (period 3s) |
| Answer timer (mid) | `pulse` | Urgency building, team color (period 1s) |
| Answer timer (last 5s) | `strobe` | Panic mode, team color (6 Hz) |
| Correct answer | `strobe` → solid | Burst in team color (8 Hz, 0.5s) then solid green |
| Wrong answer | `strobe` → `candle` | Red strobe (4 Hz, 0.3s) then red/orange candle |
| Time's up | `strobe` → `breathe` | Rapid red strobe then dim red breathe |
| Scores (mid-game) | `breathe` | Leading team's color (period 3s) |
| Final scores reveal | `candle` | Amber suspense (intensity 0.5) |
| Winner announced | `strobe` → `breathe` | Winner color burst (8 Hz, 1s) then breathe |

## API

### `LEDController`

Use as a context manager or call `open()` / `close()` manually.

```python
# Context manager (preferred)
with LEDController() as leds:
    ...

# Manual lifecycle
leds = LEDController()
leds.open()
# ... use leds ...
leds.close()
```

All animated modes run in a background thread. Calling any mode (or `stop()`) automatically stops the previous animation.

---

### `set_color(color)`

Set all LEDs to a fixed color.

```python
leds.set_color("#ff6600")
leds.set_color((255, 102, 0))
```

---

### `off()`

Turn all LEDs off (shorthand for `set_color((0, 0, 0))`).

---

### `rainbow(colors, period=2.0, fps=60)`

Smoothly cycle through a list of colors using linear interpolation.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `colors` | `list[Color]` | *required* | At least 2 colors to cycle through |
| `period` | `float` | `2.0` | Seconds for one full cycle |
| `fps` | `int` | `60` | Animation frame rate |

```python
leds.rainbow(["#ff0000", "#00ff00", "#0000ff"], period=4.0)
```

---

### `pulse(colors, period=1.5, fps=60)`

Pulse through colors by ramping brightness up then down using a sine curve. Each color gets one full pulse (dark -> bright -> dark) before moving to the next.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `colors` | `list[Color]` | *required* | At least 1 color |
| `period` | `float` | `1.5` | Seconds per pulse (one up+down cycle) |
| `fps` | `int` | `60` | Animation frame rate |

```python
leds.pulse(["#ff0000", "#0000ff"], period=2.0)
```

---

### `strobe(color, hz=10.0)`

Rapid flash alternating between the given color and black.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `color` | `Color` | *required* | The flash color |
| `hz` | `float` | `10.0` | Flashes per second |

```python
leds.strobe("#ffffff", hz=15)
```

---

### `candle(color=(255, 147, 41), intensity=0.4, fps=30)`

Simulate a flickering candle by randomly varying brightness with smooth interpolation.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `color` | `Color` | `(255, 147, 41)` | Base flame color (default: warm orange) |
| `intensity` | `float` | `0.4` | Flicker amount, 0.0 (steady) to 1.0 (dramatic) |
| `fps` | `int` | `30` | Animation frame rate |

```python
leds.candle()                              # default warm flame
leds.candle("#ff2200", intensity=0.7)      # aggressive red flicker
```

---

### `breathe(color, period=4.0, fps=60)`

Gentle breathing effect with gamma-corrected cosine easing for a natural feel (similar to the Apple sleep indicator).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `color` | `Color` | *required* | The breathing color |
| `period` | `float` | `4.0` | Seconds for one full breath (in + out) |
| `fps` | `int` | `60` | Animation frame rate |

```python
leds.breathe("#0000ff", period=3.0)
```

---

### `stop()`

Stop the current animation without changing the LEDs. The strip stays at whatever color it was showing when `stop()` was called.

## Command-line tool

The CLI (`cli.py`) exposes all library modes. Animated modes run until Ctrl+C and turn LEDs off on exit.

```bash
# Fixed color (hex or r,g,b)
python3 -m leds.cli on '#ff0000'
python3 -m leds.cli on 255,0,0

# Turn off
python3 -m leds.cli off

# Rainbow cycle
python3 -m leds.cli rainbow '#ff0000' '#00ff00' '#0000ff' -p 3.0

# Pulse
python3 -m leds.cli pulse '#ff0000' '#0000ff' -p 2.0

# Strobe
python3 -m leds.cli strobe '#ffffff' --hz 15

# Candle flicker
python3 -m leds.cli candle
python3 -m leds.cli candle '#ff2200' -i 0.7

# Breathe
python3 -m leds.cli breathe '#0000ff' -p 3.0
```

Run `python3 -m leds.cli <command> --help` for full option details.

## USB protocol

The controller uses a vendor-specific bulk transfer protocol on endpoint `0x04 OUT`:

```
Payload: [0x00, 0x03, R, G, B]
```

where R, G, B are single bytes (0-255) setting the color for the entire strip.

## Hardware

- **Vendor**: Google LLC (`18d1`)
- **Product**: KlopfKlopf LED Controller (`5035`)
- **MCU**: ATmega32
- **Interface**: USB 1.1, vendor-specific class, bulk transfers
- **Max packet size**: 64 bytes
