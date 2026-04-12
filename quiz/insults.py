"""Insult pack loading and resolution.

Insult packs are JSON files in insults/ with 5 category arrays.
The resolve_insult helper implements the canonical fallback chain:
AI agent → static pack → empty string. Callers decide whether to fall back
to hardcoded text if resolve_insult returns empty.
"""

import glob
import json
import logging
import os
import random

log = logging.getLogger("quiz.insults")

INSULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "insults")

INSULT_CATEGORIES = ("correct_fast", "correct_slow", "wrong", "timeout", "nobody")


def list_insult_packs():
    """Return sorted list of available insult pack paths."""
    pattern = os.path.join(INSULTS_DIR, "*.json")
    return sorted(glob.glob(pattern))


def insult_pack_name(path):
    """Extract display name from an insult pack. Uses 'name' field if present."""
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("name", os.path.splitext(os.path.basename(path))[0])
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load insult pack name from %s: %s", path, e)
        return os.path.splitext(os.path.basename(path))[0]


def load_insult_pack(path):
    """Load an insult pack from JSON. Returns dict with category keys."""
    with open(path) as f:
        data = json.load(f)
    pack = {}
    for cat in INSULT_CATEGORIES:
        pack[cat] = data.get(cat, [])
    return pack


def insult_pick(pack, category):
    """Pick a random insult from a category, or return empty string."""
    if not pack:
        return ""
    pool = pack.get(category, [])
    return random.choice(pool) if pool else ""


def resolve_insult(category, insult_ai_obj=None, insult_pack=None, **ai_kwargs):
    """Resolve an insult for the given category.

    Tries the AI agent first (with ai_kwargs forwarded to generate_insult),
    then the static pack. Returns empty string if neither produces anything.
    Callers can fall back to hardcoded pools (SAVAGE_TEXTS / LAME_TEXTS)
    if they want a guaranteed non-empty string.
    """
    if insult_ai_obj:
        try:
            insult = insult_ai_obj.generate_insult(category, **ai_kwargs)
            if insult:
                return insult
        except Exception:
            # Never let an AI crash kill the game — log loudly and fall through
            log.exception("AI insult generation raised for category %r", category)
    return insult_pick(insult_pack, category)
