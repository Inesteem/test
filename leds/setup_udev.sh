#!/usr/bin/env bash
# Set up udev rule for the KlopfKlopf LED Controller so it can be accessed without sudo.

set -euo pipefail

RULE='SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="5035", MODE="0666", GROUP="plugdev"'
RULE_FILE="/etc/udev/rules.d/99-klopfklopf.rules"

echo "Writing udev rule to $RULE_FILE ..."
echo "$RULE" | sudo tee "$RULE_FILE" > /dev/null

echo "Reloading udev rules ..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Done. The KlopfKlopf LED Controller is now accessible without sudo."
