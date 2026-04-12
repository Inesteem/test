#!/usr/bin/env bash
# Sets up udev rule so the buzzer can be accessed without root.
set -e

RULE_FILE="/etc/udev/rules.d/99-buzzer.rules"

sudo tee "$RULE_FILE" > /dev/null <<'EOF'
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="c036", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="c036", MODE="0666"
SUBSYSTEM=="input", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="c036", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Done. Unplug and replug the buzzer, then run: python3 buzzer.py"
