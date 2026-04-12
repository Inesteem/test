"""Drawing primitives, animations, and question rendering.

All curses-based rendering helpers live here. Depends on quiz/constants.py
for ASCII art and box-drawing characters.
"""

import curses
import time

from quiz.constants import (
    ART_FIRE,
    BAR_EMPTY,
    BAR_FULL,
    BOX_BL,
    BOX_BR,
    BOX_H,
    BOX_TL,
    BOX_TR,
    BOX_V,
    BOX_bl,
    BOX_br,
    BOX_h,
    BOX_tl,
    BOX_tr,
    BOX_v,
)


# ── Primitive helpers ──

def center_text(win, row, text, attr=0):
    """Draw text centered on a row. No-op if the row is out of bounds."""
    rows, cols = win.getmaxyx()
    if row < 0 or row >= rows:
        return
    col = max(0, (cols - len(text)) // 2)
    try:
        win.addstr(row, col, text[:cols], attr)
    except curses.error:
        pass


def draw_box(win, top, left, height, width, double=True):
    """Draw a box-drawing frame. No-op if it would go offscreen."""
    rows, cols = win.getmaxyx()
    if double:
        tl, tr, bl, br, h, v = BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V
    else:
        tl, tr, bl, br, h, v = BOX_tl, BOX_tr, BOX_bl, BOX_br, BOX_h, BOX_v

    if top < 0 or left < 0 or top + height > rows or left + width > cols:
        return

    try:
        win.addstr(top, left, tl + h * (width - 2) + tr)
        win.addstr(top + height - 1, left, bl + h * (width - 2) + br)
        for r in range(top + 1, top + height - 1):
            win.addstr(r, left, v)
            win.addstr(r, left + width - 1, v)
    except curses.error:
        pass


def draw_separator(win, row, attr=None):
    """Draw a dim horizontal separator line."""
    if attr is None:
        attr = curses.A_DIM
    _, cols = win.getmaxyx()
    try:
        win.addstr(row, 2, BOX_h * (cols - 4), attr)
    except curses.error:
        pass


def draw_progress_bar(win, row, elapsed, timeout, width=30):
    """Draw a progress bar that drains as time runs out, changing color."""
    _, cols = win.getmaxyx()
    progress = max(0.0, 1.0 - elapsed / timeout)
    filled = int(progress * width)
    bar = BAR_FULL * filled + BAR_EMPTY * (width - filled)

    if progress > 0.66:
        attr = curses.color_pair(1) | curses.A_BOLD
    elif progress > 0.33:
        attr = curses.color_pair(3) | curses.A_BOLD
    else:
        attr = curses.color_pair(2) | curses.A_BOLD

    col = max(0, (cols - width - 2) // 2)
    try:
        win.addstr(row, col, f"[{bar}]", attr)
    except curses.error:
        pass


def fill_screen(win, color_pair):
    """Clear the window and apply a background color pair."""
    win.bkgd(" ", curses.color_pair(color_pair))
    win.clear()


# ── Text utilities ──

def wrap_text(text, width):
    """Wrap text to fit within width, breaking at word boundaries."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        elif current:
            current += " " + word
        else:
            current = word
    if current:
        lines.append(current)
    return lines


def edit_text_field(win, row, col, current, max_len, attr=0):
    """Inline text editor. Returns the edited string on Enter, current on Escape."""
    buf = list(current)
    cursor = len(buf)
    curses.curs_set(1)

    while True:
        try:
            win.addstr(row, col, " " * (max_len + 2), attr)
            display = "".join(buf)
            win.addstr(row, col, display[:max_len], attr)
            win.move(row, col + min(cursor, max_len))
        except curses.error:
            pass
        win.refresh()

        key = win.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            curses.curs_set(0)
            return "".join(buf)
        elif key == 27:  # Escape
            curses.curs_set(0)
            return current
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
        elif key == curses.KEY_LEFT and cursor > 0:
            cursor -= 1
        elif key == curses.KEY_RIGHT and cursor < len(buf):
            cursor += 1
        elif 32 <= key <= 126 and len(buf) < max_len:
            buf.insert(cursor, chr(key))
            cursor += 1


# ── Fire & ripple effects ──

def draw_fire_columns(win, box_top, box_left, box_w, box_h, frame=0):
    """Draw animated fire columns on left and right of the question box."""
    rows, cols = win.getmaxyx()
    fire_len = len(ART_FIRE)
    if fire_len == 0:
        return

    for i in range(box_h):
        row = box_top + i
        if row < 0 or row >= rows:
            continue
        fire_idx = (i + frame) % fire_len
        fire_line = ART_FIRE[fire_idx]
        # Alternate red and yellow for flickering effect
        attr = curses.color_pair(4 if (i + frame) % 3 != 0 else 5) | curses.A_BOLD

        left_col = box_left - len(fire_line) - 1
        if left_col >= 0:
            try:
                win.addstr(row, left_col, fire_line, attr)
            except curses.error:
                pass

        right_col = box_left + box_w + 1
        if right_col + len(fire_line) <= cols:
            try:
                win.addstr(row, right_col, fire_line, attr)
            except curses.error:
                pass


def ripple_choices(win, choice_rows, cols, frame):
    """Flash one choice row with a yellow highlight for a ripple effect."""
    if not choice_rows:
        return
    target_row = choice_rows[frame % len(choice_rows)]
    try:
        attr = curses.color_pair(3) | curses.A_BOLD
        win.chgat(target_row, 2, cols - 4, attr)
    except curses.error:
        pass


# ── Question rendering ──

def draw_question(win, q, question_num, total, status_line=None, ranking_line=None,
                  elapsed=None, timeout=None, is_final=False, fire_frame=0,
                  ripple_frame=-1):
    """Render the full question screen with choices, progress bar, and effects."""
    win.bkgd(" ", curses.color_pair(0))
    win.clear()
    rows, cols = win.getmaxyx()

    # Wrap question text to fit inside the box
    inner_width = min(66, cols - 8)
    q_lines = wrap_text(q["question"].upper(), inner_width)

    # Main content box — height adapts to question length
    box_w = min(70, cols - 4)
    q_height = len(q_lines)
    box_h = q_height + 16  # question lines + 3 answers * 3 + padding
    box_top = rows // 2 - box_h // 2 - 2
    box_left = (cols - box_w) // 2
    draw_box(win, box_top, box_left, box_h, box_w)

    # Question number header
    if is_final:
        header = " FINAL QUESTION "
    else:
        header = f" Question {question_num}/{total} "
    center_text(win, box_top, header,
                curses.color_pair(2) | curses.A_BOLD if is_final else curses.A_DIM)

    # Question text — ALLCAPS, wrapped, bold white
    for j, line in enumerate(q_lines):
        center_text(win, box_top + 2 + j, line, curses.A_BOLD)

    sep_row = box_top + 2 + q_height + 1
    draw_separator(win, sep_row)

    # Answer choices with 2-row spacing between each
    choice_start = sep_row + 2
    choice_rows = []
    for i, (key, value) in enumerate(q["choices"].items()):
        choice_text = f"   {key.upper()})  {value}   "
        row = choice_start + i * 3
        center_text(win, row, choice_text, curses.A_BOLD)
        choice_rows.append(row)

    if ripple_frame >= 0:
        ripple_choices(win, choice_rows, cols, ripple_frame)

    if is_final:
        draw_fire_columns(win, box_top, box_left, box_w, box_h, fire_frame)

    if elapsed is not None and timeout is not None:
        draw_progress_bar(win, box_top + box_h + 1, elapsed, timeout)

    if status_line:
        center_text(win, box_top + box_h + 3, status_line, curses.A_DIM)

    if ranking_line:
        center_text(win, box_top + box_h + 4, ranking_line, curses.A_DIM)

    win.refresh()


def animate_falling_text(win, text, color_pair, duration=1.5):
    """Animate text falling from top to center with ease-out timing."""
    rows, _ = win.getmaxyx()
    target_row = rows // 2
    steps = target_row
    if steps <= 0:
        return
    dt = duration / steps
    for row in range(steps):
        win.clear()
        center_text(win, row, text, curses.color_pair(color_pair) | curses.A_BOLD)
        win.refresh()
        progress = row / steps
        time.sleep(dt * (0.3 + 0.7 * (1 - progress)))

    win.clear()
    center_text(win, target_row, text, curses.color_pair(color_pair) | curses.A_BOLD)
    win.refresh()
    time.sleep(3.0)


# ── Team-config accessors ──

def team_label(team_config, buzzer_num):
    return team_config[buzzer_num]["name"]


def team_color(team_config, buzzer_num):
    return team_config[buzzer_num]["color"]
