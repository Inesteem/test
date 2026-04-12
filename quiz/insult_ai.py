"""AI-powered insult generator using Claude CLI in headless mode.

Uses 'claude -p' with session persistence so the model stays in character
across the entire game. No API key needed — uses existing Claude Code auth.

Agent definitions are loaded from agents/*.json.
"""

import glob
import json
import logging
import os
import shutil
import subprocess
import threading
import uuid

log = logging.getLogger("insult_ai")

AGENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")

DEFAULT_SYSTEM_PROMPT = (
    "You are a savage roast master at a quiz game for engineers. "
    "STRICT LIMIT: 60 characters max, one short sentence. "
    "Comedy roast style, dark humor, cynicism. Never repeat yourself. "
    "Stay PG-13. Output ONLY the insult — no quotes, no explanation. "
    "If your response exceeds 60 characters, you have failed."
)


def list_agents():
    """Return sorted list of available agent definition paths."""
    pattern = os.path.join(AGENTS_DIR, "*.json")
    return sorted(glob.glob(pattern))


def load_agent(path):
    """Load an agent definition. Returns dict with name, description, system_prompt."""
    with open(path) as f:
        data = json.load(f)
    return {
        "name": data.get("name", os.path.splitext(os.path.basename(path))[0]),
        "description": data.get("description", ""),
        "system_prompt": data.get("system_prompt", DEFAULT_SYSTEM_PROMPT),
    }


def agent_name(path):
    """Extract display name from an agent file."""
    try:
        return load_agent(path)["name"]
    except (json.JSONDecodeError, OSError):
        return os.path.splitext(os.path.basename(path))[0]


class InsultAI:
    """Generates contextual insults via Claude CLI with session persistence."""

    def __init__(self, system_prompt=None):
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._session_id = str(uuid.uuid4())
        self._primed = False
        self._last_result = None
        self._last_thread = None
        # Generation counter prevents stale results from a previous
        # generate_async() leaking into the current get_result() call.
        self._gen_id = 0

    def available(self):
        """Check if the claude CLI is on PATH."""
        found = shutil.which("claude") is not None
        log.info("claude CLI available: %s", found)
        return found

    def prime(self):
        """Send an initial priming message to establish the persona.

        Call this once at game start (e.g. during team setup) so the
        session is warm by the time the first question starts.
        """
        if self._primed:
            return True
        log.info("Priming session %s...", self._session_id)
        try:
            r = subprocess.run(
                ["claude", "-p", "Prime: say READY",
                 "--model", "haiku",
                 "--session-id", self._session_id,
                 "--system-prompt", self._system_prompt],
                capture_output=True, text=True, timeout=20,
            )
            self._primed = r.returncode == 0
            log.info("Prime result: rc=%d, stdout=%r, stderr=%r",
                     r.returncode, r.stdout.strip()[:100], r.stderr.strip()[:200])
            return self._primed
        except Exception as e:
            log.error("Prime failed: %s", e)
            return False

    def _call(self, prompt):
        """Send a prompt to the existing session and return the response."""
        if not self._primed:
            self.prime()
        log.debug("Calling session %s with prompt: %s", self._session_id, prompt[:80])
        try:
            r = subprocess.run(
                ["claude", "-p", prompt,
                 "--model", "haiku",
                 "--resume", self._session_id],
                capture_output=True, text=True, timeout=20,
            )
            log.info("Call result: rc=%d, stdout=%r, stderr=%r",
                     r.returncode, r.stdout.strip()[:100], r.stderr.strip()[:200])
            if r.returncode == 0:
                return r.stdout.strip().strip('"')
            return ""
        except Exception as e:
            log.error("Call failed: %s", e)
            return ""

    def _build_prompt(self, event, question, answer_time, team_name, given_answer,
                      correct_answer, was_correct, scores=None, team_color=""):
        """Build a context string for the model."""
        team_desc = f"{team_name} ({team_color})" if team_color else team_name
        parts = [f"Event: {event}", f"Question: {question}", f"Team: {team_desc}"]

        if given_answer:
            parts.append(f"Their answer: {given_answer}")
            parts.append(f"Correct answer: {correct_answer}")

        if answer_time is not None:
            parts.append(f"Time to answer: {answer_time:.1f}s")

        if scores:
            score_str = ", ".join(f"{t}: {s}" for t, s in scores.items())
            parts.append(f"Current scores: {score_str}")

        if was_correct:
            if answer_time is not None and answer_time < 3.0:
                parts.append("CORRECT and FAST. Backhanded compliment.")
            else:
                parts.append("CORRECT but slowly. Mock their speed.")
        elif event == "wrong":
            parts.append("WRONG answer. Destroy them.")
        elif event == "timeout":
            parts.append("RAN OUT OF TIME. Mock their indecision.")
        elif event == "nobody":
            parts.append("NO TEAM got it right. Shame the entire room.")

        parts.append("Reference their history if relevant (past mistakes, streaks, rivalry). Occasionally mock their team name or color.")

        return "\n".join(parts)

    def generate_insult(self, event, question="", answer_time=None, team_name="",
                        given_answer="", correct_answer="", was_correct=False,
                        scores=None, team_color=""):
        """Generate an insult. Returns empty string on failure."""
        prompt = self._build_prompt(event, question, answer_time, team_name,
                                    given_answer, correct_answer, was_correct,
                                    scores, team_color)
        result = self._call(prompt)
        log.info("Generated insult for %s: %r", event, result[:80] if result else "(empty)")
        return result

    def generate_async(self, event, **kwargs):
        """Start generation in background. Call get_result() to retrieve it.

        If a previous generation is still running, it's abandoned — its
        eventual result is discarded so it can't leak into this call.
        """
        self._gen_id += 1
        my_gen = self._gen_id
        self._last_result = None

        def _run():
            result = self.generate_insult(event, **kwargs)
            # Only record if we're still the current generation
            if self._gen_id == my_gen:
                self._last_result = result

        self._last_thread = threading.Thread(target=_run, daemon=True)
        self._last_thread.start()

    def get_result(self, timeout=8.0):
        """Wait for the async result. Returns insult string or empty on timeout."""
        if self._last_thread is None:
            log.warning("get_result called with no pending thread")
            return ""
        self._last_thread.join(timeout=timeout)
        alive = self._last_thread.is_alive()
        result = self._last_result or ""
        if alive:
            log.warning("get_result timed out after %.1fs", timeout)
        else:
            log.info("get_result returned: %r", result[:80] if result else "(empty)")
        return result
