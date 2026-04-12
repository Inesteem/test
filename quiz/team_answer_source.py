"""Polls team client HTTP servers for answers.

Drop-in replacement for keyboard A/B/C input in multi-client mode.
"""

import json
import logging
import urllib.request
import urllib.error

log = logging.getLogger("team_answer")


class TeamAnswerSource:
    """Polls team client HTTP servers for A/B/C answers."""

    def __init__(self, team_urls):
        """
        Args:
            team_urls: dict mapping buzzer_num → base URL
                       e.g. {1: "http://10.0.0.50:7777", 2: "http://..."}
        """
        self._urls = {k: v.rstrip("/") for k, v in team_urls.items()}

    def reset(self, buzzer_num):
        """Tell the team client to clear its stored answer."""
        url = self._urls.get(buzzer_num)
        if not url:
            return
        try:
            req = urllib.request.Request(
                f"{url}/reset", method="POST",
                data=b"", headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=1):
                pass
            log.debug("Reset team %d at %s", buzzer_num, url)
        except (urllib.error.URLError, OSError) as e:
            log.warning("Failed to reset team %d: %s", buzzer_num, e)

    def poll_once(self, buzzer_num):
        """Non-blocking poll for a team's answer.

        Returns "a", "b", "c", or None if no answer yet / error.
        """
        url = self._urls.get(buzzer_num)
        if not url:
            return None
        try:
            with urllib.request.urlopen(f"{url}/answer", timeout=0.5) as resp:
                data = json.loads(resp.read())
                answer = data.get("answer")
                if answer in ("a", "b", "c"):
                    log.info("Team %d answered: %s", buzzer_num, answer)
                    return answer
                return None
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None
