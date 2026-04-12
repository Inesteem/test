"""CursesDisplay — implements the Display protocol using curses.

Wraps the existing drawing primitives from quiz/drawing.py and the
curses-specific rendering that was previously inline in feedback.py.
"""

import curses
import time

from quiz.constants import (
    ART_CHECK,
    ART_CROSS,
    ART_QUESTION,
    BAR_EMPTY,
    BAR_FULL,
    TITLE_ART,
)
from quiz.drawing import (
    animate_falling_text as _curses_animate_falling_text,
    center_text,
    draw_box,
    draw_question as _curses_draw_question,
    draw_separator,
    fill_screen,
    team_color,
    team_label,
    wrap_text,
)


class CursesDisplay:
    """Display implementation backed by a curses window."""

    def __init__(self, win):
        self._win = win

    # ── Game screens ──

    def draw_question(self, q, question_num, total, *, status_line="",
                      ranking_line="", elapsed=None, timeout=None,
                      is_final=False, fire_frame=0, ripple_frame=-1):
        _curses_draw_question(
            self._win, q, question_num, total,
            status_line=status_line, ranking_line=ranking_line,
            elapsed=elapsed, timeout=timeout,
            is_final=is_final, fire_frame=fire_frame,
            ripple_frame=ripple_frame,
        )

    def draw_feedback(self, correct, team_name, *, question_text="",
                      correct_answer="", insult=""):
        pair = 1 if correct else 2
        art = ART_CHECK if correct else ART_CROSS
        art_start = 2
        msg = (f"CORRECT! +1 for {team_name}!"
               if correct else f"WRONG! -1 for {team_name}.")
        msg_row = art_start + len(art) + 1

        fill_screen(self._win, pair)
        rows, cols = self._win.getmaxyx()
        attr = curses.color_pair(pair) | curses.A_BOLD
        dim_attr = curses.color_pair(pair)

        for i, line in enumerate(art):
            center_text(self._win, art_start + i, line, attr)
        center_text(self._win, msg_row, msg, attr)

        next_row = msg_row + 2
        if question_text:
            q_lines = wrap_text(question_text, min(cols - 8, 60))
            for j, line in enumerate(q_lines):
                center_text(self._win, next_row + j, line, dim_attr)
            next_row += len(q_lines) + 1

        if correct and correct_answer:
            center_text(self._win, next_row, correct_answer, attr)

        if insult:
            insult_lines = wrap_text(f'"{insult}"', min(cols - 8, 70))
            start = rows // 2 + 4 - len(insult_lines) // 2
            for j, line in enumerate(insult_lines):
                center_text(self._win, start + j, line, attr)

        self._win.refresh()

    def draw_continue_prompt(self, text="Press Enter to continue"):
        rows, _ = self._win.getmaxyx()
        center_text(self._win, rows - 2, text, curses.A_DIM)
        self._win.refresh()

    def draw_answer_reveal(self, q, *, title="NOBODY GOT IT!", insult=""):
        fill_screen(self._win, 3)
        rows, cols = self._win.getmaxyx()
        attr = curses.color_pair(3) | curses.A_BOLD
        dim_attr = curses.color_pair(3)

        art_start = rows // 2 - len(ART_QUESTION) - 4
        for i, line in enumerate(ART_QUESTION):
            center_text(self._win, art_start + i, line, attr)

        center_text(self._win, rows // 2 - 3, title, attr)

        insult_height = 0
        if insult:
            insult_lines = wrap_text(f'"{insult}"', min(60, cols - 8))
            for j, line in enumerate(insult_lines):
                center_text(self._win, rows // 2 - 1 + j, line, attr)
            insult_height = len(insult_lines)

        q_start = rows // 2 + 1 + insult_height
        q_lines = wrap_text(q["question"].upper(), min(60, cols - 8))
        for j, line in enumerate(q_lines):
            center_text(self._win, q_start + j, line, dim_attr)

        answer_text = f"{q['answer'].upper()}) {q['choices'][q['answer']]}"
        answer_row = q_start + len(q_lines) + 1
        center_text(self._win, answer_row, "The answer was:", dim_attr)
        center_text(self._win, answer_row + 1, answer_text, attr)

        if insult:
            center_text(self._win, rows - 2, "Press Enter to continue",
                        curses.color_pair(3) | curses.A_DIM)

        self._win.refresh()

    def draw_timeout(self, team_name, *, insult=""):
        fill_screen(self._win, 2)
        rows, _ = self._win.getmaxyx()
        attr = curses.color_pair(2) | curses.A_BOLD

        for i, line in enumerate(ART_CROSS):
            center_text(self._win, rows // 2 - 4 + i, line, attr)
        center_text(self._win, rows // 2 + 2,
                    f"TIME'S UP! {team_name} ran out of time.", attr)

        if insult:
            center_text(self._win, rows // 2 + 4, f'"{insult}"', attr)

        self._win.refresh()

    def draw_scores(self, scores, team_config, *, final=False):
        self._win.bkgd(" ", curses.color_pair(0))
        self._win.clear()
        rows, cols = self._win.getmaxyx()

        min_score = min(scores.values()) if scores else 0
        max_score = max(scores.values()) if scores else 1
        score_range = max(max_score, 1) - min(min_score, 0)
        bar_max_width = max(5, min(30, cols // 2 - 10))
        sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        box_w = min(55, cols - 4)
        box_h = len(sorted_teams) * 2 + 6
        box_top = rows // 2 - box_h // 2
        box_left = (cols - box_w) // 2
        draw_box(self._win, box_top, box_left, box_h, box_w)

        title = " FINAL SCORES " if final else " Scores "
        center_text(self._win, box_top, title, curses.A_BOLD)

        for i, (t, score) in enumerate(sorted_teams):
            name = team_label(team_config, t)
            row = box_top + 2 + i * 2
            rank = i + 1
            rank_str = f" {rank}. "

            if score > 0:
                bar_width = int((score / score_range) * bar_max_width) if score_range else 0
                bar = BAR_FULL * bar_width + BAR_EMPTY * (bar_max_width - bar_width)
                bar_attr = curses.color_pair(1) | curses.A_BOLD
            elif score < 0:
                bar_width = int((abs(score) / score_range) * bar_max_width) if score_range else 0
                bar = BAR_FULL * bar_width + BAR_EMPTY * (bar_max_width - bar_width)
                bar_attr = curses.color_pair(2) | curses.A_BOLD
            else:
                bar = BAR_EMPTY * bar_max_width
                bar_attr = curses.A_DIM

            score_str = f"+{score}" if score > 0 else str(score)
            prefix = f"{rank_str}{name:<10} "
            suffix = f" {score_str}"
            base_attr = curses.A_BOLD if rank == 1 and final else 0

            full_line = f"{prefix}{bar}{suffix}"
            col = max(0, (cols - len(full_line)) // 2)
            try:
                self._win.addstr(row, col, prefix, base_attr)
                self._win.addstr(row, col + len(prefix), bar, bar_attr)
                score_attr = curses.color_pair(2) | curses.A_BOLD if score < 0 else base_attr
                self._win.addstr(row, col + len(prefix) + len(bar), suffix, score_attr)
            except curses.error:
                pass

        if final and sorted_teams:
            winner_name = team_label(team_config, sorted_teams[0][0])
            draw_separator(self._win, box_top + box_h - 3)
            center_text(self._win, box_top + box_h - 2, f"{winner_name} wins!",
                        curses.A_BOLD | curses.A_REVERSE)
            center_text(self._win, box_top + box_h + 1, "Press any key to exit",
                        curses.A_DIM)
        elif sorted_teams:
            center_text(self._win, box_top + box_h + 1,
                        "Press any key for next question", curses.A_DIM)
        else:
            center_text(self._win, box_top + box_h + 1,
                        "Press any key to continue", curses.A_DIM)

        self._win.refresh()

    def animate_falling_text(self, text, style, duration=1.5):
        color_pair = 1 if style == "correct" else 2
        _curses_animate_falling_text(self._win, text, color_pair, duration)

    def draw_ready(self, team_config):
        rows, _ = self._win.getmaxyx()
        self._win.clear()

        art_start = rows // 2 - len(TITLE_ART) - 4
        for i, line in enumerate(TITLE_ART):
            center_text(self._win, art_start + i, line, curses.A_BOLD)

        draw_separator(self._win, art_start + len(TITLE_ART) + 1)

        team_start = art_start + len(TITLE_ART) + 3
        for i, (_, tc) in enumerate(team_config.items()):
            center_text(self._win, team_start + i,
                        f"  {tc['name']}: {tc['color_name']}  ", curses.A_BOLD)

        center_text(self._win, team_start + len(team_config) + 2,
                    "Press any key to start", curses.A_DIM)
        self._win.refresh()

    # ── Setup/waiting screens ──

    def draw_waiting(self, title, subtitle, items, status):
        self._win.bkgd(" ", curses.color_pair(0))
        self._win.clear()
        rows, cols = self._win.getmaxyx()

        box_h = len(items) * 2 + 8
        box_w = min(55, cols - 4)
        box_top = max(0, rows // 2 - box_h // 2)
        box_left = (cols - box_w) // 2
        draw_box(self._win, box_top, box_left, box_h, box_w)

        center_text(self._win, box_top + 1, f" {title} ", curses.A_BOLD)
        center_text(self._win, box_top + 2, subtitle, curses.A_DIM)
        draw_separator(self._win, box_top + 3)

        for i, (label, done) in enumerate(items):
            row = box_top + 5 + i * 2 if len(items) <= 6 else box_top + 5 + i
            attr = curses.A_BOLD if done else curses.A_DIM
            center_text(self._win, row, label, attr)

        status_row = box_top + box_h - 2
        is_done = all(done for _, done in items)
        attr = curses.A_BOLD | curses.A_REVERSE if is_done else curses.A_DIM
        center_text(self._win, status_row, status, attr)

        self._win.refresh()

    def draw_buzzer_assign(self, current_name, current_color, assigned, team_config):
        self._win.bkgd(" ", curses.color_pair(0))
        self._win.clear()
        rows, cols = self._win.getmaxyx()

        num_slots = len(team_config)
        box_h = num_slots + 10
        box_w = min(55, cols - 4)
        box_top = max(0, rows // 2 - box_h // 2)
        box_left = (cols - box_w) // 2
        draw_box(self._win, box_top, box_left, box_h, box_w)

        center_text(self._win, box_top + 1, " BUZZER ASSIGNMENT ", curses.A_BOLD)
        center_text(self._win, box_top + 2, "Esc = skip remaining",
                    curses.A_DIM)
        draw_separator(self._win, box_top + 3)

        center_text(self._win, box_top + 5,
                    f">>> {current_name}: PRESS YOUR BUZZER! <<<",
                    curses.A_BOLD | curses.A_REVERSE)

        row = box_top + 7
        for slot_num in sorted(team_config.keys()):
            if slot_num in assigned:
                info = assigned[slot_num]
                label = f"  \u2713 {info['name']}: buzzer {info['buzzer_num']}  "
                center_text(self._win, row, label, curses.A_BOLD)
            else:
                label = f"    {team_config[slot_num]['name']}: waiting...  "
                center_text(self._win, row, label, curses.A_DIM)
            row += 1

        self._win.refresh()

    def draw_error(self, message, detail=""):
        self._win.clear()
        self._win.addstr(0, 0, message)
        if detail:
            self._win.addstr(1, 0, detail)
        self._win.addstr(3, 0, "Press any key to exit.")
        self._win.refresh()

    # ── Input ──

    def get_command(self, timeout=0):
        if timeout == 0:
            self._win.nodelay(True)
            key = self._win.getch()
            self._win.nodelay(False)
            if key == -1:
                return None
            return self._key_to_command(key)
        else:
            self._win.nodelay(True)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                key = self._win.getch()
                if key != -1:
                    cmd = self._key_to_command(key)
                    if cmd is not None:
                        self._win.nodelay(False)
                        return cmd
                time.sleep(0.05)
            self._win.nodelay(False)
            return None

    def wait_for_key(self):
        self.flush_input()
        self._win.nodelay(False)
        key = self._win.getch()
        return self._key_to_command(key)

    def flush_input(self):
        curses.flushinp()

    # ── Internal ──

    @staticmethod
    def _key_to_command(key):
        if 0 <= key <= 255:
            ch = chr(key).lower()
            if ch in ("a", "b", "c", "r", "s"):
                return ch
            if key in (10, 13):
                return "enter"
            if key == 27:
                return "escape"
            if key == 32:
                return "space"
            return None
        if key == curses.KEY_ENTER:
            return "enter"
        if key == curses.KEY_UP:
            return "up"
        if key == curses.KEY_DOWN:
            return "down"
        if key == curses.KEY_LEFT:
            return "left"
        if key == curses.KEY_RIGHT:
            return "right"
        return None
