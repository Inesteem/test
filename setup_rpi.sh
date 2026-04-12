#!/usr/bin/env bash
# Re-setup the buzzer server on the RPi after a reboot.
# Run from the local machine: ./setup_rpi.sh

set -euo pipefail

RPI_HOST="${BUZZER_RPI_HOST:-10.0.0.1}"
RPI_PORT="${BUZZER_RPI_PORT:-8888}"
RPI="${RPI_USER:-$(whoami)}@${RPI_HOST}"

echo ">> Copying latest buzzer files to RPi..."
scp -q buzzers/buzzer.py buzzers/buzzer_server.py "$RPI:buzzer/"

echo ">> Stopping old server (if any)..."
ssh "$RPI" 'test -f ~/buzzer/server.pid && kill "$(cat ~/buzzer/server.pid)" 2>/dev/null; exit 0'

echo ">> Starting buzzer server on RPi..."
ssh -f "$RPI" "cd ~/buzzer && ~/buzzer/venv/bin/python3 buzzer_server.py --host 0.0.0.0 --port $RPI_PORT > server.log 2>&1 & echo \$! > server.pid"

sleep 1

echo ">> Verifying from local machine..."
RESPONSE=$(curl -sf "http://${RPI_HOST}:${RPI_PORT}/") || { echo "FAILED — cannot reach RPi at ${RPI_HOST}:${RPI_PORT}"; exit 1; }
echo "   $RESPONSE"
echo ">> Done. Buzzer server is running."
