#!/usr/bin/env bash
# Deploy buzzer server + team client to the RPi.
# Run from the project root: ./setup_rpi_client.sh
#
# Handles both first-time setup (venv, packages, udev) and re-deployment.
# Starts two services on the RPi:
#   1. Buzzer server on port $RPI_BUZZER_PORT (default 8888)
#   2. Team client on port $RPI_CLIENT_PORT (default 7777)
#
# The team client shows a browser config screen for game master address.

set -euo pipefail

RPI_HOST="${BUZZER_RPI_HOST:-10.0.0.1}"
RPI_BUZZER_PORT="${BUZZER_RPI_PORT:-8888}"
RPI_CLIENT_PORT="${RPI_CLIENT_PORT:-7777}"
RPI="${RPI_USER:-$(whoami)}@${RPI_HOST}"

echo "=== Quiz Buzzer RPi Setup ==="
echo "    Target: $RPI"
echo ""

# ── 1. Bootstrap: venv + packages ──

echo ">> Checking RPi environment..."
ssh "$RPI" '
    # Create directories
    mkdir -p ~/buzzer/leds ~/buzzer/static

    # Create venv if missing
    if [ ! -d ~/buzzer/venv ]; then
        echo "   Creating Python venv..."
        python3 -m venv ~/buzzer/venv
    fi

    # Install required packages
    NEED_INSTALL=""
    ~/buzzer/venv/bin/python3 -c "import evdev" 2>/dev/null || NEED_INSTALL="evdev"
    ~/buzzer/venv/bin/python3 -c "import usb.core" 2>/dev/null || NEED_INSTALL="$NEED_INSTALL pyusb"

    if [ -n "$NEED_INSTALL" ]; then
        echo "   Installing: $NEED_INSTALL"
        ~/buzzer/venv/bin/pip install --quiet $NEED_INSTALL
    else
        echo "   Packages OK (evdev, pyusb)"
    fi
'

# ── 2. Udev rules ──

echo ">> Checking udev rules..."
ssh "$RPI" '
    CHANGED=""

    # Buzzer udev rule
    BUZZER_RULE="SUBSYSTEM==\"usb\", ATTR{idVendor}==\"2341\", ATTR{idProduct}==\"c036\", MODE=\"0666\", GROUP=\"plugdev\""
    if [ ! -f /etc/udev/rules.d/99-buzzer.rules ]; then
        echo "   Installing buzzer udev rule..."
        echo "$BUZZER_RULE" | sudo tee /etc/udev/rules.d/99-buzzer.rules > /dev/null
        CHANGED=1
    fi

    # LED strip udev rule
    LED_RULE="SUBSYSTEM==\"usb\", ATTR{idVendor}==\"18d1\", ATTR{idProduct}==\"5035\", MODE=\"0666\", GROUP=\"plugdev\""
    if [ ! -f /etc/udev/rules.d/99-klopfklopf.rules ]; then
        echo "   Installing LED strip udev rule..."
        echo "$LED_RULE" | sudo tee /etc/udev/rules.d/99-klopfklopf.rules > /dev/null
        CHANGED=1
    fi

    if [ -n "$CHANGED" ]; then
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        echo "   Udev rules reloaded"
    else
        echo "   Udev rules OK"
    fi
'

# ── 3. Copy files ──

echo ">> Copying files to RPi..."
scp -q buzzers/buzzer.py buzzers/buzzer_server.py "$RPI:buzzer/"
scp -q team_client.py "$RPI:buzzer/"
scp -q leds/__init__.py leds/stub.py leds/klopfklopf.py "$RPI:buzzer/leds/"
scp -q static/simple-keyboard.min.js static/simple-keyboard.css static/keyboard.js static/quiz-icon.svg "$RPI:buzzer/static/"
scp -q start-quiz-client.sh QuizBuzzer.desktop "$RPI:buzzer/"

# ── 4. Stop old processes ──

echo ">> Stopping old processes..."
ssh "$RPI" 'test -f ~/buzzer/client.pid && kill "$(cat ~/buzzer/client.pid)" 2>/dev/null; true'
ssh "$RPI" 'test -f ~/buzzer/buzzer.pid && kill "$(cat ~/buzzer/buzzer.pid)" 2>/dev/null; true'
sleep 0.5

# ── 5. Start services ──

echo ">> Starting buzzer server on :${RPI_BUZZER_PORT}..."
ssh -f "$RPI" "cd ~/buzzer && ~/buzzer/venv/bin/python3 buzzer_server.py --host 0.0.0.0 --port $RPI_BUZZER_PORT > buzzer_server.log 2>&1 & echo \$! > buzzer.pid"
sleep 1

echo ">> Checking buzzer server..."
if RESPONSE=$(curl -sf "http://${RPI_HOST}:${RPI_BUZZER_PORT}/"); then
    echo "   $RESPONSE"
else
    echo "   Buzzer server not responding (no buzzers plugged in?). Continuing anyway."
fi

echo ">> Starting team client on :${RPI_CLIENT_PORT}..."
ssh -f "$RPI" "cd ~/buzzer && ~/buzzer/venv/bin/python3 team_client.py --port ${RPI_CLIENT_PORT} > client.log 2>&1 & echo \$! > client.pid"
sleep 2

echo ">> Verifying team client..."
curl -sf "http://${RPI_HOST}:${RPI_CLIENT_PORT}/" > /dev/null || { echo "   FAILED — team client not reachable"; exit 1; }
echo "   Running at http://${RPI_HOST}:${RPI_CLIENT_PORT}"

# ── 6. Desktop icon ──

echo ">> Installing desktop icon..."
ssh "$RPI" '
    cd ~/buzzer
    sed -i "s|DEPLOY_APP_DIR|$HOME/buzzer|g" start-quiz-client.sh 2>/dev/null || true
    chmod +x start-quiz-client.sh
    sed "s|DEPLOY_APP_DIR|$HOME/buzzer|g" QuizBuzzer.desktop > ~/Desktop/QuizBuzzer.desktop
    chmod +x ~/Desktop/QuizBuzzer.desktop
    gio set ~/Desktop/QuizBuzzer.desktop metadata::trusted true 2>/dev/null || true
'

echo ""
echo "=== Done! ==="
echo "  Buzzer server:  http://${RPI_HOST}:${RPI_BUZZER_PORT}"
echo "  Team client:    http://${RPI_HOST}:${RPI_CLIENT_PORT}"
echo "  Desktop icon:   QuizBuzzer"
echo ""
echo "  Open the browser or tap the desktop icon to configure the game master."
echo "  Logs: ssh $RPI 'tail -f ~/buzzer/client.log'"
