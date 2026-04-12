"""Quiz question loader.

Loads questions from JSON files in the questions/ directory.
Supports shuffling question order and randomizing answer positions.

JSON format:
[
  {
    "question": "What is 1+1?",
    "choices": ["1", "2", "3"],
    "answer": 1
  }
]

- choices: list of 3 strings
- answer: index (0-based) of the correct choice in the original list
- difficulty: 1-10 rating (optional, defaults to 5)
"""

import glob
import json
import os
import random

QUESTIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "questions")

KEYS = ("a", "b", "c")


def list_bundles():
    """Return sorted list of available question bundle paths."""
    pattern = os.path.join(QUESTIONS_DIR, "*.json")
    return sorted(glob.glob(pattern))


def bundle_name(path):
    """Extract display name from a bundle path."""
    return os.path.splitext(os.path.basename(path))[0]


def load_bundle(path):
    """Load and validate a question bundle from a JSON file.

    Returns a list of raw question dicts (not yet shuffled).
    """
    with open(path) as f:
        data = json.load(f)

    questions = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Question {i}: expected dict, got {type(item).__name__}")
        if "question" not in item or "choices" not in item or "answer" not in item:
            raise ValueError(f"Question {i}: missing required keys (question, choices, answer)")
        if len(item["choices"]) != 3:
            raise ValueError(f"Question {i}: expected 3 choices, got {len(item['choices'])}")
        if not isinstance(item["answer"], int) or item["answer"] not in (0, 1, 2):
            raise ValueError(f"Question {i}: answer must be 0, 1, or 2")
        questions.append(item)

    return questions


def prepare_questions(raw_questions):
    """Shuffle questions, pin the hardest one last, randomize answer positions.

    Returns a list of dicts in the format the UI expects:
        {"question": str, "choices": {"a": ..., "b": ..., "c": ...}, "answer": "a"/"b"/"c"}
    """
    if not raw_questions:
        return []

    # Find the hardest question, break ties randomly
    hardest = max(raw_questions, key=lambda q: (q.get("difficulty", 5), random.random()))
    rest = [q for q in raw_questions if q is not hardest]
    random.shuffle(rest)
    ordered = rest + [hardest]

    prepared = []
    for item in ordered:
        # Shuffle choice order
        indexed = list(enumerate(item["choices"]))
        random.shuffle(indexed)

        choices = {}
        answer_key = None
        for key, (orig_idx, text) in zip(KEYS, indexed):
            choices[key] = text
            if orig_idx == item["answer"]:
                answer_key = key

        prepared.append({
            "question": item["question"],
            "choices": choices,
            "answer": answer_key,
        })

    return prepared


# Default: load first available bundle for backwards compat with tests
_bundles = list_bundles()
QUESTIONS = prepare_questions(load_bundle(_bundles[0])) if _bundles else []
