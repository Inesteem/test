"""
CLI for quiz game sound effects.

Usage:
    python -m sound                  # list available sounds
    python -m sound correct          # play a sound
    python -m sound wrong --vol 0.3  # with volume
    python -m sound all              # play all sounds in sequence
"""

import argparse

from sound.sound import Sound, MELODIES


def main():
    parser = argparse.ArgumentParser(description="Quiz game sound effects")
    parser.add_argument(
        "name",
        nargs="?",
        choices=[*sorted(MELODIES), "all"],
        help="Sound to play (omit to list available sounds)",
    )
    parser.add_argument(
        "--vol", type=float, default=0.5, help="Volume 0.0–1.0 (default: 0.5)"
    )
    args = parser.parse_args()

    if args.name is None:
        print("Available sounds:")
        for name in sorted(MELODIES):
            print(f"  {name}")
        return

    snd = Sound(volume=args.vol)

    if args.name == "all":
        for name in sorted(MELODIES):
            print(f"  ♪ {name}")
            snd.play(name)
        return

    snd.play(args.name)


if __name__ == "__main__":
    main()
