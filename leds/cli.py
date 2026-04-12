#!/usr/bin/env python3
"""Command-line interface for the KlopfKlopf LED Controller."""

import argparse
import signal
import sys
import time

from leds.klopfklopf import LEDController


def wait_forever():
    """Block until Ctrl+C."""
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(
        prog="klopfklopf",
        description="Control the KlopfKlopf USB LED strip.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── on ──
    p_on = sub.add_parser("on", help="Set a fixed color")
    p_on.add_argument("color", help="Color as hex (#ff0000) or r,g,b (255,0,0)")

    # ── off ──
    sub.add_parser("off", help="Turn LEDs off")

    # ── rainbow ──
    p_rain = sub.add_parser("rainbow", help="Rainbow cycle through colors")
    p_rain.add_argument("colors", nargs="+", help="Two or more colors")
    p_rain.add_argument("-p", "--period", type=float, default=2.0, help="Cycle period in seconds (default: 2.0)")
    p_rain.add_argument("--fps", type=int, default=60, help="Frame rate (default: 60)")

    # ── pulse ──
    p_pulse = sub.add_parser("pulse", help="Pulse brightness up and down")
    p_pulse.add_argument("colors", nargs="+", help="One or more colors")
    p_pulse.add_argument("-p", "--period", type=float, default=1.5, help="Pulse period in seconds (default: 1.5)")
    p_pulse.add_argument("--fps", type=int, default=60, help="Frame rate (default: 60)")

    # ── strobe ──
    p_strobe = sub.add_parser("strobe", help="Strobe flash effect")
    p_strobe.add_argument("color", help="Flash color")
    p_strobe.add_argument("--hz", type=float, default=10.0, help="Flashes per second (default: 10)")

    # ── candle ──
    p_candle = sub.add_parser("candle", help="Flickering candle effect")
    p_candle.add_argument("color", nargs="?", default=None, help="Flame color (default: warm orange)")
    p_candle.add_argument("-i", "--intensity", type=float, default=0.4, help="Flicker intensity 0.0-1.0 (default: 0.4)")
    p_candle.add_argument("--fps", type=int, default=30, help="Frame rate (default: 30)")

    # ── breathe ──
    p_breathe = sub.add_parser("breathe", help="Gentle breathing effect")
    p_breathe.add_argument("color", help="Breathing color")
    p_breathe.add_argument("-p", "--period", type=float, default=4.0, help="Breath period in seconds (default: 4.0)")
    p_breathe.add_argument("--fps", type=int, default=60, help="Frame rate (default: 60)")

    args = parser.parse_args()

    def parse_cli_color(s):
        """Parse 'r,g,b' or hex color from CLI arg."""
        if "," in s:
            parts = [int(x.strip()) for x in s.split(",")]
            return (parts[0], parts[1], parts[2])
        return s

    with LEDController() as leds:
        signal.signal(signal.SIGINT, lambda *_: (leds.off(), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda *_: (leds.off(), sys.exit(0)))

        if args.command == "on":
            leds.set_color(parse_cli_color(args.color))
            print(f"Set color: {args.color}")

        elif args.command == "off":
            leds.off()
            print("LEDs off.")

        elif args.command == "rainbow":
            colors = [parse_cli_color(c) for c in args.colors]
            leds.rainbow(colors, period=args.period, fps=args.fps)
            print(f"Rainbow ({len(colors)} colors, {args.period}s period) — Ctrl+C to stop")
            wait_forever()

        elif args.command == "pulse":
            colors = [parse_cli_color(c) for c in args.colors]
            leds.pulse(colors, period=args.period, fps=args.fps)
            print(f"Pulse ({len(colors)} colors, {args.period}s period) — Ctrl+C to stop")
            wait_forever()

        elif args.command == "strobe":
            leds.strobe(parse_cli_color(args.color), hz=args.hz)
            print(f"Strobe {args.color} at {args.hz} Hz — Ctrl+C to stop")
            wait_forever()

        elif args.command == "candle":
            color_arg = parse_cli_color(args.color) if args.color else (255, 147, 41)
            leds.candle(color=color_arg, intensity=args.intensity, fps=args.fps)
            print(f"Candle (intensity {args.intensity}) — Ctrl+C to stop")
            wait_forever()

        elif args.command == "breathe":
            leds.breathe(parse_cli_color(args.color), period=args.period, fps=args.fps)
            print(f"Breathe {args.color} ({args.period}s period) — Ctrl+C to stop")
            wait_forever()

        leds.off()


if __name__ == "__main__":
    main()
