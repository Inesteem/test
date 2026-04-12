#!/usr/bin/env python3
"""Set all LEDs on the KlopfKlopf LED Controller to red."""

import usb.core
import usb.util

VENDOR_ID = 0x18D1
PRODUCT_ID = 0x5035
EP_OUT = 0x04

dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
if dev is None:
    raise SystemExit("KlopfKlopf LED Controller not found")

for iface in range(2):
    if dev.is_kernel_driver_active(iface):
        dev.detach_kernel_driver(iface)

dev.set_configuration()
usb.util.claim_interface(dev, 0)

r, g, b = 255, 0, 0
payload = bytearray([0x00, 0x03, r, g, b])
dev.write(EP_OUT, payload)

print(f"Set all LEDs to red (RGB: {r}, {g}, {b})")
