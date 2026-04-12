#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Set up a udev rule for the KlopfKlopf LED Controller (Linux only).
#
# WHY THIS IS NEEDED
#   On Linux, raw USB devices are owned by root by default. Without this
#   rule the quiz game would need to run as root (sudo) to talk to the LED
#   strip — which is undesirable.
#
# WHAT THIS SCRIPT DOES
#   It writes a single one-line file to /etc/udev/rules.d/ that tells the
#   kernel: "when a USB device with vendor 18d1 and product 5035 is plugged
#   in, make it readable and writable by everyone (mode 0666)."
#
#   The rule targets ONLY this specific device. It does not change
#   permissions on any other USB device, does not install software, and
#   does not modify your system beyond that one file.
#
# WHAT SUDO IS USED FOR
#   Writing to /etc/udev/rules.d/ requires root. After the rule is in
#   place, the LED controller works without root for all users, forever.
#   You only need to run this script once.
#
# THE RULE (one line)
#   SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="5035",
#   MODE="0666", GROUP="plugdev"
#
# CAN I SKIP THIS?
#   Yes. LEDs are entirely optional — the quiz game detects a missing LED
#   controller and runs without it. You only need this if you want the
#   RGB light show.
#
# macOS: not needed. libusb access works without extra permissions.
# ---------------------------------------------------------------------------

set -euo pipefail

RULE='SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="5035", MODE="0666", GROUP="plugdev"'
RULE_FILE="/etc/udev/rules.d/99-klopfklopf.rules"

echo "This script writes a udev rule so the LED controller can be used without sudo."
echo ""
echo "  Rule:   $RULE"
echo "  File:   $RULE_FILE"
echo ""
echo "It only affects USB device 18d1:5035 (KlopfKlopf LED Controller)."
echo ""

echo "Writing udev rule to $RULE_FILE ..."
echo "$RULE" | sudo tee "$RULE_FILE" > /dev/null

echo "Reloading udev rules ..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "Done. Unplug and replug the LED strip — it will now work without sudo."
