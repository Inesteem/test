"""Feedback screens: show_feedback, show_answer_reveal, show_scores.

All full-screen game screens that display the result of a question round
or the current standings.
"""

import curses
import logging
import random
import time

from quiz.constants import (
    ART_CHECK,
    ART_CROSS,
    ART_QUESTION,
    BAR_EMPTY,
    BAR_FULL,
    LAME_TEXTS,
    SAVAGE_TEXTS,
)
from quiz.drawing import (
    animate_falling_text,
    center_text,
    draw_box,
    draw_separator,
    fill_screen,
    team_color,
    team_label,
    wrap_text,
)
from quiz.insults import insult_pick, resolve_insult
from quiz.led_show import leds_correct, leds_times_up, leds_wrong

log = logging.getLogger("quiz.feedback")


def _score_summary(scores, team_config):
    """Build a name→score dict suitable for passing to the AI prompt builder."""
    return {team_config[b]["name"]: s for b, s in (scores or {}).items()
            if b in team_config}


def _feedback_event(correct, answer_time):
    """Map (correct, answer_time) to the event name used by the insult system."""
    if correct and answer_time is not None and answer_time < 3.0:
        return "correct_fast"
    if correct:
        return "correct_slow"
    return "wrong"


def _draw_feedback_layout(win, pair, art, art_start, msg_row, msg,
                          insult, insult_lines_cache=None,
                          correct_answer="", correct=True,
                          question_text=""):
    """Draw the feedback screen in its canonical layout.

    If insult_lines_cache is provided, use it (avoids re-wrapping).
    Returns (insult_lines, insult_start_row) for the redraw path.
    """
    fill_screen(win, pair)
    rows, cols = win.getmaxyx()
    attr = curses.color_pair(pair) | curses.A_BOLD
    dim_attr = curses.color_pair(pair)

    for i, line in enumerate(art):
        center_text(win, art_start + i, line, attr)
    center_text(win, msg_row, msg, attr)

    # Show the question and answer(s) below the main message
    next_row = msg_row + 2
    if question_text:
        q_lines = wrap_text(question_text, min(cols - 8, 60))
        for j, line in enumerate(q_lines):
            center_text(win, next_row + j, line, dim_attr)
        next_row += len(q_lines) + 1

    if correct and correct_answer:
        center_text(win, next_row, correct_answer, attr)

    lines = insult_lines_cache
    start = None
    if insult:
        if lines is None:
            lines = wrap_text(f'"{insult}"', min(cols - 8, 70))
        start = rows // 2 + 4 - len(lines) // 2
        for j, line in enumerate(lines):
            center_text(win, start + j, line, attr)

    return lines, start


def show_feedback(win, leds, snd, correct, name, team_config, buzzer_num,
                  answer_time=None, insult_pack=None, insult_ai_obj=None,
                  question_text="", given_answer="", correct_answer="",
                  scores=None, game_state=None):
    """Display feedback for a team's answer — green for correct, red for wrong."""
    pair = 1 if correct else 2
    log.info("show_feedback: correct=%s, name=%s, answer_time=%s, ai=%s, pack=%s",
             correct, name, answer_time, bool(insult_ai_obj), bool(insult_pack))

    if game_state:
        game_state.update(
            phase="feedback",
            active_team=None,
            feedback=("CORRECT" if correct else "WRONG"),
            feedback_team=name,
            feedback_team_num=buzzer_num,
            feedback_correct=correct,
            time_remaining=None,
        )

    event = _feedback_event(correct, answer_time)

    # Kick off AI insult generation early (runs in background while we draw)
    if insult_ai_obj:
        color_name = team_config.get(buzzer_num, {}).get("color_name", "")
        insult_ai_obj.generate_async(
            event, question=question_text, answer_time=answer_time,
            team_name=name, given_answer=given_answer,
            correct_answer=correct_answer, was_correct=correct,
            scores=_score_summary(scores, team_config), team_color=color_name,
        )

    art = ART_CHECK if correct else ART_CROSS
    art_start = 2
    msg = (f"CORRECT! +1 for {name}!" if correct
           else f"WRONG! -1 for {name}.")
    msg_row = art_start + len(art) + 1

    # Paint the art/message immediately so the player sees feedback while
    # we block on AI resolution below. The insult will be drawn in the
    # post-effects redraw once resolved.
    answer_kw = dict(correct=correct)
    if correct:
        answer_kw.update(question_text=question_text,
                         correct_answer=correct_answer)
    _draw_feedback_layout(win, pair, art, art_start, msg_row, msg, "",
                          **answer_kw)
    win.refresh()

    # Resolve the insult with full fallback chain:
    #   AI (with suspense music) → static pack → hardcoded pool
    insult = ""
    if insult_ai_obj:
        suspense_handle = snd.suspense(background=True, loop=True)
        try:
            insult = insult_ai_obj.get_result(timeout=20.0)
        finally:
            # suspense() may return None if the sound backend isn't ready
            if suspense_handle is not None:
                suspense_handle.stop()
        log.info("AI insult returned: %r", insult[:80] if insult else "(empty)")
    if not insult and insult_pack:
        insult = resolve_insult(event, insult_pack=insult_pack)
    if not insult and (insult_ai_obj or insult_pack):
        insult = random.choice(SAVAGE_TEXTS if correct else LAME_TEXTS)

    # Now redraw with the resolved insult
    insult_lines, _ = _draw_feedback_layout(
        win, pair, art, art_start, msg_row, msg, insult, **answer_kw,
    )
    win.refresh()
    leds.stop()

    # LED + sound effects
    if correct:
        leds_correct(leds, team_config, buzzer_num)
        snd.correct()
        # SAVAGE animation only when insults are entirely off
        if (answer_time is not None and answer_time < 3.0
                and not insult_pack and not insult_ai_obj):
            animate_falling_text(win, random.choice(SAVAGE_TEXTS), 1)
    else:
        snd.wrong()
        leds_wrong(leds)

    # Post-effects redraw: LEDs/sounds may have run for up to ~1.5s and
    # the terminal rendering may have been affected. Redraw fresh.
    log.info("Post-feedback: insult_ai_obj=%s, have_insult=%s",
             bool(insult_ai_obj), bool(insult))

    if insult_ai_obj:
        # AI mode: wait for Enter (no auto-advance)
        _draw_feedback_layout(win, pair, art, art_start, msg_row, msg,
                              insult, insult_lines_cache=insult_lines,
                              **answer_kw)
        rows, _ = win.getmaxyx()
        center_text(win, rows - 2, "Press Enter to continue", curses.A_DIM)
        win.refresh()
        curses.flushinp()
        win.nodelay(False)
        win.getch()
    else:
        # Non-AI mode: 5-second auto-advance, skippable with Enter
        curses.flushinp()
        win.nodelay(True)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            k = win.getch()
            if k in (curses.KEY_ENTER, 10, 13):
                break
            time.sleep(0.05)

    leds.off()


def show_answer_reveal(win, leds, snd, q, title="NOBODY GOT IT!", insult=""):
    """Show the correct answer with a dramatic yellow reveal screen."""
    fill_screen(win, 3)
    rows, cols = win.getmaxyx()

    # Question mark art
    art_start = rows // 2 - len(ART_QUESTION) - 4
    for i, line in enumerate(ART_QUESTION):
        center_text(win, art_start + i, line, curses.color_pair(3) | curses.A_BOLD)

    center_text(win, rows // 2 - 3, title, curses.color_pair(3) | curses.A_BOLD)

    # Insult prominent, right below the title
    insult_height = 0
    if insult:
        insult_lines = wrap_text(f'"{insult}"', min(60, cols - 8))
        for j, line in enumerate(insult_lines):
            center_text(win, rows // 2 - 1 + j, line,
                        curses.color_pair(3) | curses.A_BOLD)
        insult_height = len(insult_lines)

    # Repeat the question
    q_start = rows // 2 + 1 + insult_height
    q_lines = wrap_text(q["question"].upper(), min(60, cols - 8))
    for j, line in enumerate(q_lines):
        center_text(win, q_start + j, line, curses.color_pair(3))

    # Show correct answer
    answer_text = f"{q['answer'].upper()}) {q['choices'][q['answer']]}"
    answer_row = q_start + len(q_lines) + 1
    center_text(win, answer_row, "The answer was:", curses.color_pair(3))
    center_text(win, answer_row + 1, answer_text, curses.color_pair(3) | curses.A_BOLD)

    if insult:
        center_text(win, rows - 2, "Press Enter to continue",
                    curses.color_pair(3) | curses.A_DIM)

    win.refresh()
    leds.stop()
    leds.candle((255, 170, 40), intensity=0.5)
    snd.dramatic_sting()

    if insult:
        curses.flushinp()
        win.nodelay(False)
        win.getch()
    else:
        time.sleep(5)

    leds.off()


def show_timeout_screen(win, leds, snd, q, name, current_buzzer, team_config,
                        insult_pack, insult_ai_obj, scores):
    """Display the TIME'S UP screen with a timeout insult."""
    fill_screen(win, 2)
    rows, _ = win.getmaxyx()
    for i, line in enumerate(ART_CROSS):
        center_text(win, rows // 2 - 4 + i, line, curses.color_pair(2) | curses.A_BOLD)
    center_text(win, rows // 2 + 2, f"TIME'S UP! {name} ran out of time.",
                curses.color_pair(2) | curses.A_BOLD)

    # Paint the timeout art/message immediately and start sound/LED effects
    # BEFORE blocking on the AI — otherwise the user sees a frozen screen
    # and hears nothing for up to 20 seconds while Claude thinks.
    win.refresh()
    leds.stop()
    leds_times_up(leds)
    snd.times_up()

    color_name = team_config.get(current_buzzer, {}).get("color_name", "")
    insult = resolve_insult(
        "timeout",
        insult_ai_obj=insult_ai_obj,
        insult_pack=insult_pack,
        question=q["question"],
        team_name=name,
        team_color=color_name,
        scores=_score_summary(scores, team_config),
    )
    if not insult and (insult_ai_obj or insult_pack):
        insult = random.choice(LAME_TEXTS)
    if insult:
        center_text(win, rows // 2 + 4, f'"{insult}"',
                    curses.color_pair(2) | curses.A_BOLD)
        win.refresh()

    time.sleep(2)
    leds.off()


def show_nobody_reveal(win, leds, snd, q, insult_pack, insult_ai_obj,
                       scores, team_config):
    """Show 'nobody got it' reveal — falling text insult then answer reveal.

    Kicks off AI generation asynchronously so the times_up sound plays
    immediately instead of after a 20s freeze.
    """
    snd.times_up()

    # Kick off AI in the background — we'll pick up the result after
    # times_up finishes (which takes ~1-2s), then fall back as needed.
    if insult_ai_obj:
        insult_ai_obj.generate_async(
            "nobody",
            question=q["question"],
            scores=_score_summary(scores, team_config),
        )

    insult = ""
    if insult_ai_obj:
        # Give the AI a chance to finish; if not, fall back
        insult = insult_ai_obj.get_result(timeout=10.0)
    if not insult and insult_pack:
        insult = insult_pick(insult_pack, "nobody")
    if not insult:
        insult = random.choice(LAME_TEXTS)
    animate_falling_text(win, insult, 2, duration=2.0)
    show_answer_reveal(win, leds, snd, q, title="NOBODY GOT IT!", insult=insult)


def show_scores(win, leds, snd, scores, team_config, final=False, game_state=None):
    """Display the scoreboard between rounds or as the final reveal."""
    leds.off()
    win.bkgd(" ", curses.color_pair(0))
    win.clear()
    rows, cols = win.getmaxyx()

    if game_state:
        game_state.update(
            phase="scores" if not final else "final_scores",
            active_team=None,
            question_text="",
            choices={},
            time_remaining=None,
            scores={str(k): v for k, v in scores.items()},
        )

    min_score = min(scores.values()) if scores else 0
    max_score = max(scores.values()) if scores else 1
    score_range = max(max_score, 1) - min(min_score, 0)
    bar_max_width = max(5, min(30, cols // 2 - 10))
    sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    box_w = min(55, cols - 4)
    box_h = len(sorted_teams) * 2 + 6
    box_top = rows // 2 - box_h // 2
    box_left = (cols - box_w) // 2
    draw_box(win, box_top, box_left, box_h, box_w)

    title = " FINAL SCORES " if final else " Scores "
    center_text(win, box_top, title, curses.A_BOLD)

    if final:
        leds.candle((255, 170, 40), intensity=0.5)
        snd.dramatic_sting()

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
            win.addstr(row, col, prefix, base_attr)
            win.addstr(row, col + len(prefix), bar, bar_attr)
            score_attr = curses.color_pair(2) | curses.A_BOLD if score < 0 else base_attr
            win.addstr(row, col + len(prefix) + len(bar), suffix, score_attr)
        except curses.error:
            pass

    if final and sorted_teams:
        winner = sorted_teams[0][0]
        winner_name = team_label(team_config, winner)
        winner_clr = team_color(team_config, winner)

        leds.stop()
        leds.strobe(winner_clr, hz=8.0)
        time.sleep(1.0)
        leds.breathe(winner_clr, period=2.0)

        draw_separator(win, box_top + box_h - 3)
        center_text(win, box_top + box_h - 2, f"{winner_name} wins!",
                    curses.A_BOLD | curses.A_REVERSE)
        center_text(win, box_top + box_h + 1, "Press any key to exit", curses.A_DIM)
    elif sorted_teams:
        leader = sorted_teams[0][0]
        leader_clr = team_color(team_config, leader)
        leds.breathe(leader_clr, period=3.0)
        center_text(win, box_top + box_h + 1,
                    "Press any key for next question", curses.A_DIM)
    else:
        center_text(win, box_top + box_h + 1,
                    "Press any key to continue", curses.A_DIM)

    win.refresh()
    curses.flushinp()
    win.nodelay(False)
    win.getch()
