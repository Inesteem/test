"""KlopfKlopf LED Controller library.

Controls the KlopfKlopf USB LED strip (18d1:5035) with support for
fixed colors, rainbow cycles, pulsing, strobing, and more.

Usage:
    from klopfklopf import LEDController

    with LEDController() as leds:
        leds.set_color("#ff0000")
        leds.rainbow(["#ff0000", "#00ff00", "#0000ff"], period=2.0)
        leds.pulse(["#ff0000", "#0000ff"], period=1.5)
        leds.strobe("#ffffff", hz=10)
        leds.off()
"""

import math
import threading
import time
from typing import Union

import usb.core
import usb.util

VENDOR_ID = 0x18D1
PRODUCT_ID = 0x5035
EP_OUT = 0x04

Color = Union[str, tuple[int, int, int]]


def parse_color(color: Color) -> tuple[int, int, int]:
    """Parse a hex string or RGB tuple into (r, g, b) with values 0-255."""
    if isinstance(color, (list, tuple)):
        r, g, b = color
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    s = color.lstrip("#")
    if len(s) == 3:
        s = s[0] * 2 + s[1] * 2 + s[2] * 2
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Linearly interpolate between two RGB colors. t in [0, 1]."""
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


class LEDController:
    """Controls a KlopfKlopf USB LED strip."""

    def __init__(self):
        self._dev = None
        self._animation_stop = threading.Event()
        self._animation_thread: threading.Thread | None = None

    def open(self):
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            raise RuntimeError("KlopfKlopf LED Controller not found")
        for iface in range(2):
            try:
                if dev.is_kernel_driver_active(iface):
                    dev.detach_kernel_driver(iface)
            except (usb.core.USBError, NotImplementedError):
                pass  # not available on macOS
        dev.set_configuration()
        usb.util.claim_interface(dev, 0)
        self._dev = dev

    def close(self):
        self.stop()
        if self._dev is not None:
            usb.util.dispose_resources(self._dev)
            self._dev = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    def _write(self, r: int, g: int, b: int):
        payload = bytearray([0x00, 0x03, r, g, b])
        self._dev.write(EP_OUT, payload)

    def stop(self):
        """Stop any running animation."""
        if self._animation_thread is not None:
            self._animation_stop.set()
            self._animation_thread.join()
            self._animation_thread = None
            self._animation_stop.clear()

    def _run_animation(self, target, args):
        self.stop()
        self._animation_stop.clear()
        self._animation_thread = threading.Thread(target=target, args=args, daemon=True)
        self._animation_thread.start()

    # ── 1. Fixed color / off ──

    def set_color(self, color: Color):
        """Set all LEDs to a fixed color. Accepts "#rrggbb", "#rgb", or (r, g, b)."""
        self.stop()
        r, g, b = parse_color(color)
        self._write(r, g, b)

    def off(self):
        """Turn all LEDs off."""
        self.set_color((0, 0, 0))

    # ── 2. Rainbow ──

    def rainbow(self, colors: list[Color], period: float = 2.0, fps: int = 60):
        """Cycle through colors with linear interpolation.

        Args:
            colors: List of colors to cycle through.
            period: Time in seconds for one full cycle through all colors.
            fps: Animation frame rate.
        """
        parsed = [parse_color(c) for c in colors]
        if len(parsed) < 2:
            raise ValueError("Rainbow needs at least 2 colors")
        self._run_animation(self._rainbow_loop, (parsed, period, fps))

    def _rainbow_loop(self, colors, period, fps):
        n = len(colors)
        dt = 1.0 / fps
        while not self._animation_stop.is_set():
            t = (time.monotonic() % period) / period
            pos = t * n
            idx = int(pos) % n
            frac = pos - int(pos)
            color = lerp_color(colors[idx], colors[(idx + 1) % n], frac)
            self._write(*color)
            self._animation_stop.wait(dt)

    # ── 3. Pulse ──

    def pulse(self, colors: list[Color], period: float = 1.5, fps: int = 60):
        """Pulse through colors by smoothly ramping brightness up and down.

        Args:
            colors: List of colors to pulse through.
            period: Time in seconds for one full pulse cycle (up + down) per color.
            fps: Animation frame rate.
        """
        parsed = [parse_color(c) for c in colors]
        if not parsed:
            raise ValueError("Pulse needs at least 1 color")
        self._run_animation(self._pulse_loop, (parsed, period, fps))

    def _pulse_loop(self, colors, period, fps):
        n = len(colors)
        dt = 1.0 / fps
        total_period = period * n
        while not self._animation_stop.is_set():
            t = time.monotonic() % total_period
            idx = int(t / period) % n
            phase = (t % period) / period
            # Sine curve: 0 → 1 → 0 over one period
            brightness = math.sin(phase * math.pi)
            r, g, b = colors[idx]
            self._write(int(r * brightness), int(g * brightness), int(b * brightness))
            self._animation_stop.wait(dt)

    # ── 4. Strobe ──

    def strobe(self, color: Color, hz: float = 10.0):
        """Rapid flash between a color and black.

        Args:
            color: The strobe color.
            hz: Flashes per second.
        """
        parsed = parse_color(color)
        self._run_animation(self._strobe_loop, (parsed, hz))

    def _strobe_loop(self, color, hz):
        half = 0.5 / hz
        on = True
        while not self._animation_stop.is_set():
            if on:
                self._write(*color)
            else:
                self._write(0, 0, 0)
            on = not on
            self._animation_stop.wait(half)

    # ── 5. Extras ──

    def candle(self, color: Color = (255, 147, 41), intensity: float = 0.4, fps: int = 30):
        """Simulate a flickering candle flame.

        Args:
            color: Base flame color (default warm orange).
            intensity: Flicker intensity 0.0-1.0 (how much brightness varies).
            fps: Animation frame rate.
        """
        parsed = parse_color(color)
        self._run_animation(self._candle_loop, (parsed, intensity, fps))

    def _candle_loop(self, color, intensity, fps):
        import random
        dt = 1.0 / fps
        target = 1.0
        current = 1.0
        while not self._animation_stop.is_set():
            # Smoothly drift toward a random target brightness
            target = 1.0 - random.random() * intensity
            current += (target - current) * 0.3
            r, g, b = color
            self._write(int(r * current), int(g * current), int(b * current))
            self._animation_stop.wait(dt)

    def breathe(self, color: Color, period: float = 4.0, fps: int = 60):
        """Gentle breathing effect — like Apple's sleep indicator LED.

        Args:
            color: The breathing color.
            period: Time in seconds for one full breath (in + out).
            fps: Animation frame rate.
        """
        parsed = parse_color(color)
        self._run_animation(self._breathe_loop, (parsed, period, fps))

    def _breathe_loop(self, color, period, fps):
        dt = 1.0 / fps
        while not self._animation_stop.is_set():
            phase = (time.monotonic() % period) / period
            # Eased cosine curve for a natural breathing feel
            brightness = (1.0 - math.cos(2.0 * math.pi * phase)) / 2.0
            # Apply gamma for perceptual smoothness
            brightness = brightness ** 2.2
            r, g, b = color
            self._write(int(r * brightness), int(g * brightness), int(b * brightness))
            self._animation_stop.wait(dt)
