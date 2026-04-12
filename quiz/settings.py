"""Settings screen and team client IP editor.

Both are interactive curses dialogs with their own navigation state.
"""

import curses
import shutil

from quiz.constants import (
    DEFAULT_ANSWER_TIMEOUT,
    DEFAULT_RPI_HOST,
    DEFAULT_RPI_PORT,
    TIMEOUT_OPTIONS,
)
from quiz.drawing import (
    center_text,
    draw_box,
    draw_separator,
    edit_text_field,
)
from quiz.insult_ai import InsultAI, agent_name, list_agents, load_agent
from quiz.insults import insult_pack_name, list_insult_packs, load_insult_pack
from quiz.questions import bundle_name, list_bundles, load_bundle, prepare_questions


def show_settings(win):
    """Settings screen before the game starts. Returns a config dict.

    Rows (index): 0=bundle, 1=timeout, 2=insult, 3=game mode,
    4=rpi host, 5=rpi port, 6=gm port (multi only), 7=start button (multi)
    or 6=start button (single).
    """
    timeout_idx = (
        TIMEOUT_OPTIONS.index(int(DEFAULT_ANSWER_TIMEOUT))
        if int(DEFAULT_ANSWER_TIMEOUT) in TIMEOUT_OPTIONS
        else 4  # default 30s
    )

    rpi_host = DEFAULT_RPI_HOST
    rpi_port = DEFAULT_RPI_PORT

    # Question bundles
    bundles = list_bundles()
    bundle_idx = 0
    bundle_questions = []
    if bundles:
        bundle_questions = load_bundle(bundles[0])

    # Insult options: Off (0) → static packs (1..N) → AI agents (N+1..)
    i_packs = list_insult_packs()
    ai_agents = list_agents() if shutil.which("claude") else []
    n_static = len(i_packs)
    i_max = n_static + len(ai_agents)
    i_pack_idx = 0

    # Multi-client mode
    multi_client = False
    gm_port = "9000"

    selected_row = 0

    def _num_rows():
        return 8 if multi_client else 7

    def _validated_gm_port():
        try:
            port = int(gm_port)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            pass
        return 9000

    def _result():
        questions = prepare_questions(bundle_questions)
        insult_pack = None
        insult_ai_out = None
        if 1 <= i_pack_idx <= n_static:
            insult_pack = load_insult_pack(i_packs[i_pack_idx - 1])
        elif i_pack_idx > n_static:
            agent_def = load_agent(ai_agents[i_pack_idx - n_static - 1])
            insult_ai_out = InsultAI(system_prompt=agent_def["system_prompt"])
        return {
            "answer_timeout": float(TIMEOUT_OPTIONS[timeout_idx]),
            "buzzer_url": f"http://{rpi_host}:{rpi_port}",
            "questions": questions,
            "insult_pack": insult_pack,
            "insult_ai": insult_ai_out,
            "multi_client": multi_client,
            "gm_port": _validated_gm_port(),
        }

    while True:
        win.bkgd(" ", curses.color_pair(0))
        win.clear()
        rows, cols = win.getmaxyx()

        box_h = 24
        box_w = min(58, cols - 4)
        box_top = max(0, rows // 2 - box_h // 2)
        box_left = (cols - box_w) // 2
        draw_box(win, box_top, box_left, box_h, box_w)

        center_text(win, box_top + 1, " SETTINGS ", curses.A_BOLD)
        center_text(win, box_top + 2,
                    "Up/Down, Left/Right, Enter = edit, Esc = start",
                    curses.A_DIM)
        draw_separator(win, box_top + 3)

        # Row 0: Question bundle
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 0 else curses.A_BOLD
        b_name = bundle_name(bundles[bundle_idx]) if bundles else "(none)"
        la = "<" if bundle_idx > 0 else " "
        ra = ">" if bundle_idx < len(bundles) - 1 else " "
        center_text(win, box_top + 5,
                    f"Questions:       {la} {b_name} ({len(bundle_questions)}) {ra}",
                    attr)

        # Row 1: Answer timeout
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 1 else curses.A_BOLD
        tv = TIMEOUT_OPTIONS[timeout_idx]
        la = "<" if timeout_idx > 0 else " "
        ra = ">" if timeout_idx < len(TIMEOUT_OPTIONS) - 1 else " "
        center_text(win, box_top + 7, f"Answer timeout:  {la} {tv}s {ra}", attr)

        # Row 2: Insult mode
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 2 else curses.A_BOLD
        if i_pack_idx == 0:
            i_label = "Off"
        elif i_pack_idx <= n_static:
            i_label = insult_pack_name(i_packs[i_pack_idx - 1])
        else:
            i_label = "AI: " + agent_name(ai_agents[i_pack_idx - n_static - 1])
        la = "<" if i_pack_idx > 0 else " "
        ra = ">" if i_pack_idx < i_max else " "
        center_text(win, box_top + 9,
                    f"Insult players:  {la} {i_label:<20} {ra}",
                    attr)

        # Row 3: Game mode
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 3 else curses.A_BOLD
        mode_label = "Multi-Client (HTTP)" if multi_client else "Single Player (keyboard)"
        center_text(win, box_top + 11, f"Game mode:       < {mode_label} >", attr)

        draw_separator(win, box_top + 13)

        # Row 4: RPi host
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 4 else curses.A_BOLD
        center_text(win, box_top + 15, f"Buzzer RPi host: {rpi_host:<20}", attr)

        # Row 5: RPi port
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 5 else curses.A_BOLD
        center_text(win, box_top + 17, f"Buzzer RPi port: {rpi_port:<10}", attr)

        # Row 6: GM server port (only visible in multi-client)
        if multi_client:
            attr = curses.A_BOLD | curses.A_REVERSE if selected_row == 6 else curses.A_BOLD
            center_text(win, box_top + 19, f"GM server port:  {gm_port:<10}", attr)

        draw_separator(win, box_top + 21)

        # Start button row depends on whether gm_port row is present
        start_row_idx = 7 if multi_client else 6
        attr = curses.A_BOLD | curses.A_REVERSE if selected_row == start_row_idx else curses.A_BOLD
        center_text(win, box_top + 22, "  >>> START GAME <<<  ", attr)

        win.refresh()

        key = win.getch()
        if key == curses.KEY_UP and selected_row > 0:
            selected_row -= 1
        elif key == curses.KEY_DOWN and selected_row < _num_rows() - 1:
            selected_row += 1
        elif selected_row == 0 and key == curses.KEY_LEFT and bundle_idx > 0:
            bundle_idx -= 1
            bundle_questions = load_bundle(bundles[bundle_idx])
        elif selected_row == 0 and key == curses.KEY_RIGHT and bundle_idx < len(bundles) - 1:
            bundle_idx += 1
            bundle_questions = load_bundle(bundles[bundle_idx])
        elif selected_row == 1 and key == curses.KEY_LEFT and timeout_idx > 0:
            timeout_idx -= 1
        elif selected_row == 1 and key == curses.KEY_RIGHT and timeout_idx < len(TIMEOUT_OPTIONS) - 1:
            timeout_idx += 1
        elif selected_row == 2 and key == curses.KEY_LEFT and i_pack_idx > 0:
            i_pack_idx -= 1
        elif selected_row == 2 and key == curses.KEY_RIGHT and i_pack_idx < i_max:
            i_pack_idx += 1
        elif selected_row == 3 and key in (curses.KEY_LEFT, curses.KEY_RIGHT,
                                           curses.KEY_ENTER, 10, 13, 32):
            multi_client = not multi_client
            if selected_row >= _num_rows():
                selected_row = _num_rows() - 1
        elif selected_row == 4 and key in (curses.KEY_ENTER, 10, 13):
            label = "Buzzer RPi host: "
            field_col = (cols - len(label) - 20) // 2 + len(label)
            rpi_host = edit_text_field(win, box_top + 15, field_col, rpi_host, 20,
                                       curses.A_BOLD | curses.A_REVERSE)
        elif selected_row == 5 and key in (curses.KEY_ENTER, 10, 13):
            label = "Buzzer RPi port: "
            field_col = (cols - len(label) - 10) // 2 + len(label)
            rpi_port = edit_text_field(win, box_top + 17, field_col, rpi_port, 10,
                                       curses.A_BOLD | curses.A_REVERSE)
        elif selected_row == 6 and multi_client and key in (curses.KEY_ENTER, 10, 13):
            label = "GM server port:  "
            field_col = (cols - len(label) - 10) // 2 + len(label)
            gm_port = edit_text_field(win, box_top + 19, field_col, gm_port, 10,
                                      curses.A_BOLD | curses.A_REVERSE)
        elif selected_row == start_row_idx and key in (curses.KEY_ENTER, 10, 13):
            return _result()
        elif key == 27:
            return _result()

