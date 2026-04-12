"""Constants, ASCII art, and text pools for the quiz UI."""

import os

# Environment-configurable defaults
DEFAULT_RPI_HOST = os.environ.get("BUZZER_RPI_HOST", "10.0.0.1")
DEFAULT_RPI_PORT = os.environ.get("BUZZER_RPI_PORT", "8888")

# Timing
POLL_INTERVAL = 0.1           # seconds between ranking polls
DEFAULT_ANSWER_TIMEOUT = 30.0  # default seconds to answer after buzzing
TIMEOUT_OPTIONS = [10, 15, 20, 25, 30, 45, 60]

# Predefined color palette for the team picker
COLOR_PALETTE = [
    ("#0066ff", "Blue"),
    ("#ffcc00", "Yellow"),
    ("#ff6600", "Orange"),
    ("#cc00ff", "Purple"),
    ("#00cccc", "Cyan"),
    ("#ff0099", "Pink"),
    ("#ffffff", "White"),
    ("#ff4444", "Coral"),
    ("#44ddaa", "Mint"),
    ("#ffaa00", "Amber"),
    ("#8844ff", "Violet"),
    ("#00aaff", "Sky Blue"),
]

# ── Box drawing characters ──
BOX_H = "═"
BOX_V = "║"
BOX_TL = "╔"
BOX_TR = "╗"
BOX_BL = "╚"
BOX_BR = "╝"
BOX_LT = "╠"
BOX_RT = "╣"
BOX_h = "─"
BOX_v = "│"
BOX_tl = "┌"
BOX_tr = "┐"
BOX_bl = "└"
BOX_br = "┘"

# Progress bar characters
BAR_FULL = "█"
BAR_EMPTY = "░"

# ── ASCII art ──

ART_CHECK = [
    "        ██",
    "       ██ ",
    " ██   ██  ",
    "  ██ ██   ",
    "   ███    ",
]

ART_CROSS = [
    " ██   ██ ",
    "  ██ ██  ",
    "   ███   ",
    "  ██ ██  ",
    " ██   ██ ",
]

ART_QUESTION = [
    "  ██████  ",
    " ██    ██ ",
    "     ██   ",
    "    ██    ",
    "          ",
    "    ██    ",
]

# Fire columns for the final question (left and right of the box)
ART_FIRE = [
    "  (  )  ",
    " (    ) ",
    "(  ()  )",
    " ( () ) ",
    "(  ()  )",
    " (    ) ",
    "  (  )  ",
    "   ()   ",
    "  (  )  ",
    " (    ) ",
    "(  ()  )",
    " ( () ) ",
    "(      )",
    " (    ) ",
    "  (  )  ",
    "   ()   ",
]

TITLE_ART = [
    "╔══╗ ╔╗ ╔╗ ╔══╗ ╔══╗",
    "║  ║ ║║ ║║   ╔╝ ╠══╣",
    "╚══╝ ╚╝ ╚╝ ╚══╝ ╩  ╩",
]

# ── Falling text pools ──

SAVAGE_TEXTS = ["SAVAGE!", "LIGHTNING!", "BLAZING!", "UNSTOPPABLE!", "ON FIRE!"]
LAME_TEXTS = ["LAME!", "CRICKETS...", "AWKWARD...", "YIKES!", "TUMBLEWEED..."]
