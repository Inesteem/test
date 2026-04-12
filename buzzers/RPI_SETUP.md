# Raspberry Pi Setup

The RPi serves as both **buzzer host** (physical USB buzzers) and optionally a **team client** (with LED strip and touchscreen kiosk browser).

## Quick Start

From the project root on your laptop, run:

```bash
BUZZER_RPI_HOST=<rpi-ip> ./setup_rpi_client.sh
```

This single script handles everything:
- Creates venv and installs Python packages (evdev, pyusb) if missing
- Sets up udev rules for buzzers and LED strip (one-time, needs sudo)
- Copies all code to the RPi
- Starts the buzzer server and team client
- Installs a desktop icon for kiosk mode

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BUZZER_RPI_HOST` | `10.0.0.1` | RPi IP address |
| `BUZZER_RPI_PORT` | `8888` | Buzzer server port |
| `RPI_CLIENT_PORT` | `7777` | Team client port |
| `RPI_USER` | `$(whoami)` | SSH username |

### Example

```bash
BUZZER_RPI_HOST=10.0.0.1 ./setup_rpi_client.sh
```

## What's on the RPi

```
~/buzzer/
  buzzer.py            # buzzer detection (evdev)
  buzzer_server.py     # HTTP server for buzzer state
  team_client.py       # team client HTTP server + web UI
  start-quiz-client.sh # desktop icon launcher
  QuizBuzzer.desktop   # desktop entry template
  venv/                # Python venv (evdev, pyusb)
  leds/                # LED controller library
  static/              # keyboard JS/CSS, app icon
  client.log           # team client log
  buzzer_server.log    # buzzer server log
```

## Prerequisites

- Raspberry Pi OS (Bookworm or later) with desktop environment
- Python 3.10+
- SSH access (key-based recommended)
- USB buzzers and/or LED strip plugged in
- Chromium browser (for kiosk mode)

## Udev Rules

The setup script installs these automatically (needs sudo once):

| Device | Rule File | Vendor:Product |
|--------|-----------|----------------|
| USB Buzzers | `/etc/udev/rules.d/99-buzzer.rules` | `2341:c036` |
| LED Strip | `/etc/udev/rules.d/99-klopfklopf.rules` | `18d1:5035` |

To install manually:
```bash
# On the RPi:
sudo bash -c 'echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"2341\", ATTR{idProduct}==\"c036\", MODE=\"0666\", GROUP=\"plugdev\"" > /etc/udev/rules.d/99-buzzer.rules'
sudo bash -c 'echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"18d1\", ATTR{idProduct}==\"5035\", MODE=\"0666\", GROUP=\"plugdev\"" > /etc/udev/rules.d/99-klopfklopf.rules'
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Desktop Icon (Kiosk Mode)

The setup script installs a `QuizBuzzer` desktop icon. Tapping it:

1. Starts the team client (if not running)
2. Launches Chromium in kiosk mode (fullscreen, no address bar)
3. Shows the config screen where you enter the game master IP

Chromium flags used:
```
--ozone-platform=wayland --enable-wayland-ime
--kiosk --noerrdialogs --disable-infobars --no-first-run
--enable-touch-events
--disk-cache-size=1 --aggressive-cache-discard
```

## On-Screen Keyboard

The team client embeds [simple-keyboard](https://virtual-keyboard.js.org/) for touchscreen input. It activates automatically when a text/number input is focused. No system keyboard configuration needed.

## Buzzer-Only Mode

If you only need the buzzer server (no team client or kiosk):

```bash
BUZZER_RPI_HOST=10.0.0.1 ./setup_rpi.sh
```

This copies only `buzzer.py` and `buzzer_server.py` and starts the server.

## Endpoints

### Buzzer Server (port 8888)

| Method | Path | Response |
|--------|------|----------|
| GET | `/` | `{"buzzers": [1, 2], "ranking": [2, 1]}` |
| POST | `/reset` | `{"ok": true}` |

### Team Client (port 7777)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Web UI (setup + game) |
| GET | `/client_info` | Team number, config state |
| GET | `/answer` | Current answer (polled by master) |
| POST | `/connect` | Set game master (from browser config) |
| POST | `/team_config` | Submit name+color (forwarded to master) |
| POST | `/quit` | Stop app + close kiosk browser |
| POST | `/new_game` | Reset for new game |

## Optional: Auto-Start on Boot

Create a systemd service:

```bash
sudo tee /etc/systemd/system/quiz-buzzer.service > /dev/null << 'EOF'
[Unit]
Description=Quiz Buzzer Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$HOME/buzzer
ExecStart=$HOME/buzzer/venv/bin/python3 buzzer_server.py --host 0.0.0.0 --port 8888
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now quiz-buzzer
```

## Logs

```bash
# Buzzer server
ssh user@<rpi-ip> 'tail -f ~/buzzer/buzzer_server.log'

# Team client
ssh user@<rpi-ip> 'tail -f ~/buzzer/client.log'
```
