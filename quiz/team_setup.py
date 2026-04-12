"""Team setup screens — color picker, name entry, and the orchestrator."""

import curses
import logging
import time

from quiz.constants import COLOR_PALETTE
from quiz.drawing import (
    center_text,
    draw_box,
    draw_separator,
    edit_text_field,
)

log = logging.getLogger("quiz.team_setup")


def pick_color(win, buzzer_num, used_colors, leds):
    """Let a team pick their color. Returns (hex_color, color_name).

    If every palette entry is taken (13+ teams), falls back to the full
    palette — teams end up sharing a color but the game stays playable.
    """
    available = [(c, n) for c, n in COLOR_PALETTE if c not in used_colors]
    if not available:
        available = list(COLOR_PALETTE)
    selected = 0
    last_selected = -1

    while True:
        win.bkgd(" ", curses.color_pair(0))
        win.clear()
        rows, cols = win.getmaxyx()

        box_h = len(available) + 6
        box_w = min(40, cols - 4)
        box_top = rows // 2 - box_h // 2
        box_left = (cols - box_w) // 2
        draw_box(win, box_top, box_left, box_h, box_w)

        center_text(win, box_top + 1, f" Team {buzzer_num}: pick your color ", curses.A_BOLD)
        center_text(win, box_top + 2, "Up/Down + Enter", curses.A_DIM)

        for i, (_, name) in enumerate(available):
            if i == selected:
                attr = curses.A_BOLD | curses.A_REVERSE
                marker = f"  {name}  "
            else:
                attr = 0
                marker = f"  {name}"
            center_text(win, box_top + 4 + i, marker, attr)

        win.refresh()

        if selected != last_selected:
            leds.breathe(available[selected][0], period=2.0)
            last_selected = selected

        key = win.getch()
        if key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(available) - 1:
            selected += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            leds.stop()
            return available[selected]


def pick_team_name(win, buzzer_num, default_name, leds, color_hex):
    """Let a team type their name. Returns the chosen name (or default if empty)."""
    win.bkgd(" ", curses.color_pair(0))
    win.clear()
    rows, cols = win.getmaxyx()

    box_h = 8
    box_w = min(45, cols - 4)
    box_top = rows // 2 - box_h // 2
    box_left = (cols - box_w) // 2
    draw_box(win, box_top, box_left, box_h, box_w)

    center_text(win, box_top + 1, f" Buzzer {buzzer_num}: enter team name ", curses.A_BOLD)
    center_text(win, box_top + 2, "Type name + Enter (or Enter for default)", curses.A_DIM)
    draw_separator(win, box_top + 4)

    leds.breathe(color_hex, period=2.0)
    win.refresh()

    label = "Name: "
    field_row = box_top + 3
    field_col = (cols - len(label) - 15) // 2 + len(label)
    center_text(win, field_row, f"{label}{' ' * 15}", curses.A_BOLD)
    win.refresh()

    name = edit_text_field(win, field_row, field_col, default_name, 15, curses.A_BOLD)
    leds.stop()
    return name.strip() or default_name


def setup_teams(win, buzzers, leds):
    """Run color picker + name entry for each team. Returns team_config dict."""
    team_config = {}
    used_colors = set()

    for num, _ in buzzers:
        color_hex, color_name = pick_color(win, num, used_colors, leds)
        used_colors.add(color_hex)
        team_name = pick_team_name(win, num, f"Team {num}", leds, color_hex)
        team_config[num] = {
            "name": team_name,
            "color": color_hex,
            "color_name": color_name,
        }
        leds.set_color(color_hex)
        time.sleep(0.8)
        leds.off()
        time.sleep(0.3)

    return team_config


def wait_for_registrations(display, num_teams, game_state, leds):
    """Block until num_teams clients have registered via POST /register.

    Shows a progress screen. Returns dict {team_num: callback_url}.
    """
    while True:
        display.get_command()  # drain input (escape not supported here)

        state = game_state.snapshot()
        registered = state.get("registered_clients", {})
        n_done = len(registered)

        items = []
        for i in range(1, num_teams + 1):
            if i in registered:
                items.append((f"  \u2713 Team {i}: {registered[i]}  ", True))
            else:
                items.append((f"  Team {i}: waiting...  ", False))

        if n_done >= num_teams:
            status = "All clients connected! Press any key."
        else:
            status = f"{n_done}/{num_teams} connected..."

        display.draw_waiting("WAITING FOR CLIENTS",
                             "Start clients with --game-master <this IP>:<port>",
                             items, status)

        if n_done >= num_teams:
            leds.rainbow(["#0066ff", "#ffcc00"], period=3.0)
            display.wait_for_key()
            leds.stop()
            return registered

        time.sleep(0.2)


def wait_for_team_configs(display, num_teams, game_state, leds):
    """Block until all registered teams have submitted name+color config.

    Returns team_config dict: {team_num: {name, color, color_name}}.
    Escape falls back to defaults for unconfigured teams.
    """
    while True:
        cmd = display.get_command()
        if cmd == "escape":
            state = game_state.snapshot()
            configs = state.get("team_configs", {})
            for i in range(1, num_teams + 1):
                if i not in configs:
                    c_hex, c_name = COLOR_PALETTE[(i - 1) % len(COLOR_PALETTE)]
                    configs[i] = {
                        "name": f"Team {i}",
                        "color": c_hex,
                        "color_name": c_name,
                    }
                    log.info("Team %d defaulted (escape pressed)", i)
            leds.stop()
            return configs

        state = game_state.snapshot()
        configs = state.get("team_configs", {})
        n_done = len(configs)

        items = []
        for i in range(1, num_teams + 1):
            if i in configs:
                tc = configs[i]
                items.append((f"  Team {i}: {tc['name']} ({tc.get('color_name', '')})  ", True))
            else:
                items.append((f"  Team {i}: picking...  ", False))

        if n_done >= num_teams:
            status = "All teams ready! Press any key to continue."
        else:
            status = f"{n_done}/{num_teams} configured..."

        display.draw_waiting("WAITING FOR TEAMS",
                             "Teams pick name & color on their devices  (Esc = defaults)",
                             items, status)

        if n_done >= num_teams:
            colors = [tc["color"] for tc in configs.values()]
            if len(colors) >= 2:
                leds.rainbow(colors, period=3.0)
            elif colors:
                leds.breathe(colors[0])
            display.wait_for_key()
            leds.stop()
            return configs

        time.sleep(0.05)


def _broadcast_assign_state(game_state, slot_num, name, assigned, team_config):
    """Push buzzer_assign phase to clients with full progress info."""
    if game_state is None:
        return
    # Build progress: {slot: {name, color, buzzer_num}} for assigned teams
    done = {}
    for s, bz in assigned.items():
        done[str(s)] = {
            "name": team_config[s]["name"],
            "color": team_config[s]["color"],
            "buzzer_num": bz,
        }
    game_state.update(
        phase="buzzer_assign",
        assign_team=slot_num,
        assign_team_name=name,
        assigned_teams=done,
    )


def assign_buzzers(display, team_config, ctrl, leds, game_state):
    """Ask each team to press their buzzer. Returns {slot_num: actual_buzzer_num}.

    For each team in order:
    1. Broadcast state with phase="buzzer_assign", assign_team=slot_num, assign_team_name=name
    2. Reset buzzers on RPi
    3. Poll get_ranking() until an unclaimed buzzer appears
    4. Record mapping, flash team color on LEDs

    Args:
        display: Display protocol instance
        team_config: {slot_num: {name, color, color_name}} from wait_for_team_configs
        ctrl: RemoteBuzzerController instance
        leds: LED controller
        game_state: GameState instance (for broadcasting to clients), can be None

    Returns:
        dict mapping slot_num -> actual physical buzzer_num
    """
    assigned = {}  # slot_num -> actual_buzzer_num
    assigned_buzzers = set()  # set of actual buzzer nums already claimed
    slots = sorted(team_config.keys())

    # Build the {slot: {name, color, buzzer_num}} dict for display
    def _assigned_info():
        return {s: {"name": team_config[s]["name"],
                     "color": team_config[s]["color"],
                     "buzzer_num": assigned[s]}
                for s in assigned}

    for slot_num in slots:
        name = team_config[slot_num]["name"]
        color = team_config[slot_num]["color"]

        _broadcast_assign_state(game_state, slot_num, name, assigned, team_config)

        ctrl.reset()

        aborted = False
        while True:
            cmd = display.get_command()
            if cmd == "escape":
                log.info("assign_buzzers: aborted by Escape key")
                aborted = True
                break

            display.draw_buzzer_assign(name, color, _assigned_info(), team_config)

            # Check all ranking entries — not just [0] — so a stale
            # buzzer that re-registers after reset doesn't block us.
            ranking = ctrl.get_ranking()
            matched = None
            for candidate in ranking:
                if candidate not in assigned_buzzers:
                    matched = candidate
                    break

            if matched is not None:
                assigned[slot_num] = matched
                assigned_buzzers.add(matched)
                log.info("assign_buzzers: slot %d -> buzzer %d (%s)",
                         slot_num, matched, name)
                _broadcast_assign_state(
                    game_state, slot_num, name, assigned, team_config)
                leds.set_color(color)
                time.sleep(0.5)
                leds.off()
                time.sleep(0.2)
                break

            time.sleep(0.1)

        if aborted:
            break

    # Fill in any unassigned slots — avoid collisions with already-claimed buzzers
    for slot_num in slots:
        if slot_num not in assigned:
            fallback = slot_num
            if fallback in assigned_buzzers:
                fallback = max(assigned_buzzers) + 1
            assigned[slot_num] = fallback
            assigned_buzzers.add(fallback)
            log.info("assign_buzzers: slot %d -> %d (fallback)", slot_num, fallback)

    if game_state is not None:
        game_state.update(phase="idle", assign_team=None,
                          assign_team_name=None, assigned_teams=None)

    return assigned


