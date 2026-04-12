"""Game flow — run_question and the phase helpers.

Each question round goes through: phase 1 (buzz-in) → phase 2 (answer cycle).
Phase 2 alternates between "wait for next buzz" (2a) and "team answers" (2b)
until someone gets it right, nobody does, or the game master skips.

All phase helpers return sentinel strings or tuples:
    _R_RESET       — game master pressed 'r', outer loop restarts
    _R_SKIPPED     — game master pressed 's', question is done
    _R_TIMED_OUT   — answer or next-buzz window expired
    _R_BUZZED      — (phase 1/2a) someone buzzed in, move forward
    ("answered", ch, answer_time)  — (phase 2b only) team submitted an answer
"""

import logging
import time

from quiz.constants import DEFAULT_ANSWER_TIMEOUT, POLL_INTERVAL
from quiz.drawing import team_label
from quiz.feedback import (
    show_answer_reveal,
    show_feedback,
    show_nobody_reveal,
    show_timeout_screen,
)
from quiz.led_show import leds_answer_phase, leds_idle_rainbow

log = logging.getLogger("quiz.flow")

# Return sentinels for phase helpers
_R_RESET = "reset"
_R_SKIPPED = "skipped"
_R_TIMED_OUT = "timed_out"
_R_BUZZED = "buzzed"


def _stop_music(handle):
    """Safely stop a background music handle (no-op if already None)."""
    if handle is not None:
        handle.stop()


def _broadcast_state(game_state, phase, **extra):
    """Push a state update to the game master HTTP server.

    Consolidates the team_config / scores serialization so callers don't
    have to repeat the `{str(k): v for k, v in ...}` conversions.
    """
    if game_state is None:
        return

    payload = {"phase": phase}

    scores = extra.pop("scores", None)
    if scores is not None:
        payload["scores"] = {str(k): v for k, v in scores.items()}

    team_config = extra.pop("team_config", None)
    if team_config is not None:
        payload["teams"] = {str(k): v for k, v in team_config.items()}

    payload.update(extra)
    game_state.update(**payload)


def _phase1_buzz_in(display, q, question_num, total, ctrl, leds, team_config, snd,
                    is_last_question, game_state, scores):
    """Phase 1: wait for the first team to buzz in.

    Returns _R_BUZZED / _R_RESET / _R_SKIPPED.
    """
    def _start_music():
        if is_last_question:
            return snd.final_countdown(background=True, loop=True)
        return snd.jeopardy_thinking(background=True, loop=True)

    leds_idle_rainbow(leds, team_config)
    music = _start_music()
    buzz_label = (">>> FINAL QUESTION! BUZZ IN! <<<" if is_last_question
                  else ">>> BUZZ IN! <<<")
    fire_frame = 0

    _broadcast_state(
        game_state, "buzzing",
        active_team=None,
        question_num=question_num, question_total=total,
        question_text=q["question"], choices=q["choices"],
        time_remaining=None,
        feedback_team_num=None, feedback_correct=None,
        scores=scores or {}, team_config=team_config,
    )

    display.draw_question(q, question_num, total,
                          status_line=f"{buzz_label}  (r = reset, s = skip)",
                          is_final=is_last_question, fire_frame=fire_frame)

    try:
        while True:
            cmd = display.get_command()
            if cmd == "r":
                return _R_RESET
            if cmd == "s":
                return _R_SKIPPED

            if len(ctrl.get_ranking()) > 0:
                return _R_BUZZED

            if is_last_question:
                fire_frame += 1
                display.draw_question(q, question_num, total,
                                      status_line=f"{buzz_label}  (r = reset, s = skip)",
                                      is_final=True, fire_frame=fire_frame)

            time.sleep(POLL_INTERVAL)
    finally:
        _stop_music(music)


def _phase2_wait_for_next_buzz(display, q, question_num, total, ctrl, leds, snd,
                               team_config, turn, is_last_question, game_state):
    """Phase 2a: wait up to 5s for another team to buzz after a wrong answer.

    Returns _R_BUZZED / _R_RESET / _R_SKIPPED / _R_TIMED_OUT.
    """
    ranking = ctrl.get_ranking()
    _broadcast_state(game_state, "buzzing", active_team=None, time_remaining=None)
    display.draw_question(q, question_num, total,
                          status_line="Waiting for next buzz...  (r = reset, s = skip)",
                          ranking_line=f"Order so far: {[team_label(team_config, b) for b in ranking]}",
                          is_final=is_last_question, fire_frame=0)
    leds_idle_rainbow(leds, team_config)

    deadline = time.monotonic() + 5
    last_tick_sec = -1
    while time.monotonic() < deadline:
        cmd = display.get_command()
        if cmd == "r":
            return _R_RESET
        if cmd == "s":
            return _R_SKIPPED

        if len(ctrl.get_ranking()) > turn:
            return _R_BUZZED

        sec = int(time.monotonic())
        if sec != last_tick_sec:
            last_tick_sec = sec
            snd.tick(background=True)

        time.sleep(POLL_INTERVAL)

    return _R_TIMED_OUT


def _phase2_answer_countdown(display, q, question_num, total, ctrl, leds, snd,
                             team_config, current_buzzer, answer_timeout,
                             is_last_question, answer_source, game_state, scores):
    """Phase 2b: current buzzer-holder answers within the timeout.

    Returns ("answered", ch, answer_time) / _R_RESET / _R_SKIPPED / _R_TIMED_OUT.
    """
    name = team_label(team_config, current_buzzer)
    buzz_start = time.monotonic()
    led_phase = leds_answer_phase(leds, team_config, current_buzzer,
                                  answer_timeout, answer_timeout, "")

    if answer_source:
        answer_source.reset(current_buzzer)
    _broadcast_state(
        game_state, "answering",
        active_team=current_buzzer,
        question_num=question_num, question_total=total,
        question_text=q["question"], choices=q["choices"],
        time_remaining=answer_timeout, answer_timeout=answer_timeout,
        scores=scores or {}, team_config=team_config,
    )

    display.flush_input()

    fire_frame = 0
    last_countdown = -1

    while True:
        # Game master keyboard: r/s always, a/b/c only in single-player
        cmd = display.get_command()
        if not answer_source and cmd in ("a", "b", "c"):
            return ("answered", cmd, time.monotonic() - buzz_start)
        if cmd == "s":
            return _R_SKIPPED
        if cmd == "r":
            return _R_RESET

        # Multi-client: poll team client for an answer
        if answer_source:
            remote_ans = answer_source.poll_once(current_buzzer)
            if remote_ans in ("a", "b", "c"):
                return ("answered", remote_ans, time.monotonic() - buzz_start)

        elapsed = time.monotonic() - buzz_start
        if elapsed >= answer_timeout:
            return _R_TIMED_OUT

        if game_state:
            game_state.update(time_remaining=answer_timeout - elapsed)

        remaining = answer_timeout - elapsed
        remaining_int = int(remaining)
        fire_frame += 1

        ripple = int(elapsed * 3) if elapsed > answer_timeout * 0.6 else -1

        new_second = remaining_int != last_countdown
        if new_second:
            last_countdown = remaining_int
            snd.tick(background=True)

        # Only fetch ranking when we're about to draw (every second or
        # on ripple/fire frames). No need to HTTP-poll the RPi 10 times
        # per second just for the display label.
        if new_second or ripple >= 0 or is_last_question:
            ranking = ctrl.get_ranking()
            if answer_source:
                status = f"{name}: tap answer on device  (r/s = reset/skip)  [{remaining_int}s]"
            else:
                status = f"{name}: press A, B, or C  (r/s = reset/skip)  [{remaining_int}s]"
            display.draw_question(q, question_num, total,
                                  status_line=status,
                                  ranking_line=f"Order: {[team_label(team_config, b) for b in ranking]}",
                                  elapsed=elapsed, timeout=answer_timeout,
                                  is_final=is_last_question, fire_frame=fire_frame,
                                  ripple_frame=ripple)

        led_phase = leds_answer_phase(leds, team_config, current_buzzer,
                                      remaining, answer_timeout, led_phase)

        time.sleep(POLL_INTERVAL)


def run_question(display, q, question_num, total, ctrl, leds, team_config, snd,
                 answer_timeout=DEFAULT_ANSWER_TIMEOUT, is_last_question=False,
                 insult_pack=None, insult_ai_obj=None, scores=None,
                 game_state=None, answer_source=None):
    """Run a single question round. Returns dict of {buzzer_num: score_delta}.

    Top-level state machine:
        outer while loop → [phase 1 → phase 2 cycle] → return deltas
        reset sentinel from any phase restarts the outer loop.
    """
    while True:
        ctrl.reset()
        score_deltas = {}
        turn = 0

        # Phase 1: initial buzz-in
        p1 = _phase1_buzz_in(display, q, question_num, total, ctrl, leds,
                             team_config, snd, is_last_question, game_state, scores)
        if p1 == _R_RESET:
            continue
        if p1 == _R_SKIPPED:
            show_answer_reveal(display, leds, snd, q, title="SKIPPED!")
            return score_deltas
        # p1 == _R_BUZZED — proceed to phase 2

        # Phase 2: answer cycle. A reset sentinel from any inner phase
        # falls through a `break` statement, which lands on the reset handler
        # below. Every other phase result either returns directly or
        # `continue`s the inner loop.
        while True:
            ranking = ctrl.get_ranking()

            # Phase 2a: wait for next buzz if we've exhausted current ranking
            if turn >= len(ranking):
                p2a = _phase2_wait_for_next_buzz(
                    display, q, question_num, total, ctrl, leds, snd,
                    team_config, turn, is_last_question, game_state,
                )
                if p2a == _R_RESET:
                    break
                if p2a == _R_SKIPPED:
                    show_answer_reveal(display, leds, snd, q, title="SKIPPED!")
                    return score_deltas
                if p2a == _R_TIMED_OUT:
                    show_nobody_reveal(display, leds, snd, q, insult_pack,
                                       insult_ai_obj, scores, team_config)
                    return score_deltas
                # _R_BUZZED — loop back to pick up the new ranking
                continue

            # Phase 2b: current team answers
            current_buzzer = ranking[turn]
            result = _phase2_answer_countdown(
                display, q, question_num, total, ctrl, leds, snd,
                team_config, current_buzzer, answer_timeout,
                is_last_question, answer_source, game_state, scores,
            )

            if result == _R_RESET:
                break
            if result == _R_SKIPPED:
                leds.off()
                show_answer_reveal(display, leds, snd, q, title="SKIPPED!")
                return score_deltas
            if result == _R_TIMED_OUT:
                name = team_label(team_config, current_buzzer)
                show_timeout_screen(display, leds, snd, q, name, current_buzzer,
                                    team_config, insult_pack, insult_ai_obj, scores)
                turn += 1
                continue

            # Answered — result == ("answered", ch, answer_time)
            _, ch, answer_time = result
            name = team_label(team_config, current_buzzer)
            correct = ch == q["answer"]
            given = f"{ch.upper()}) {q['choices'].get(ch, '?')}"
            correct_text = f"{q['answer'].upper()}) {q['choices'][q['answer']]}"
            show_feedback(display, leds, snd, correct, name, team_config, current_buzzer,
                          answer_time, insult_pack, insult_ai_obj,
                          q["question"], given, correct_text, scores,
                          game_state=game_state)

            if correct:
                score_deltas[current_buzzer] = score_deltas.get(current_buzzer, 0) + 1
                leds.off()
                return score_deltas

            score_deltas[current_buzzer] = score_deltas.get(current_buzzer, 0) - 1
            turn += 1

        # Landed here via `break` from an _R_RESET sentinel → restart.
        ctrl.reset()
        leds.off()
        time.sleep(0.3)
        # Fall through to the top of the outer `while True:` which resets
        # score_deltas and turn for a fresh attempt.
