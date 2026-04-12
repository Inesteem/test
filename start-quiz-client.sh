#!/bin/bash
# Start the quiz team client + kiosk browser on RPi.
# Launched by the desktop icon.

export XDG_RUNTIME_DIR=/run/user/1000
export WAYLAND_DISPLAY=wayland-0

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
CLIENT_PORT="${CLIENT_PORT:-7777}"

# Start team client if not already running
# No --game-master: the browser config screen handles it
if ! pgrep -f "team_client.py" > /dev/null 2>&1; then
    cd "$APP_DIR"
    ~/buzzer/venv/bin/python3 team_client.py \
        --port "$CLIENT_PORT" \
        > client.log 2>&1 &
    echo $! > client.pid
    sleep 1
fi

# Kill any existing kiosk Chromium and relaunch
pkill -f "chromium.*kiosk" 2>/dev/null || true
sleep 1
nohup chromium --ozone-platform=wayland --enable-wayland-ime \
    --disk-cache-size=1 --aggressive-cache-discard \
    --kiosk --noerrdialogs --disable-infobars --no-first-run \
    --enable-touch-events "http://localhost:${CLIENT_PORT}" > /dev/null 2>&1 &
