"""Display protocol — the rendering interface for the quiz game.

Both CursesDisplay and WebDisplay implement this protocol. The game engine
(flow.py, feedback.py) calls these methods instead of touching curses directly.

Display methods are pure rendering + input. Sound, LEDs, and game logic
stay in the callers.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Display(Protocol):
    """Abstract display interface for the quiz game master UI."""

    # ── Game screens ──

    def draw_question(self, q: dict, question_num: int, total: int, *,
                      status_line: str = "", ranking_line: str = "",
                      elapsed: float | None = None, timeout: float | None = None,
                      is_final: bool = False, fire_frame: int = 0,
                      ripple_frame: int = -1) -> None:
        """Render the question screen with choices, progress bar, and effects."""
        ...

    def draw_feedback(self, correct: bool, team_name: str, *,
                      question_text: str = "", correct_answer: str = "",
                      insult: str = "") -> None:
        """Render feedback screen — green for correct, red for wrong."""
        ...

    def draw_continue_prompt(self, text: str = "Press Enter to continue") -> None:
        """Overlay a 'press to continue' hint on the current screen."""
        ...

    def draw_answer_reveal(self, q: dict, *, title: str = "NOBODY GOT IT!",
                           insult: str = "") -> None:
        """Render the correct answer reveal screen (yellow)."""
        ...

    def draw_timeout(self, team_name: str, *, insult: str = "") -> None:
        """Render the TIME'S UP screen."""
        ...

    def draw_scores(self, scores: dict, team_config: dict, *,
                    final: bool = False) -> None:
        """Render the scoreboard."""
        ...

    def animate_falling_text(self, text: str, style: str,
                             duration: float = 1.5) -> None:
        """Animate text falling from top to center. Blocks for duration."""
        ...

    def draw_ready(self, team_config: dict) -> None:
        """Render the ready screen with title art and team list."""
        ...

    # ── Setup/waiting screens ──

    def draw_waiting(self, title: str, subtitle: str,
                     items: list[tuple[str, bool]], status: str) -> None:
        """Render a waiting/progress screen.

        items: list of (label, done) tuples.
        """
        ...

    def draw_buzzer_assign(self, current_name: str, current_color: str,
                           assigned: dict, team_config: dict) -> None:
        """Render the buzzer assignment screen.

        current_name: name of the team currently pressing their buzzer.
        assigned: {slot_num: {name, color, buzzer_num}} for already-done teams.
        """
        ...

    def draw_error(self, message: str, detail: str = "") -> None:
        """Render an error screen."""
        ...

    # ── Input ──

    def get_command(self, timeout: float = 0) -> str | None:
        """Poll for a command.

        timeout=0: non-blocking, return immediately (None if no input).
        timeout>0: block up to timeout seconds.

        Returns one of: "a", "b", "c", "r", "s", "enter", "escape",
        "up", "down", "left", "right", "space", or None.
        """
        ...

    def wait_for_key(self) -> str | None:
        """Block until any key/command is received. Returns the command string."""
        ...

    def flush_input(self) -> None:
        """Discard any buffered input."""
        ...
