#!/usr/bin/env bash
# Set up and test the AI Roast session for the quiz game.
# Run before starting the game to verify Claude CLI works.
#
# This script:
# 1. Checks claude CLI is available and authenticated
# 2. Cleans up old quiz roast sessions
# 3. Creates and primes a test session
# 4. Verifies it can generate insults
#
# Usage: ./setup_insult_ai.sh

set -euo pipefail

echo ">> Checking claude CLI..."
if ! command -v claude &>/dev/null; then
    echo "FAILED — 'claude' not found on PATH."
    echo "Install Claude Code: https://claude.ai/claude-code"
    exit 1
fi
echo "   Found: $(which claude)"

echo ">> Cleaning up old quiz roast sessions..."
# List sessions and remove any with our naming pattern
# (sessions auto-expire, but this keeps things tidy)
claude sessions list 2>/dev/null | grep -i "quiz-roast" | awk '{print $1}' | while read sid; do
    echo "   Removing session $sid"
    claude sessions delete "$sid" 2>/dev/null || true
done
echo "   Done."

SYSTEM_PROMPT="You are the savage, witty roast master of a live quiz buzzer game for software engineers. Generate ONLY a single short insult or backhanded comment. Maximum 80 characters, one sentence. Be creative, funny, cutting, never repeat yourself. Think comedy roast meets disappointed tech lead. Dark humor, cynicism encouraged. Stay PG-13. Output ONLY the insult text — no quotes, no explanation, no preamble."

echo ">> Priming test session..."
SESSION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
PRIME_RESULT=$(claude -p "Prime: say READY" --model haiku --session-id "$SESSION_ID" --system-prompt "$SYSTEM_PROMPT" 2>&1)
if echo "$PRIME_RESULT" | grep -qi "ready"; then
    echo "   Primed successfully."
else
    echo "   FAILED to prime session."
    echo "   Response: $PRIME_RESULT"
    echo ""
    echo "   Make sure you're logged in: claude /login"
    exit 1
fi

echo ">> Testing insult generation..."
INSULT=$(claude -p "Event: wrong
Question: What is 2+2?
Team: Team Potato
Their answer: 5
Correct answer: 4
WRONG answer. Destroy them." --model haiku --resume "$SESSION_ID" 2>&1)
echo "   Generated: \"$INSULT\""

if [ -n "$INSULT" ]; then
    echo ">> AI Roast is ready! Select 'AI Roast' in the game settings."
else
    echo ">> WARNING: Empty response. AI Roast may not work reliably."
fi
