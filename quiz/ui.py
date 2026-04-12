#!/usr/bin/env python3
"""Quiz UI entry point.

Orchestrates: settings → buzzer connection → team setup → game loop.
All heavy lifting lives in the submodules:
    quiz/constants.py    — constants & ASCII art
    quiz/drawing.py      — curses drawing primitives & question render
    quiz/insults.py      — insult pack loading + resolve_insult helper
    quiz/led_show.py     — LED choreography
    quiz/settings.py     — settings screen
    quiz/team_setup.py   — color picker, team name entry, client registration
    quiz/feedback.py     — feedback / answer-reveal / scoreboard screens
    quiz/flow.py         — run_question state machine
"""

import curses
import logging
import os
import threading

from buzzers.buzzer_remote import RemoteBuzzerController
from leds.klopfklopf import LEDController
from leds.stub import NoOpLEDController
from quiz.constants import TITLE_ART
from quiz.drawing import center_text, draw_separator
from quiz.feedback import show_scores
from quiz.flow import run_question
from quiz.game_master_server import start_game_master_server
from quiz.game_state import GameState
from quiz.led_show import leds_idle_rainbow
from quiz.settings import show_settings
from quiz.team_answer_source import TeamAnswerSource
from quiz.team_setup import (
    assign_buzzers, setup_teams,
    wait_for_registrations, wait_for_team_configs,
)
from sound.sound import Sound

# Logging — writes to file so it doesn't interfere with curses
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quiz.log")
logging.basicConfig(
    filename=LOG_FILE, level=logging.DEBUG,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("quiz.ui")


def _init_color_pairs():
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_GREEN)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)     # fire
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # fire highlight


def _no_buzzers_error(stdscr, buzzer_url):
    stdscr.clear()
    stdscr.addstr(0, 0, f"No buzzers found at {buzzer_url}")
    stdscr.addstr(1, 0, "Is buzzer_server.py running on the RPi?")
    stdscr.addstr(3, 0, "Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()


def _draw_ready_screen(stdscr, team_config, leds):
    """Display the title + team color list, then wait for any key."""
    rows, _ = stdscr.getmaxyx()
    stdscr.clear()

    art_start = rows // 2 - len(TITLE_ART) - 4
    for i, line in enumerate(TITLE_ART):
        center_text(stdscr, art_start + i, line, curses.A_BOLD)

    draw_separator(stdscr, art_start + len(TITLE_ART) + 1)

    team_start = art_start + len(TITLE_ART) + 3
    for i, (_, tc) in enumerate(team_config.items()):
        center_text(stdscr, team_start + i,
                    f"  {tc['name']}: {tc['color_name']}  ", curses.A_BOLD)

    center_text(stdscr, team_start + len(team_config) + 2,
                "Press any key to start", curses.A_DIM)
    leds_idle_rainbow(leds, team_config)
    stdscr.refresh()
    stdscr.getch()


def main(stdscr):
    curses.curs_set(0)
    _init_color_pairs()

    ctrl = None
    gm_server = None
    leds = None
    snd = None

    try:
        # Hardware init inside try/finally so a failed Sound() doesn't leak
        # an open LEDController.
        try:
            leds = LEDController()
            leds.open()
        except RuntimeError:
            log.warning("LED controller not found — running without LEDs")
            leds = NoOpLEDController()
        snd = Sound()

        config = show_settings(stdscr)
        answer_timeout = config["answer_timeout"]
        buzzer_url = config["buzzer_url"]
        questions = config["questions"]
        insult_pack = config["insult_pack"]
        insult_ai_obj = config["insult_ai"]
        is_multi = config["multi_client"]
        gm_port = config["gm_port"]
        log.info("Config: timeout=%.0f, url=%s, questions=%d, insult_pack=%s, "
                 "insult_ai=%s, multi=%s",
                 answer_timeout, buzzer_url, len(questions),
                 bool(insult_pack), bool(insult_ai_obj), is_multi)

        # Connect to RPi buzzer server
        ctrl = RemoteBuzzerController(buzzer_url)
        ctrl.start()

        buzzers_nums = ctrl.get_buzzers()
        if not buzzers_nums:
            _no_buzzers_error(stdscr, buzzer_url)
            return

        buzzers = [(num, None) for num in buzzers_nums]

        # Multi-client setup — clients register with the master
        game_state = None
        answer_source = None
        if is_multi:
            num_teams = len(buzzers_nums)
            game_state = GameState()
            gm_server = start_game_master_server(game_state, port=gm_port,
                                                 max_teams=num_teams)
            log.info("Multi-client: GM server on port %d, waiting for %d clients",
                     gm_port, num_teams)

        # Prime AI insult session in background while teams set up
        if insult_ai_obj:
            threading.Thread(target=insult_ai_obj.prime, daemon=True).start()

        if is_multi:
            # Step 1: wait for all clients to register
            registered = wait_for_registrations(stdscr, num_teams, game_state, leds)
            team_urls = {num: url for num, url in registered.items()}

            # Step 2: wait for all teams to pick color + name
            team_config = wait_for_team_configs(stdscr, num_teams, game_state, leds)

            # Step 3: buzzer assignment
            buzzer_map = assign_buzzers(stdscr, team_config, ctrl, leds, game_state)

            # Re-key by actual physical buzzer numbers
            team_config = {buzzer_map[slot]: cfg for slot, cfg in team_config.items()}
            team_urls = {buzzer_map[slot]: url for slot, url in team_urls.items()}
            answer_source = TeamAnswerSource(team_urls)
            buzzers = [(num, None) for num in sorted(team_config.keys())]
            # Push final team data so clients can show it during ready screen
            game_state.update(
                teams={str(k): v for k, v in team_config.items()},
                scores={str(k): 0 for k in team_config},
            )
        else:
            team_config = setup_teams(stdscr, buzzers, leds)
        _draw_ready_screen(stdscr, team_config, leds)

        # Quiz loop
        scores = {num: 0 for num, _ in buzzers}
        total = len(questions)

        for i, q in enumerate(questions):
            is_last = (i == total - 1)
            deltas = run_question(
                stdscr, q, i + 1, total, ctrl, leds, team_config, snd,
                answer_timeout=answer_timeout,
                is_last_question=is_last,
                insult_pack=insult_pack,
                insult_ai_obj=insult_ai_obj,
                scores=scores,
                game_state=game_state,
                answer_source=answer_source,
            )
            for buzzer_num, delta in deltas.items():
                scores[buzzer_num] += delta

            if i < total - 1:
                show_scores(stdscr, leds, snd, scores, team_config,
                            game_state=game_state)

        show_scores(stdscr, leds, snd, scores, team_config,
                    final=True, game_state=game_state)

    except KeyboardInterrupt:
        pass
    finally:
        if leds is not None:
            try:
                leds.stop()
                leds.off()
                leds.close()
            except Exception:
                pass
        if ctrl is not None:
            try:
                ctrl.stop()
            except Exception:
                pass
        if gm_server is not None:
            try:
                gm_server.shutdown()
                gm_server.server_close()
            except Exception:
                pass


if __name__ == "__main__":
    curses.wrapper(main)
