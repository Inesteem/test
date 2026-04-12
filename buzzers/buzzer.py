#!/usr/bin/env python3
"""Detect button presses from multiple Sebastian Schuchmann USB Buzzers.

Provides a BuzzerController that collects presses in a background thread
and exposes the current ranking (press order) to the caller.
"""

import select
import threading

import evdev
from evdev import ecodes

VENDOR_ID = 0x2341
PRODUCT_ID = 0xC036


def find_buzzers():
    """Find all connected buzzer keyboard event devices.

    Returns a list of (buzzer_number, InputDevice) tuples, sorted by
    physical USB path for stable enumeration across runs.
    """
    devices = []
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if dev.info.vendor == VENDOR_ID and dev.info.product == PRODUCT_ID and "Keyboard" in dev.name:
            devices.append(dev)
        else:
            dev.close()

    devices.sort(key=lambda d: d.phys)
    return [(i + 1, dev) for i, dev in enumerate(devices)]


class BuzzerController:
    """Manages buzzers in a background thread, exposes ranking.

    Usage:
        buzzers = find_buzzers()
        ctrl = BuzzerController(buzzers)
        ctrl.start()

        # Poll the ranking
        ranking = ctrl.get_ranking()  # e.g. [2, 1] means buzzer 2 first, then 1

        # Reset for next question
        ctrl.reset()

        # Cleanup
        ctrl.stop()
    """

    def __init__(self, buzzers):
        self._buzzers = buzzers
        self._lock = threading.Lock()
        self._ranking = []
        self._pressed = set()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """Grab devices and start listening."""
        for _, dev in self._buzzers:
            dev.grab()
        self._drain_all()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listening and release devices."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        for _, dev in self._buzzers:
            dev.ungrab()
            dev.close()

    def reset(self):
        """Clear the ranking for a new question."""
        with self._lock:
            self._ranking = []
            self._pressed = set()
        self._drain_all()

    def get_ranking(self):
        """Return the current press order as a list of buzzer numbers."""
        with self._lock:
            return list(self._ranking)

    def _drain_all(self):
        for _, dev in self._buzzers:
            while dev.read_one():
                pass

    def _listen(self):
        fd_map = {dev.fd: (num, dev) for num, dev in self._buzzers}

        while not self._stop.is_set():
            r, _, _ = select.select(fd_map, [], [], 0.1)
            for fd in r:
                num, dev = fd_map[fd]
                for event in dev.read():
                    if event.type == ecodes.EV_KEY and event.value == 1 and event.code == ecodes.KEY_K:
                        with self._lock:
                            if num not in self._pressed:
                                self._pressed.add(num)
                                self._ranking.append(num)


def main():
    buzzers = find_buzzers()
    if not buzzers:
        print("No buzzers found. Are they plugged in?")
        return

    print(f"Found {len(buzzers)} buzzer(s):")
    for num, dev in buzzers:
        print(f"  Buzzer {num}: {dev.phys}")

    ctrl = BuzzerController(buzzers)
    ctrl.start()

    print("\nPress buzzers (Ctrl+C to quit, 'r' + Enter to reset)...\n")

    import sys
    try:
        while True:
            ranking = ctrl.get_ranking()
            print(f"\rRanking: {ranking}    ", end="", flush=True)

            # Check for reset input (non-blocking would be nicer but this is just a demo)
            import select as sel
            if sel.select([sys.stdin], [], [], 0.5)[0]:
                line = sys.stdin.readline().strip()
                if line == "r":
                    ctrl.reset()
                    print("\n[Reset!]")
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        ctrl.stop()


if __name__ == "__main__":
    main()
