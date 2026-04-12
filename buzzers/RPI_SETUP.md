# Raspberry Pi Buzzer Server Setup

The buzzer server runs on a Raspberry Pi, detecting USB buzzer presses and exposing them over HTTP as JSON for the quiz to poll.

Default RPi: `10.0.0.1` (configurable via env var or settings UI).

## What's on the RPi

```
~/buzzer/
  buzzer.py          # buzzer detection logic (evdev)
  buzzer_server.py   # HTTP server wrapping buzzer logic
  venv/              # Python venv with evdev installed
  server.log         # stdout/stderr from last server run
  server.pid         # PID of running server (used by setup_rpi.sh)
```

## How it was set up

1. SSH access as `user@10.0.0.1` (key-based auth)
2. Created `~/buzzer/` and a Python venv inside it:
   ```
   mkdir -p ~/buzzer
   python3 -m venv ~/buzzer/venv
   ~/buzzer/venv/bin/pip install evdev
   ```
3. Copied `buzzer.py` and `buzzer_server.py` to `~/buzzer/`
4. RPi has Python 3.13.5, runs Debian (PEP 668 managed, hence the venv)
5. Two buzzers are connected and detected without any udev rules (the RPi user already has input device access)

## Starting the server after reboot

The server does not auto-start. Run the setup script from the project root:

```bash
./setup_rpi.sh
```

To use a different RPi address or port:

```bash
BUZZER_RPI_HOST=10.0.0.50 BUZZER_RPI_PORT=9000 ./setup_rpi.sh
```

Output looks like:

```
>> Copying latest buzzer files to RPi...
>> Stopping old server (if any)...
>> Starting buzzer server on RPi...
>> Verifying from local machine...
   {"buzzers": [1, 2], "ranking": []}
>> Done. Buzzer server is running.
```

## Configuration

The RPi address and port can be set in three ways (highest priority first):

1. **Settings UI** — edit host/port fields in the in-game settings screen at startup
2. **Environment variables** — `BUZZER_RPI_HOST` and `BUZZER_RPI_PORT`
3. **Defaults** — `10.0.0.1:8888`

Both `setup_rpi.sh` and the quiz UI respect these env vars.

## Optional: auto-start on boot via systemd

To make the server survive reboots without running `setup_rpi.sh`, create a systemd unit:

```bash
sudo tee /etc/systemd/system/buzzer-server.service > /dev/null << 'EOF'
[Unit]
Description=Buzzer HTTP Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/buzzer
ExecStart=/home/pi/buzzer/venv/bin/python3 buzzer_server.py --host 0.0.0.0 --port 8888
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable buzzer-server
sudo systemctl start buzzer-server
```

## Endpoints

| Method | Path     | Response                                      |
|--------|----------|-----------------------------------------------|
| GET    | `/`      | `{"buzzers": [1, 2], "ranking": [2, 1]}`     |
| POST   | `/reset` | `{"ok": true}`                                |

## Local dependencies (macOS)

The quiz machine needs these installed via Homebrew:

- `libusb` — USB backend for pyusb (LED controller)
- `sox` — audio synthesis for sound effects

```bash
brew install libusb sox
```

Python deps are in the local venv (`./venv`):

```bash
python3 -m venv venv
venv/bin/pip install pyusb
```
