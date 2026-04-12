"""Feedback screens: show_feedback, show_answer_reveal, show_scores.

All full-screen game screens that display the result of a question round
or the current standings.
"""

import logging
import random
import time

from quiz.constants import LAME_TEXTS, SAVAGE_TEXTS
from quiz.drawing import team_color, team_label
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


def show_feedback(display, leds, snd, correct, name, team_config, buzzer_num,
                  answer_time=None, insult_pack=None, insult_ai_obj=None,
                  question_text="", given_answer="", correct_answer="",
                  scores=None, game_state=None):
    """Display feedback for a team's answer — green for correct, red for wrong."""
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
            question_text=question_text,
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

    # Paint the art/message immediately so the player sees feedback while
    # we block on AI resolution below.
    display.draw_feedback(correct, name,
                          question_text=question_text,
                          correct_answer=correct_answer)

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

    # Redraw with the resolved insult
    display.draw_feedback(correct, name,
                          question_text=question_text,
                          correct_answer=correct_answer,
                          insult=insult)
    leds.stop()

    # LED + sound effects
    if correct:
        leds_correct(leds, team_config, buzzer_num)
        snd.correct()
        # SAVAGE animation only when insults are entirely off
        if (answer_time is not None and answer_time < 3.0
                and not insult_pack and not insult_ai_obj):
            display.animate_falling_text(random.choice(SAVAGE_TEXTS), "correct")
    else:
        snd.wrong()
        leds_wrong(leds)

    # Post-effects redraw: LEDs/sounds may have run for up to ~1.5s and
    # the terminal rendering may have been affected. Redraw fresh.
    log.info("Post-feedback: insult_ai_obj=%s, have_insult=%s",
             bool(insult_ai_obj), bool(insult))

    if insult_ai_obj:
        # AI mode: wait for Enter (no auto-advance)
        display.draw_feedback(correct, name,
                              question_text=question_text,
                              correct_answer=correct_answer,
                              insult=insult)
        display.draw_continue_prompt()
        display.wait_for_key()
    else:
        # Non-AI mode: 5-second auto-advance, skippable with Enter
        display.get_command(timeout=5.0)

    leds.off()


def show_answer_reveal(display, leds, snd, q, title="NOBODY GOT IT!", insult=""):
    """Show the correct answer with a dramatic yellow reveal screen."""
    display.draw_answer_reveal(q, title=title, insult=insult)
    leds.stop()
    leds.candle((255, 170, 40), intensity=0.5)
    snd.dramatic_sting()

    if insult:
        display.flush_input()
        display.wait_for_key()
    else:
        time.sleep(5)

    leds.off()


def show_timeout_screen(display, leds, snd, q, name, current_buzzer, team_config,
                        insult_pack, insult_ai_obj, scores):
    """Display the TIME'S UP screen with a timeout insult."""
    # Paint the timeout art/message immediately and start sound/LED effects
    # BEFORE blocking on the AI — otherwise the user sees a frozen screen
    # and hears nothing for up to 20 seconds while Claude thinks.
    display.draw_timeout(name)
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
        display.draw_timeout(name, insult=insult)

    time.sleep(2)
    leds.off()


def show_nobody_reveal(display, leds, snd, q, insult_pack, insult_ai_obj,
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
    display.animate_falling_text(insult, "wrong", duration=2.0)
    show_answer_reveal(display, leds, snd, q, title="NOBODY GOT IT!", insult=insult)


def show_scores(display, leds, snd, scores, team_config, final=False, game_state=None):
    """Display the scoreboard between rounds or as the final reveal."""
    leds.off()

    if game_state:
        game_state.update(
            phase="scores" if not final else "final_scores",
            active_team=None,
            question_text="",
            choices={},
            time_remaining=None,
            scores={str(k): v for k, v in scores.items()},
        )

    display.draw_scores(scores, team_config, final=final)

    if final:
        leds.candle((255, 170, 40), intensity=0.5)
        snd.dramatic_sting()

    if final and scores:
        sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_teams[0][0]
        winner_clr = team_color(team_config, winner)

        leds.stop()
        leds.strobe(winner_clr, hz=8.0)
        time.sleep(1.0)
        leds.breathe(winner_clr, period=2.0)
    elif scores:
        sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        leader = sorted_teams[0][0]
        leader_clr = team_color(team_config, leader)
        leds.breathe(leader_clr, period=3.0)

    display.wait_for_key()
