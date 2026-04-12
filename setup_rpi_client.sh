#!/usr/bin/env bash
# Deploy buzzer server + team client to the RPi.
# Run from the project root: ./setup_rpi_client.sh
#
# Starts two services on the RPi:
#   1. Buzzer server on port $RPI_BUZZER_PORT (default 8888)
#   2. Team client on port $RPI_CLIENT_PORT (default 7777)
#
# The team client auto-registers with the game master.

set -euo pipefail

RPI_HOST="${BUZZER_RPI_HOST:-10.0.0.1}"
RPI_BUZZER_PORT="${BUZZER_RPI_PORT:-8888}"
RPI_CLIENT_PORT="${RPI_CLIENT_PORT:-7777}"
GM_HOST="${GM_HOST:-}"
GM_PORT="${GM_PORT:-9000}"
RPI="${RPI_USER:-$(whoami)}@${RPI_HOST}"
USE_LEDS="${RPI_LEDS:-}"

if [ -z "$GM_HOST" ]; then
    echo "Usage: GM_HOST=<game-master-ip> ./setup_rpi_client.sh"
    echo ""
    echo "Environment variables:"
    echo "  GM_HOST           Game master IP (required)"
    echo "  GM_PORT           Game master port (default: 9000)"
    echo "  BUZZER_RPI_HOST   RPi address (default: 10.0.0.1)"
    echo "  BUZZER_RPI_PORT   Buzzer server port (default: 8888)"
    echo "  RPI_CLIENT_PORT   Team client port (default: 7777)"
    echo "  RPI_LEDS          Set to '1' to enable LED strip on RPi"
    exit 1
fi

echo ">> Creating directory structure on RPi..."
ssh "$RPI" 'mkdir -p ~/buzzer/leds ~/buzzer/static'

echo ">> Copying buzzer server files..."
scp -q buzzers/buzzer.py buzzers/buzzer_server.py "$RPI:buzzer/"

echo ">> Copying team client files..."
scp -q team_client.py "$RPI:buzzer/"
scp -q leds/__init__.py leds/stub.py leds/klopfklopf.py "$RPI:buzzer/leds/"
scp -q static/simple-keyboard.min.js static/simple-keyboard.css static/keyboard.js "$RPI:buzzer/static/"

echo ">> Stopping old processes..."
ssh "$RPI" '
    test -f ~/buzzer/buzzer.pid && kill "$(cat ~/buzzer/buzzer.pid)" 2>/dev/null; true
    test -f ~/buzzer/server.pid && kill "$(cat ~/buzzer/server.pid)" 2>/dev/null; true
    test -f ~/buzzer/client.pid && kill "$(cat ~/buzzer/client.pid)" 2>/dev/null; true
'

echo ">> Starting buzzer server on :${RPI_BUZZER_PORT}..."
ssh -f "$RPI" "cd ~/buzzer && ~/buzzer/venv/bin/python3 buzzer_server.py --host 0.0.0.0 --port $RPI_BUZZER_PORT > buzzer_server.log 2>&1 & echo \$! > buzzer.pid"
sleep 1

echo ">> Verifying buzzer server..."
RESPONSE=$(curl -sf "http://${RPI_HOST}:${RPI_BUZZER_PORT}/") || { echo "FAILED — buzzer server not reachable"; exit 1; }
echo "   $RESPONSE"

LEDS_FLAG=""
if [ -n "$USE_LEDS" ]; then
    LEDS_FLAG="--leds"
    echo ">> LED strip enabled"
fi

echo ">> Starting team client on :${RPI_CLIENT_PORT} (game master: ${GM_HOST}:${GM_PORT})..."
ssh -f "$RPI" "cd ~/buzzer && ~/buzzer/venv/bin/python3 team_client.py --game-master ${GM_HOST}:${GM_PORT} --port ${RPI_CLIENT_PORT} ${LEDS_FLAG} > client.log 2>&1 & echo \$! > client.pid"
sleep 2

echo ">> Verifying team client..."
curl -sf "http://${RPI_HOST}:${RPI_CLIENT_PORT}/" > /dev/null || { echo "FAILED — team client not reachable"; exit 1; }
echo "   Team client running at http://${RPI_HOST}:${RPI_CLIENT_PORT}"

echo ""
echo ">> Done! RPi is running:"
echo "   Buzzer server: http://${RPI_HOST}:${RPI_BUZZER_PORT}"
echo "   Team client:   http://${RPI_HOST}:${RPI_CLIENT_PORT}"
echo ""
echo "   Open http://${RPI_HOST}:${RPI_CLIENT_PORT} on a phone/browser to play."
echo "   Logs: ssh $RPI 'tail -f ~/buzzer/client.log'"
