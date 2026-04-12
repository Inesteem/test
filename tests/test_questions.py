"""Tests for quiz/questions.py — question format validation.

Tests load specific bundles explicitly via load_bundle() rather than using
the module-level QUESTIONS constant, since that's randomized at import time.
"""

import os

import pytest

from quiz.questions import load_bundle, prepare_questions, list_bundles, bundle_name

QUESTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "questions")


def _load(name):
    """Load and prepare a specific bundle by file name."""
    path = os.path.join(QUESTIONS_DIR, name)
    return prepare_questions(load_bundle(path))


def _load_raw(name):
    """Load a bundle without shuffling (for deterministic content checks)."""
    path = os.path.join(QUESTIONS_DIR, name)
    return load_bundle(path)


def _correct_text(q):
    """Text of the correct choice from a prepared question dict."""
    return q["choices"][q["answer"]]


@pytest.fixture
def google_swe_raw():
    return _load_raw("google-swe.json")


@pytest.fixture
def google_swe_prepared():
    return _load(("google-swe.json"))


# ---------------------------------------------------------------------------
# Bundle discovery
# ---------------------------------------------------------------------------

class TestBundleDiscovery:

    def test_list_bundles_returns_paths(self):
        bundles = list_bundles()
        assert len(bundles) > 0
        assert all(b.endswith(".json") for b in bundles)

    def test_google_swe_bundle_exists(self):
        bundles = list_bundles()
        names = [bundle_name(b) for b in bundles]
        assert "google-swe" in names


# ---------------------------------------------------------------------------
# Format validation — applies to every shipped bundle
# ---------------------------------------------------------------------------

class TestAllBundlesValidate:

    def test_every_bundle_loads_without_error(self):
        for path in list_bundles():
            questions = load_bundle(path)
            assert len(questions) > 0, f"{path} is empty"

    def test_every_question_has_required_fields(self):
        for path in list_bundles():
            for i, q in enumerate(load_bundle(path)):
                assert "question" in q, f"{path} q{i} missing 'question'"
                assert "choices" in q, f"{path} q{i} missing 'choices'"
                assert "answer" in q, f"{path} q{i} missing 'answer'"
                assert isinstance(q["choices"], list), f"{path} q{i} choices not a list"
                assert len(q["choices"]) == 3, f"{path} q{i} expected 3 choices"
                assert q["answer"] in (0, 1, 2), f"{path} q{i} answer not 0/1/2"
                assert isinstance(q["question"], str) and q["question"].strip()
                for j, c in enumerate(q["choices"]):
                    assert isinstance(c, str) and c.strip(), f"{path} q{i} choice {j} empty"

    def test_every_bundle_has_distinct_choices_per_question(self):
        for path in list_bundles():
            for i, q in enumerate(load_bundle(path)):
                assert len(set(q["choices"])) == 3, \
                    f"{path} q{i} has duplicate choices"

    def test_every_bundle_has_unique_question_texts(self):
        for path in list_bundles():
            texts = [q["question"] for q in load_bundle(path)]
            assert len(texts) == len(set(texts)), \
                f"{path} has duplicate question texts"


# ---------------------------------------------------------------------------
# prepare_questions — shuffling and hardest-last invariant
# ---------------------------------------------------------------------------

class TestPrepareQuestions:

    def test_prepared_questions_match_raw_count(self, google_swe_raw, google_swe_prepared):
        assert len(google_swe_prepared) == len(google_swe_raw)

    def test_prepared_has_abc_keys(self, google_swe_prepared):
        for q in google_swe_prepared:
            assert set(q["choices"].keys()) == {"a", "b", "c"}
            assert q["answer"] in ("a", "b", "c")
            assert q["choices"][q["answer"]], "answer key should resolve to a choice"

    def test_hardest_question_is_last(self, google_swe_raw):
        prepared = prepare_questions(google_swe_raw)
        last_q_text = prepared[-1]["question"]
        max_difficulty = max(q.get("difficulty", 5) for q in google_swe_raw)
        last_raw = next(q for q in google_swe_raw if q["question"] == last_q_text)
        assert last_raw.get("difficulty", 5) == max_difficulty

    def test_answer_text_preserved_through_shuffle(self, google_swe_raw):
        """The answer index in raw maps to the same text after shuffling choices."""
        prepared = prepare_questions(google_swe_raw)
        raw_by_text = {q["question"]: q for q in google_swe_raw}
        for pq in prepared:
            raw = raw_by_text[pq["question"]]
            expected_text = raw["choices"][raw["answer"]]
            assert _correct_text(pq) == expected_text

    def test_empty_bundle_returns_empty(self):
        assert prepare_questions([]) == []


# ---------------------------------------------------------------------------
# Content sanity for the google-swe bundle
# ---------------------------------------------------------------------------

class TestGoogleSweContent:
    """Content-level assertions about specific questions in the google-swe bundle.

    Uses the raw bundle so choices are stable (pre-shuffle).
    """

    def test_byte_states_answer(self, google_swe_raw):
        q = next(q for q in google_swe_raw if "byte" in q["question"].lower())
        assert q["choices"][q["answer"]] == "256"

    def test_https_answer(self, google_swe_raw):
        q = next(q for q in google_swe_raw if "HTTPS" in q["question"])
        assert q["choices"][q["answer"]] == "Secure"

    def test_google_original_name_answer(self, google_swe_raw):
        q = next(q for q in google_swe_raw if "original name" in q["question"])
        assert q["choices"][q["answer"]] == "BackRub"

    def test_bst_lookup_answer(self, google_swe_raw):
        q = next(q for q in google_swe_raw if "BST" in q["question"])
        assert q["choices"][q["answer"]] == "O(log n)"

    def test_google_monorepo_answer(self, google_swe_raw):
        q = next(q for q in google_swe_raw if "monorepo" in q["question"].lower())
        assert q["choices"][q["answer"]] == "Piper"
