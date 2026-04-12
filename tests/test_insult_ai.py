"""Tests for quiz/insult_ai.py — AI insult generator via Claude CLI.

Mocks subprocess.run and shutil.which so no real CLI calls happen.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from quiz.insult_ai import (
    DEFAULT_SYSTEM_PROMPT,
    InsultAI,
    agent_name,
    list_agents,
    load_agent,
)


# ---------------------------------------------------------------------------
# Agent file loading
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_agents_dir(tmp_path, monkeypatch):
    """Create a temp agents dir with a couple of test agent files."""
    d = tmp_path / "agents"
    d.mkdir()

    (d / "test-roaster.json").write_text(json.dumps({
        "name": "Test Roaster",
        "description": "A test agent",
        "system_prompt": "You roast things. 60 chars max.",
    }))

    (d / "minimal.json").write_text(json.dumps({
        "name": "Minimal",
        "description": "",
        "system_prompt": "Minimal prompt.",
    }))

    (d / "missing-fields.json").write_text(json.dumps({
        "name": "Partial",
    }))

    (d / "broken.json").write_text("{ this is not valid json")

    monkeypatch.setattr("quiz.insult_ai.AGENTS_DIR", str(d))
    return d


class TestListAgents:

    def test_returns_sorted_paths(self, tmp_agents_dir):
        agents = list_agents()
        assert len(agents) == 4
        assert agents == sorted(agents)

    def test_only_json_files(self, tmp_agents_dir):
        (tmp_agents_dir / "not-an-agent.txt").write_text("ignore me")
        agents = list_agents()
        assert all(a.endswith(".json") for a in agents)

    def test_empty_directory_returns_empty(self, tmp_path, monkeypatch):
        d = tmp_path / "empty"
        d.mkdir()
        monkeypatch.setattr("quiz.insult_ai.AGENTS_DIR", str(d))
        assert list_agents() == []


class TestLoadAgent:

    def test_loads_all_fields(self, tmp_agents_dir):
        agent = load_agent(str(tmp_agents_dir / "test-roaster.json"))
        assert agent["name"] == "Test Roaster"
        assert agent["description"] == "A test agent"
        assert agent["system_prompt"] == "You roast things. 60 chars max."

    def test_missing_name_falls_back_to_filename(self, tmp_path):
        path = tmp_path / "some-name.json"
        path.write_text(json.dumps({"description": "x", "system_prompt": "y"}))
        agent = load_agent(str(path))
        assert agent["name"] == "some-name"

    def test_missing_description_is_empty_string(self, tmp_agents_dir):
        agent = load_agent(str(tmp_agents_dir / "missing-fields.json"))
        assert agent["description"] == ""

    def test_missing_system_prompt_falls_back_to_default(self, tmp_agents_dir):
        agent = load_agent(str(tmp_agents_dir / "missing-fields.json"))
        assert agent["system_prompt"] == DEFAULT_SYSTEM_PROMPT


class TestAgentName:

    def test_returns_name_from_file(self, tmp_agents_dir):
        assert agent_name(str(tmp_agents_dir / "test-roaster.json")) == "Test Roaster"

    def test_broken_json_falls_back_to_filename(self, tmp_agents_dir):
        assert agent_name(str(tmp_agents_dir / "broken.json")) == "broken"

    def test_missing_file_falls_back_to_filename(self):
        assert agent_name("/nonexistent/path/my-agent.json") == "my-agent"


# ---------------------------------------------------------------------------
# Shipped agents — smoke test
# ---------------------------------------------------------------------------

class TestShippedAgents:

    def test_all_shipped_agents_load(self):
        for path in list_agents():
            agent = load_agent(path)
            assert agent["name"]
            assert agent["system_prompt"]


# ---------------------------------------------------------------------------
# InsultAI._build_prompt — pure function, easy to test
# ---------------------------------------------------------------------------

class TestBuildPrompt:

    @pytest.fixture
    def ai(self):
        return InsultAI()

    def test_includes_event_question_team(self, ai):
        prompt = ai._build_prompt(
            "wrong", "What is 2+2?", None, "Foxes",
            "B) 5", "C) 4", False,
        )
        assert "Event: wrong" in prompt
        assert "Question: What is 2+2?" in prompt
        assert "Team: Foxes" in prompt

    def test_includes_given_and_correct_answer_when_provided(self, ai):
        prompt = ai._build_prompt(
            "wrong", "Q", None, "T", "A) foo", "B) bar", False,
        )
        assert "Their answer: A) foo" in prompt
        assert "Correct answer: B) bar" in prompt

    def test_includes_answer_time_when_provided(self, ai):
        prompt = ai._build_prompt(
            "correct_fast", "Q", 2.3, "T", "", "", True,
        )
        assert "Time to answer: 2.3s" in prompt

    def test_omits_answer_time_when_none(self, ai):
        prompt = ai._build_prompt("wrong", "Q", None, "T", "", "", False)
        assert "Time to answer" not in prompt

    def test_fast_correct_asks_for_backhanded_compliment(self, ai):
        prompt = ai._build_prompt(
            "correct_fast", "Q", 1.5, "T", "", "", True,
        )
        assert "CORRECT and FAST" in prompt
        assert "Backhanded compliment" in prompt

    def test_slow_correct_asks_to_mock_speed(self, ai):
        prompt = ai._build_prompt(
            "correct_slow", "Q", 25.0, "T", "", "", True,
        )
        assert "CORRECT but slowly" in prompt

    def test_wrong_asks_to_destroy(self, ai):
        prompt = ai._build_prompt("wrong", "Q", None, "T", "", "", False)
        assert "WRONG answer. Destroy them." in prompt

    def test_timeout_event_has_dedicated_instruction(self, ai):
        prompt = ai._build_prompt("timeout", "Q", None, "T", "", "", False)
        assert "RAN OUT OF TIME" in prompt

    def test_nobody_event_shames_the_room(self, ai):
        prompt = ai._build_prompt("nobody", "Q", None, "T", "", "", False)
        assert "NO TEAM got it right" in prompt

    def test_team_color_included(self, ai):
        prompt = ai._build_prompt(
            "wrong", "Q", None, "Foxes", "", "", False,
            team_color="Blue",
        )
        assert "Foxes (Blue)" in prompt

    def test_scores_included(self, ai):
        prompt = ai._build_prompt(
            "wrong", "Q", None, "T", "", "", False,
            scores={"Foxes": 3, "Hawks": -1},
        )
        assert "Current scores:" in prompt
        assert "Foxes: 3" in prompt
        assert "Hawks: -1" in prompt

    def test_prompt_asks_to_reference_history(self, ai):
        prompt = ai._build_prompt("wrong", "Q", None, "T", "", "", False)
        assert "history" in prompt.lower()


# ---------------------------------------------------------------------------
# InsultAI.available
# ---------------------------------------------------------------------------

class TestAvailable:

    def test_available_when_claude_on_path(self):
        ai = InsultAI()
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            assert ai.available() is True

    def test_unavailable_when_claude_missing(self):
        ai = InsultAI()
        with patch("shutil.which", return_value=None):
            assert ai.available() is False


# ---------------------------------------------------------------------------
# InsultAI.prime + _call with mocked subprocess
# ---------------------------------------------------------------------------

class TestPrime:

    def test_prime_returns_true_on_rc_zero(self):
        ai = InsultAI()
        fake_result = MagicMock(returncode=0, stdout="READY\n", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            assert ai.prime() is True
        assert ai._primed is True

    def test_prime_returns_false_on_nonzero_rc(self):
        ai = InsultAI()
        fake_result = MagicMock(returncode=1, stdout="", stderr="boom")
        with patch("subprocess.run", return_value=fake_result):
            assert ai.prime() is False
        assert ai._primed is False

    def test_prime_returns_false_on_exception(self):
        ai = InsultAI()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=20)):
            assert ai.prime() is False

    def test_prime_is_idempotent(self):
        ai = InsultAI()
        fake_result = MagicMock(returncode=0, stdout="READY", stderr="")
        with patch("subprocess.run", return_value=fake_result) as m:
            ai.prime()
            ai.prime()
            assert m.call_count == 1  # second call is a no-op

    def test_prime_passes_system_prompt_via_cli(self):
        ai = InsultAI(system_prompt="custom prompt")
        fake_result = MagicMock(returncode=0, stdout="READY", stderr="")
        with patch("subprocess.run", return_value=fake_result) as m:
            ai.prime()
            args = m.call_args[0][0]
            assert "--system-prompt" in args
            assert "custom prompt" in args

    def test_prime_uses_session_id(self):
        ai = InsultAI()
        fake_result = MagicMock(returncode=0, stdout="READY", stderr="")
        with patch("subprocess.run", return_value=fake_result) as m:
            ai.prime()
            args = m.call_args[0][0]
            assert "--session-id" in args
            assert ai._session_id in args


class TestCall:

    def test_call_returns_stdout_stripped(self):
        ai = InsultAI()
        ai._primed = True
        fake_result = MagicMock(returncode=0, stdout='  "You lost."  \n', stderr="")
        with patch("subprocess.run", return_value=fake_result):
            assert ai._call("prompt") == "You lost."

    def test_call_returns_empty_on_nonzero_rc(self):
        ai = InsultAI()
        ai._primed = True
        fake_result = MagicMock(returncode=1, stdout="ignored", stderr="err")
        with patch("subprocess.run", return_value=fake_result):
            assert ai._call("prompt") == ""

    def test_call_returns_empty_on_timeout(self):
        ai = InsultAI()
        ai._primed = True
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=20)):
            assert ai._call("prompt") == ""

    def test_call_primes_if_not_primed(self):
        ai = InsultAI()
        # _call internally calls prime() if not already primed
        fake_result = MagicMock(returncode=0, stdout="response", stderr="")
        with patch("subprocess.run", return_value=fake_result) as m:
            ai._call("prompt")
            # Prime + actual call = 2 subprocess invocations
            assert m.call_count == 2


# ---------------------------------------------------------------------------
# generate_insult end-to-end with mock
# ---------------------------------------------------------------------------

class TestGenerateInsult:

    def test_happy_path(self):
        ai = InsultAI()
        ai._primed = True
        fake_result = MagicMock(returncode=0, stdout="Absolutely useless.", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            result = ai.generate_insult(
                "wrong", question="Q", team_name="Foxes",
                given_answer="A", correct_answer="B",
            )
        assert result == "Absolutely useless."

    def test_failure_returns_empty(self):
        ai = InsultAI()
        ai._primed = True
        fake_result = MagicMock(returncode=1, stdout="", stderr="crashed")
        with patch("subprocess.run", return_value=fake_result):
            result = ai.generate_insult("wrong", question="Q", team_name="Foxes")
        assert result == ""


# ---------------------------------------------------------------------------
# generate_async + get_result
# ---------------------------------------------------------------------------

class TestAsyncGeneration:

    def test_async_result_retrieved(self):
        ai = InsultAI()
        ai._primed = True
        fake_result = MagicMock(returncode=0, stdout="Async insult.", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            ai.generate_async("wrong", question="Q", team_name="Foxes")
            result = ai.get_result(timeout=5.0)
        assert result == "Async insult."

    def test_get_result_without_pending_returns_empty(self):
        ai = InsultAI()
        assert ai.get_result() == ""

    def test_get_result_timeout_returns_empty(self):
        ai = InsultAI()
        ai._primed = True
        # Make subprocess.run block long enough to trigger our timeout
        def slow(*args, **kwargs):
            import time
            time.sleep(2)
            return MagicMock(returncode=0, stdout="never seen", stderr="")

        with patch("subprocess.run", side_effect=slow):
            ai.generate_async("wrong", question="Q", team_name="Foxes")
            result = ai.get_result(timeout=0.2)
        assert result == ""

    def test_stale_generation_does_not_leak(self):
        """A new generate_async() invalidates any in-flight previous call."""
        import threading
        ai = InsultAI()
        ai._primed = True

        # First call: slow, would eventually produce "STALE"
        first_result = threading.Event()

        def slow_first(*args, **kwargs):
            first_result.wait(0.5)
            return MagicMock(returncode=0, stdout="STALE", stderr="")

        # Second call: fast, produces "FRESH"
        def fast_second(*args, **kwargs):
            return MagicMock(returncode=0, stdout="FRESH", stderr="")

        call_count = [0]

        def run_impl(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return slow_first(*args, **kwargs)
            return fast_second(*args, **kwargs)

        with patch("subprocess.run", side_effect=run_impl):
            ai.generate_async("wrong", question="Q1", team_name="Foxes")
            # Immediately kick off a second call — the first is still running
            ai.generate_async("wrong", question="Q2", team_name="Foxes")
            # Let the fast second one finish
            result = ai.get_result(timeout=2.0)
            # Let the slow first one finish its write (which should be ignored)
            first_result.set()
            import time as _t
            _t.sleep(0.6)

        # We should see FRESH, not STALE
        assert result == "FRESH"
        # _last_result should still be FRESH, not clobbered by the stale thread
        assert ai._last_result == "FRESH"
