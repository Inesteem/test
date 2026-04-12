#!/usr/bin/env python3
"""Web-based quiz UI entry point.

Replaces the curses terminal with a browser display served via HTTP+SSE.
The game master opens Chrome in kiosk mode on a projector:

    google-chrome --kiosk --app=http://localhost:9000/gm

Usage:
    python3 -m quiz.web_ui [options]

All settings are passed as CLI args (no curses settings screen).
"""

import argparse
import logging
import os
import shutil
import threading

from buzzers.buzzer_remote import RemoteBuzzerController
from leds.klopfklopf import LEDController
from leds.stub import NoOpLEDController
from quiz.feedback import show_scores
from quiz.flow import run_question
from quiz.game_master_server import start_game_master_server
from quiz.game_state import GameState
from quiz.insult_ai import InsultAI, list_agents, load_agent
from quiz.insults import list_insult_packs, load_insult_pack
from quiz.led_show import leds_idle_rainbow
from quiz.questions import list_bundles, load_bundle, prepare_questions
from quiz.team_answer_source import TeamAnswerSource
from quiz.team_setup import (
    assign_buzzers,
    wait_for_registrations, wait_for_team_configs,
)
from quiz.web_display import WebDisplay
from sound.sound import Sound

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quiz.log")
logging.basicConfig(
    filename=LOG_FILE, level=logging.DEBUG,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("quiz.web_ui")


def _parse_args():
    parser = argparse.ArgumentParser(description="Quiz Game Master (Web UI)")

    # Question bundle
    bundles = list_bundles()
    parser.add_argument("--bundle", type=int, default=0,
                        help=f"Question bundle index (0-{len(bundles)-1}, default: 0)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Answer timeout in seconds (default: 30)")

    # Insults
    parser.add_argument("--insult-pack", type=int, default=None,
                        help="Static insult pack index (omit for off)")
    parser.add_argument("--insult-ai", type=int, default=None,
                        help="AI agent index (omit for off)")

    # Network
    parser.add_argument("--rpi-host", default=os.environ.get("BUZZER_RPI_HOST", "192.168.178.41"),
                        help="Buzzer RPi host")
    parser.add_argument("--rpi-port", default=os.environ.get("BUZZER_RPI_PORT", "8888"),
                        help="Buzzer RPi port")
    parser.add_argument("--gm-port", type=int, default=9000,
                        help="Game master HTTP server port (default: 9000)")

    return parser.parse_args()


def main():
    args = _parse_args()

    ctrl = None
    gm_server = None
    leds = None

    try:
        # Hardware
        try:
            leds = LEDController()
            leds.open()
        except RuntimeError:
            log.warning("LED controller not found — running without LEDs")
            leds = NoOpLEDController()
        snd = Sound()

        # Questions
        bundles = list_bundles()
        if not bundles:
            print("No question bundles found in questions/")
            return
        bundle_idx = min(args.bundle, len(bundles) - 1)
        raw_questions = load_bundle(bundles[bundle_idx])
        questions = prepare_questions(raw_questions)
        log.info("Loaded %d questions from bundle %d", len(questions), bundle_idx)

        # Insults
        insult_pack = None
        insult_ai_obj = None
        if args.insult_pack is not None:
            packs = list_insult_packs()
            if args.insult_pack < len(packs):
                insult_pack = load_insult_pack(packs[args.insult_pack])
        if args.insult_ai is not None and shutil.which("claude"):
            agents = list_agents()
            if args.insult_ai < len(agents):
                agent_def = load_agent(agents[args.insult_ai])
                insult_ai_obj = InsultAI(system_prompt=agent_def["system_prompt"])

        # Web display + game master server
        display = WebDisplay()
        game_state = GameState()
        gm_server = start_game_master_server(game_state, port=args.gm_port,
                                             web_display=display)

        buzzer_url = f"http://{args.rpi_host}:{args.rpi_port}"
        print(f"Game master UI: http://localhost:{args.gm_port}/gm")
        print(f"  Chrome kiosk: google-chrome --kiosk --app=http://localhost:{args.gm_port}/gm")
        print(f"Buzzer server:  {buzzer_url}")
        print(f"Questions:      {len(questions)} from {bundles[bundle_idx]}")
        print()
        print("Waiting for browser to connect + buzzers...")

        # Connect to RPi buzzer server
        ctrl = RemoteBuzzerController(buzzer_url)
        ctrl.start()

        buzzers_nums = ctrl.get_buzzers()
        if not buzzers_nums:
            display.draw_error(f"No buzzers found at {buzzer_url}",
                               "Is buzzer_server.py running on the RPi?")
            display.wait_for_key()
            return

        num_teams = len(buzzers_nums)
        gm_server.max_teams = num_teams

        # Prime AI insult session in background
        if insult_ai_obj:
            threading.Thread(target=insult_ai_obj.prime, daemon=True).start()

        # Multi-client flow (web mode is always multi-client)
        # Step 1: wait for all clients to register
        registered = wait_for_registrations(display, num_teams, game_state, leds)
        team_urls = {num: url for num, url in registered.items()}

        # Step 2: wait for all teams to pick color + name
        team_config = wait_for_team_configs(display, num_teams, game_state, leds)

        # Step 3: buzzer assignment
        buzzer_map = assign_buzzers(display, team_config, ctrl, leds, game_state)

        # Re-key by actual physical buzzer numbers
        team_config = {buzzer_map[slot]: cfg for slot, cfg in team_config.items()}
        team_urls = {buzzer_map[slot]: url for slot, url in team_urls.items()}
        answer_source = TeamAnswerSource(team_urls)
        buzzers = [(num, None) for num in sorted(team_config.keys())]

        game_state.update(
            teams={str(k): v for k, v in team_config.items()},
            scores={str(k): 0 for k in team_config},
            buzzer_map={str(slot): bz for slot, bz in buzzer_map.items()},
        )

        # Ready screen
        leds_idle_rainbow(leds, team_config)
        display.draw_ready(team_config)
        display.wait_for_key()

        # Quiz loop
        scores = {num: 0 for num, _ in buzzers}
        total = len(questions)

        for i, q in enumerate(questions):
            is_last = (i == total - 1)
            deltas = run_question(
                display, q, i + 1, total, ctrl, leds, team_config, snd,
                answer_timeout=args.timeout,
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
                show_scores(display, leds, snd, scores, team_config,
                            game_state=game_state)

        show_scores(display, leds, snd, scores, team_config,
                    final=True, game_state=game_state)

    except KeyboardInterrupt:
        print("\nShutting down.")
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
    main()
