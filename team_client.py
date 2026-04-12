#!/usr/bin/env python3
"""Team client for multi-client quiz mode.

Run on each team's device (phone, laptop, etc.):
    python3 team_client.py --game-master 10.0.0.2:9000 --port 7777

Then open http://localhost:7777 in a browser.
The client registers with the game master automatically and gets a team number.
The page shows a color/name picker first, then the quiz UI once the game starts.

If a KlopfKlopf USB LED strip is attached, pass --leds to enable LED effects.
"""

import argparse
import json
import logging
import re
import socket
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

log = logging.getLogger("team_client")

# ── Color palette (must match quiz/constants.py) ──

COLOR_PALETTE = [
    ("#0066ff", "Blue"),
    ("#ffcc00", "Yellow"),
    ("#ff6600", "Orange"),
    ("#cc00ff", "Purple"),
    ("#00cccc", "Cyan"),
    ("#ff0099", "Pink"),
    ("#ffffff", "White"),
    ("#ff4444", "Coral"),
    ("#44ddaa", "Mint"),
    ("#ffaa00", "Amber"),
    ("#8844ff", "Violet"),
    ("#00aaff", "Sky Blue"),
]


def _detect_lan_ip():
    """Return the IP of the interface the OS would use to reach the outside."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# ── Shared state ──

_answer_lock = threading.Lock()
_current_answer = None

_team_config_lock = threading.Lock()
_team_config = None  # {name, color, color_name} or None

_preview_lock = threading.Lock()
_preview_color = None  # hex color string during setup color selection

_game_master_url = ""
_team_num = None  # set via --team


# ── HTML pages ──

# Build palette JSON for embedding in HTML
_PALETTE_JSON = json.dumps(COLOR_PALETTE)

HTML_PAGE = (
    """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>Quiz Buzzer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #fff;
         height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

  /* Setup phase */
  #setup { display: flex; flex-direction: column; align-items: center;
           justify-content: flex-start; padding: 20px; height: 100vh; overflow-y: auto; }
  #setup h1 { margin-bottom: 10px; font-size: 1.5em; }
  #setup .subtitle { color: #888; margin-bottom: 20px; }
  #color-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
                width: 100%; max-width: 360px; margin-bottom: 20px; }
  .color-btn { height: 60px; border: 3px solid transparent; border-radius: 12px;
               cursor: pointer; font-weight: bold; font-size: 0.9em;
               transition: all 0.15s; color: #000; }
  .color-btn.selected { border-color: #fff; transform: scale(1.08);
                        box-shadow: 0 0 20px rgba(255,255,255,0.4); }
  #name-input { font-size: 1.2em; padding: 12px; border-radius: 10px; border: 2px solid #333;
                background: #16213e; color: #fff; width: 100%; max-width: 360px;
                text-align: center; margin-bottom: 20px; }
  #submit-btn { font-size: 1.3em; padding: 15px 40px; border-radius: 14px; border: none;
                background: #2ecc71; color: #fff; font-weight: bold; cursor: pointer;
                opacity: 0.4; transition: all 0.2s; }
  #submit-btn.ready { opacity: 1; }
  #submit-btn.ready:active { transform: scale(0.95); }
  #waiting-msg { margin-top: 30px; font-size: 1.2em; color: #888; display: none; }

  /* Game phase */
  #game { display: none; flex-direction: column; height: 100vh; }
  #status { text-align: center; padding: 15px; font-size: 1.2em; background: #16213e; }
  #question { text-align: center; padding: 20px; font-size: 1.3em; font-weight: bold;
              min-height: 80px; display: flex; align-items: center; justify-content: center; }
  #buttons { flex: 1; display: flex; flex-direction: column; gap: 10px; padding: 10px; }
  .btn { flex: 1; border: none; border-radius: 16px; font-size: 1.8em; font-weight: bold;
         cursor: pointer; color: #fff; opacity: 0.3; transition: all 0.2s; }
  .btn.active { opacity: 1; transform: scale(1); }
  .btn.active:active { transform: scale(0.95); }
  .btn.selected { opacity: 1; border: 4px solid #fff; }
  #btn-a { background: #e74c3c; }
  #btn-b { background: #3498db; }
  #btn-c { background: #2ecc71; }
  #timer { text-align: center; padding: 10px; font-size: 1.5em; }
  #scores { text-align: center; padding: 10px; font-size: 0.9em; color: #888; }
</style>
</head>
<body>

<!-- Setup phase -->
<div id="setup">
  <h1>Team <span id="team-num">?</span></h1>
  <div class="subtitle">Pick your color &amp; name</div>
  <div id="color-grid"></div>
  <input id="name-input" type="text" placeholder="Team name" maxlength="15">
  <button id="submit-btn" onclick="submitConfig()">READY</button>
  <div id="waiting-msg">Waiting for game to start...</div>
</div>

<!-- Game phase -->
<div id="game">
  <div id="status">Connecting...</div>
  <div id="question"></div>
  <div id="timer"></div>
  <div id="buttons">
    <button class="btn" id="btn-a" onclick="answer('a')">A</button>
    <button class="btn" id="btn-b" onclick="answer('b')">B</button>
    <button class="btn" id="btn-c" onclick="answer('c')">C</button>
  </div>
  <div id="scores"></div>
</div>

<script>
const PALETTE = """
    + _PALETTE_JSON
    + """;
let selectedColor = null;
let selectedColorName = null;
let configSubmitted = false;
let myAnswer = null;
let isMyTurn = false;
let gameStarted = false;

// ── Setup phase ──

function initSetup() {
  // Fetch client info (team number)
  fetch('/client_info').then(r => r.json()).then(info => {
    document.getElementById('team-num').textContent = info.team_num || '?';
    document.getElementById('name-input').value = info.default_name || '';
    // Check if already configured
    if (info.config) {
      configSubmitted = true;
      showWaiting();
    }
  });

  const grid = document.getElementById('color-grid');
  PALETTE.forEach(([hex, name]) => {
    const btn = document.createElement('div');
    btn.className = 'color-btn';
    btn.style.background = hex;
    btn.textContent = name;
    btn.dataset.hex = hex;
    // Ensure readability on light colors
    const r = parseInt(hex.slice(1,3), 16), g = parseInt(hex.slice(3,5), 16),
          b = parseInt(hex.slice(5,7), 16);
    if (r + g + b > 500) btn.style.color = '#333';
    btn.onclick = () => {
      if (btn.classList.contains('disabled')) return;
      document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedColor = hex;
      selectedColorName = name;
      updateSubmitBtn();
      fetch('/preview_led', {method:'POST', headers:{'Content-Type':'application/json'},
                              body: JSON.stringify({color: hex})}).catch(() => {});
    };
    grid.appendChild(btn);
  });

  // Poll for claimed colors during setup
  setInterval(async () => {
    if (configSubmitted) return;
    try {
      const r = await fetch('/proxy/state');
      if (!r.ok) return;
      const state = await r.json();
      const claimed = state.claimed_colors || [];
      document.querySelectorAll('.color-btn').forEach(btn => {
        const hex = btn.dataset.hex;
        const isClaimed = claimed.includes(hex);
        const isMySelection = (hex === selectedColor);
        if (isClaimed && !isMySelection) {
          btn.style.opacity = '0.2';
          btn.style.pointerEvents = 'none';
          btn.classList.add('disabled');
        } else if (!btn.classList.contains('selected')) {
          btn.style.opacity = '1';
          btn.style.pointerEvents = 'auto';
          btn.classList.remove('disabled');
        }
      });
    } catch(e) {}
  }, 1000);
}

function updateSubmitBtn() {
  const btn = document.getElementById('submit-btn');
  const name = document.getElementById('name-input').value.trim();
  if (selectedColor && name) {
    btn.classList.add('ready');
  } else {
    btn.classList.remove('ready');
  }
}

document.getElementById('name-input').addEventListener('input', updateSubmitBtn);

function submitConfig() {
  const name = document.getElementById('name-input').value.trim();
  if (!selectedColor || !name) return;
  fetch('/team_config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: name, color: selectedColor, color_name: selectedColorName})
  }).then(r => {
    if (r.status === 409) {
      // Color was just taken by another team
      selectedColor = null;
      selectedColorName = null;
      document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
      updateSubmitBtn();
      alert('That color was just taken! Pick another.');
      return;
    }
    if (!r.ok) throw new Error('submit failed');
    configSubmitted = true;
    showWaiting();
  }).catch(() => {
    alert('Failed to submit — try again');
  });
}

function showWaiting() {
  document.getElementById('submit-btn').style.display = 'none';
  document.getElementById('color-grid').style.display = 'none';
  document.getElementById('name-input').style.display = 'none';
  document.querySelector('.subtitle').textContent = '';
  document.getElementById('waiting-msg').style.display = 'block';
}

function resetToSetup() {
  fetch('/new_game', {method:'POST'}).then(() => { location.reload(); });
}

// ── Game phase ──

function answer(ch) {
  if (!isMyTurn || myAnswer) return;
  myAnswer = ch;
  fetch('/submit', {method:'POST', headers:{'Content-Type':'application/json'},
                     body: JSON.stringify({answer: ch})});
  document.querySelectorAll('.btn').forEach(b => b.classList.remove('selected'));
  document.getElementById('btn-' + ch).classList.add('selected');
}

function switchToGame() {
  if (gameStarted) return;
  gameStarted = true;
  document.getElementById('setup').style.display = 'none';
  document.getElementById('game').style.display = 'flex';
}

function updateUI(state) {
  const status = document.getElementById('status');
  const question = document.getElementById('question');
  const timer = document.getElementById('timer');
  const scores = document.getElementById('scores');
  const buttons = document.querySelectorAll('.btn');

  // Fetch our team num from the server-provided info
  const teamNum = document.getElementById('team-num').textContent;

  // If the game has moved past idle/setup, switch to game view
  if (state.phase && state.phase !== 'idle') {
    switchToGame();
  }

  const myTurn = state.active_team && String(state.active_team) === teamNum;

  if (state.phase === 'answering' && myTurn) {
    isMyTurn = true;
    status.textContent = 'YOUR TURN! Pick an answer!';
    status.style.background = '#e74c3c';
    question.textContent = state.question_text || '';
    buttons.forEach(b => b.classList.add('active'));
    if (state.choices) {
      document.getElementById('btn-a').textContent = 'A) ' + (state.choices.a || '');
      document.getElementById('btn-b').textContent = 'B) ' + (state.choices.b || '');
      document.getElementById('btn-c').textContent = 'C) ' + (state.choices.c || '');
    }
    if (state.time_remaining != null) {
      timer.textContent = Math.ceil(state.time_remaining) + 's';
    }
  } else {
    isMyTurn = false;
    buttons.forEach(b => { b.classList.remove('active'); b.classList.remove('selected'); });
    document.getElementById('btn-a').textContent = 'A';
    document.getElementById('btn-b').textContent = 'B';
    document.getElementById('btn-c').textContent = 'C';
    myAnswer = null;
    if (state.phase === 'buzzing') {
      status.textContent = 'BUZZ IN!';
      status.style.background = '#f39c12';
      question.textContent = state.question_text || '';
    } else if (state.phase === 'answering') {
      status.textContent = 'Team ' + state.active_team + ' is answering...';
      status.style.background = '#16213e';
      question.textContent = state.question_text || '';
    } else if (state.phase === 'buzzer_assign') {
        const isMe = state.assign_team && String(state.assign_team) === teamNum;
        // Check if we've already been assigned
        const done = state.assigned_teams || {};
        const amDone = done[teamNum];
        if (amDone) {
            status.textContent = '\u2713 Buzzer assigned!';
            status.style.background = '#2ecc71';
        } else if (isMe) {
            status.textContent = '>>> PRESS YOUR BUZZER NOW! <<<';
            status.style.background = '#e74c3c';
        } else {
            const who = state.assign_team_name || ('Team ' + state.assign_team);
            status.textContent = 'Wait \u2014 ' + who + ' is picking...';
            status.style.background = '#16213e';
        }
        // Show assignment progress
        const parts = [];
        for (const [s, info] of Object.entries(done)) {
            parts.push('\u2713 ' + info.name);
        }
        question.textContent = parts.length ? parts.join('  ') : '';
    } else if (state.phase === 'feedback') {
      status.textContent = state.feedback || 'Feedback';
      status.style.background = '#16213e';
      question.textContent = '';
    } else if (state.phase === 'scores' || state.phase === 'final_scores') {
      status.textContent = state.phase === 'final_scores' ? 'FINAL SCORES' : 'Scoreboard';
      status.style.background = '#16213e';
      question.textContent = '';
    } else {
      status.textContent = 'Waiting for game...';
      status.style.background = '#16213e';
      question.textContent = '';
    }
    timer.textContent = '';
  }

  if (state.scores && state.teams) {
    const parts = [];
    for (const [num, sc] of Object.entries(state.scores)) {
      const t = state.teams[num];
      parts.push((t ? t.name : 'Team '+num) + ': ' + sc);
    }
    scores.textContent = parts.join('  |  ');
  }
}

// Poll game state + detect game over
let gmFailCount = 0;
let gameOverShown = false;
setInterval(async () => {
  try {
    const r = await fetch('/proxy/state');
    if (r.ok) {
      gmFailCount = 0;
      const state = await r.json();
      updateUI(state);
      // Show new-game button after final scores
      if (state.phase === 'final_scores' && !gameOverShown) {
        gameOverShown = true;
        setTimeout(showNewGameBtn, 3000);
      }
    } else {
      gmFailCount++;
    }
  } catch(e) { gmFailCount++; }
  // Game master gone (server shut down) — offer reset
  if (gmFailCount > 6 && gameStarted && !gameOverShown) {
    gameOverShown = true;
    showNewGameBtn();
  }
}, 500);

function showNewGameBtn() {
  const btn = document.createElement('button');
  btn.textContent = 'NEW GAME';
  btn.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
    'font-size:1.3em;padding:15px 40px;border-radius:14px;border:none;' +
    'background:#f39c12;color:#fff;font-weight:bold;cursor:pointer;z-index:999;';
  btn.onclick = resetToSetup;
  document.body.appendChild(btn);
}

initSetup();
</script>
</body>
</html>"""
)


class TeamClientHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(200, HTML_PAGE, "text/html")
        elif self.path == "/answer":
            with _answer_lock:
                body = json.dumps({"answer": _current_answer})
            self._send(200, body, "application/json")
        elif self.path == "/client_info":
            with _team_config_lock:
                cfg = _team_config
            body = json.dumps({
                "team_num": _team_num,
                "default_name": f"Team {_team_num}" if _team_num else "",
                "config": cfg,
            })
            self._send(200, body, "application/json")
        elif self.path == "/team_config":
            with _team_config_lock:
                body = json.dumps({"config": _team_config})
            self._send(200, body, "application/json")
        elif self.path == "/proxy/state":
            self._proxy_game_state()
        else:
            self._send(404, '{"error":"not found"}', "application/json")

    def do_POST(self):
        global _current_answer, _team_config, _preview_color
        try:
            length = min(int(self.headers.get("Content-Length", 0) or 0), 4096)
        except (ValueError, TypeError):
            length = 0
        body = self.rfile.read(length) if length > 0 else b"{}"

        if self.path == "/reset":
            with _answer_lock:
                _current_answer = None
            self._send(200, '{"ok":true}', "application/json")
        elif self.path == "/new_game":
            with _team_config_lock:
                _team_config = None
            with _answer_lock:
                _current_answer = None
            with _preview_lock:
                _preview_color = None
            log.info("New game — client state reset")
            self._send(200, '{"ok":true}', "application/json")
        elif self.path == "/submit":
            try:
                data = json.loads(body)
                ans = data.get("answer", "")
                if ans in ("a", "b", "c"):
                    with _answer_lock:
                        _current_answer = ans
                    self._send(200, '{"ok":true}', "application/json")
                else:
                    self._send(400, '{"error":"invalid answer"}', "application/json")
            except json.JSONDecodeError:
                self._send(400, '{"error":"invalid json"}', "application/json")
        elif self.path == "/preview_led":
            try:
                data = json.loads(body)
                color = str(data.get("color", "")).strip()
                if _HEX_COLOR_RE.match(color):
                    with _preview_lock:
                        _preview_color = color
            except json.JSONDecodeError:
                pass
            self._send(200, '{"ok":true}', "application/json")
        elif self.path == "/team_config":
            try:
                data = json.loads(body)
                name = str(data.get("name", "")).strip()[:15]
                color = str(data.get("color", "")).strip()
                color_name = str(data.get("color_name", "")).strip()[:20]
                if not name or not _HEX_COLOR_RE.match(color):
                    self._send(400, '{"error":"invalid name or color"}', "application/json")
                    return
                # Forward to game master for validation + storage
                if _game_master_url:
                    payload = json.dumps({
                        "team_num": _team_num,
                        "name": name,
                        "color": color,
                        "color_name": color_name,
                    }).encode()
                    req = urllib.request.Request(
                        f"{_game_master_url}/team_config",
                        method="POST", data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=3):
                            pass
                    except urllib.error.HTTPError as e:
                        # Pass through master's error (e.g. 409 color taken)
                        err_body = e.read()
                        self._send(e.code, err_body, "application/json")
                        return
                    except (urllib.error.URLError, OSError):
                        self._send(503, '{"error":"game master unreachable"}',
                                   "application/json")
                        return
                # Store locally for LED driver + client_info
                with _team_config_lock:
                    _team_config = {
                        "name": name,
                        "color": color,
                        "color_name": color_name,
                    }
                with _preview_lock:
                    _preview_color = None
                log.info("Team config set: %s (%s)", name, color_name)
                self._send(200, '{"ok":true}', "application/json")
            except json.JSONDecodeError:
                self._send(400, '{"error":"invalid json"}', "application/json")
        else:
            self._send(404, '{"error":"not found"}', "application/json")

    def _proxy_game_state(self):
        if not _game_master_url:
            self._send(503, '{"error":"no game master"}', "application/json")
            return
        try:
            with urllib.request.urlopen(f"{_game_master_url}/state", timeout=1) as resp:
                data = resp.read()
            self._send_bytes(200, data, "application/json")
        except (urllib.error.URLError, OSError):
            self._send(503, '{"error":"game master unreachable"}', "application/json")

    def _send(self, status, body, content_type):
        raw = body.encode() if isinstance(body, str) else body
        self._send_bytes(status, raw, content_type)

    def _send_bytes(self, status, raw, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


# ── Client LED driver ──

class ClientLEDRunner(threading.Thread):
    """Background thread that polls game state and drives a local LED strip.

    Maps game phases to LED effects in the team's color. Works identically
    with a real LEDController or a NoOpLEDController.
    """

    POLL_INTERVAL = 0.25  # seconds between game state polls

    def __init__(self, leds, game_master_url, team_num):
        super().__init__(daemon=True)
        self._leds = leds
        self._gm_url = game_master_url.rstrip("/") if game_master_url else ""
        self._team_num = team_num
        self._stop_event = threading.Event()
        self._current_led_state = None  # (effect_name, color, ...) to avoid flicker
        self._phase_entered_at = 0.0
        self._last_phase = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("LED driver tick failed")
            self._stop_event.wait(self.POLL_INTERVAL)

    def _tick(self):
        # Before game starts, show team color if configured
        state = self._fetch_state()

        if state is None:
            # No game master connection — preview color or show team color
            with _preview_lock:
                preview = _preview_color
            with _team_config_lock:
                cfg = _team_config
            if preview and not cfg:
                self._set_led("breathe", preview, 2.0)
            elif cfg:
                self._set_led("breathe", cfg["color"], 4.0)
            else:
                self._set_led("off")
            return

        phase = state.get("phase", "idle")
        team_key = str(self._team_num)

        # Track phase transitions
        if phase != self._last_phase:
            self._last_phase = phase
            self._phase_entered_at = time.monotonic()

        # Get my team color from broadcast state, fall back to local config
        my_color = None
        teams = state.get("teams", {})
        if team_key in teams:
            my_color = teams[team_key].get("color")
        if not my_color:
            with _team_config_lock:
                cfg = _team_config
            if cfg:
                my_color = cfg["color"]

        if not my_color:
            self._set_led("off")
            return

        active_team = state.get("active_team")
        is_my_turn = active_team is not None and str(active_team) == team_key

        if phase == "buzzing":
            # Rainbow through all team colors
            all_colors = [t.get("color", "#ffffff") for t in teams.values()]
            if len(all_colors) >= 2:
                self._set_led("rainbow", tuple(all_colors), 3.0)
            else:
                self._set_led("breathe", my_color, 2.0)

        elif phase == "buzzer_assign":
            assign_team = state.get("assign_team")
            is_my_assign = assign_team is not None and str(assign_team) == team_key
            if is_my_assign and my_color:
                self._set_led("pulse", my_color, 1.0)
            else:
                self._set_led("off")

        elif phase == "answering" and is_my_turn:
            # Escalating urgency based on time remaining
            remaining = state.get("time_remaining")
            timeout = state.get("answer_timeout", 30)
            if remaining is not None:
                led_phase = _get_client_led_phase(remaining, timeout)
                if led_phase == "breathe":
                    self._set_led("breathe", my_color, 3.0)
                elif led_phase == "pulse":
                    self._set_led("pulse", my_color, 1.0)
                else:
                    self._set_led("strobe", my_color, 6.0)
            else:
                self._set_led("breathe", my_color, 3.0)

        elif phase == "answering":
            # Another team is answering — dim breathe
            self._set_led("breathe", my_color, 4.0)

        elif phase == "feedback":
            feedback_team_num = state.get("feedback_team_num")
            is_about_me = feedback_team_num is not None and str(feedback_team_num) == team_key
            elapsed = time.monotonic() - self._phase_entered_at

            if is_about_me:
                feedback_correct = state.get("feedback_correct", False)
                if feedback_correct:
                    if elapsed < 1.0:
                        self._set_led("strobe", my_color, 8.0)
                    else:
                        self._set_led("set_color", "#00ff00")
                else:
                    if elapsed < 0.5:
                        self._set_led("strobe", "#ff0000", 4.0)
                    else:
                        self._set_led("candle", "#ff2200", 0.6)
            else:
                self._set_led("off")

        elif phase in ("scores", "final_scores"):
            self._set_led("breathe", my_color, 3.0)

        else:
            # idle or unknown — preview color during setup, or show team color
            with _preview_lock:
                preview = _preview_color
            with _team_config_lock:
                cfg = _team_config
            if preview and not cfg:
                self._set_led("breathe", preview, 2.0)
            elif my_color:
                self._set_led("breathe", my_color, 4.0)
            else:
                self._set_led("off")

    def _set_led(self, effect, *args):
        """Only call the LED API when the effect actually changes."""
        key = (effect, *args)
        if key == self._current_led_state:
            return
        self._current_led_state = key

        if effect == "off":
            self._leds.off()
        elif effect == "breathe":
            self._leds.breathe(args[0], period=args[1])
        elif effect == "pulse":
            self._leds.pulse([args[0]], period=args[1])
        elif effect == "strobe":
            self._leds.strobe(args[0], hz=args[1])
        elif effect == "rainbow":
            self._leds.rainbow(list(args[0]), period=args[1])
        elif effect == "set_color":
            self._leds.set_color(args[0])
        elif effect == "candle":
            self._leds.candle(args[0], intensity=args[1])

    def _fetch_state(self):
        """Fetch game state from game master. Returns dict or None."""
        if not self._gm_url:
            return None
        try:
            with urllib.request.urlopen(f"{self._gm_url}/state", timeout=1) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None


def _get_client_led_phase(remaining, timeout):
    """Determine LED phase from answer timer — mirrors quiz/led_show.py logic."""
    if timeout <= 10:
        return "pulse" if remaining > 5 else "strobe"
    if remaining > timeout * 0.5:
        return "breathe"
    if remaining > 5:
        return "pulse"
    return "strobe"


# ── Registration ──

def _register_with_master(game_master_url, local_ip, local_port):
    """POST /register to master. Retries until success, sets global _team_num."""
    global _team_num
    callback_url = f"http://{local_ip}:{local_port}"
    payload = json.dumps({"callback_url": callback_url}).encode()

    while True:
        try:
            req = urllib.request.Request(
                f"{game_master_url}/register",
                method="POST", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                _team_num = data["team_num"]
                log.info("Registered as team %d", _team_num)
                return
        except urllib.error.HTTPError as e:
            if e.code == 409:
                print("ERROR: All team slots are full.")
                sys.exit(1)
            log.warning("Registration failed (HTTP %d), retrying...", e.code)
        except (urllib.error.URLError, OSError) as e:
            log.warning("Registration failed (%s), retrying in 2s...", e)
        time.sleep(2)


# ── Main ──

def main():
    global _game_master_url, _team_num

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Quiz team client")
    parser.add_argument("--port", type=int, default=7777,
                        help="Port to listen on (default: 7777)")
    parser.add_argument("--game-master", required=True,
                        help="Game master address (host:port)")
    parser.add_argument("--leds", action="store_true",
                        help="Enable KlopfKlopf USB LED strip")
    args = parser.parse_args()

    gm = args.game_master
    if not gm.startswith("http"):
        gm = f"http://{gm}"
    _game_master_url = gm

    # LED setup — optional hardware
    leds = None
    if args.leds:
        try:
            from leds.klopfklopf import LEDController
            leds = LEDController()
            leds.open()
            log.info("LED strip connected")
        except (ImportError, RuntimeError) as e:
            log.warning("LED strip not available: %s", e)
            leds = None

    if leds is None:
        from leds.stub import NoOpLEDController
        leds = NoOpLEDController()

    # Start HTTP server immediately so the page loads while waiting for master
    server = ReusableThreadingHTTPServer(("0.0.0.0", args.port), TeamClientHandler)
    local_ip = _detect_lan_ip()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Team client running on http://{local_ip}:{args.port}")
    print(f"Game master: {_game_master_url}")

    # Register with game master to get team number (retries until master is up)
    print("Registering with game master...")
    _register_with_master(_game_master_url, local_ip, args.port)
    print(f"Registered as Team {_team_num}")

    # Start LED driver thread (team_num now known)
    led_runner = ClientLEDRunner(leds, _game_master_url, _team_num)
    led_runner.start()

    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        if led_runner:
            led_runner.stop()
            led_runner.join(timeout=2)
        try:
            leds.stop()
            leds.off()
            leds.close()
        except Exception:
            pass
        server.server_close()


if __name__ == "__main__":
    main()
