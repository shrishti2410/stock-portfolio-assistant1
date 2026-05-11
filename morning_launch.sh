#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# morning_launch.sh — Login-time launcher with confirmation dialog
#
# Invoked by ~/Library/LaunchAgents/com.user.stock-portfolio.plist
# on user login. Shows an AppleScript dialog asking:
#   "Start Stock Portfolio Assistant?"
# If user clicks "Yes" → runs start.sh in background and opens browser.
# If user clicks "No"  → exits silently.
#
# Manual test: bash morning_launch.sh
# ──────────────────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
START_SCRIPT="$DIR/start.sh"
LOG_FILE="$HOME/Library/Logs/stock-portfolio-assistant.log"

mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date)] Morning launcher invoked" >> "$LOG_FILE"

# Wait for desktop / dock to be ready (avoid dialog appearing before login finishes)
sleep 5

# ── Show confirmation dialog ──────────────────────────────────────────
# Returns "OK" if Yes clicked, exits non-zero if No / Cancel.
RESPONSE=$(osascript <<EOF 2>>"$LOG_FILE"
tell application "System Events"
    activate
    set userResponse to display dialog ¬
        "📈 Stock Portfolio Assistant" & return & return & ¬
        "Good morning! Do you want to start the trading dashboard?" & return & return & ¬
        "This will launch:" & return & ¬
        "  • Backend API on port 8000" & return & ¬
        "  • Frontend UI on port 5173" & return & ¬
        "  • Open browser to http://localhost:5173" ¬
        buttons {"Not now", "Yes, start it"} ¬
        default button "Yes, start it" ¬
        cancel button "Not now" ¬
        with title "Stock Portfolio Assistant" ¬
        with icon note ¬
        giving up after 30
    set buttonClicked to button returned of userResponse
    if buttonClicked is "Yes, start it" then
        return "YES"
    else
        return "NO"
    end if
end tell
EOF
)

if [ "$RESPONSE" != "YES" ]; then
    echo "[$(date)] User declined or dialog timed out. Exiting." >> "$LOG_FILE"
    exit 0
fi

# ── Launch the app ────────────────────────────────────────────────────
echo "[$(date)] User confirmed. Starting app..." >> "$LOG_FILE"

if [ ! -x "$START_SCRIPT" ]; then
    osascript -e "display notification \"start.sh not found at $START_SCRIPT\" with title \"Stock Portfolio Assistant\""
    echo "[$(date)] ERROR: start.sh missing at $START_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

# Run start.sh in a new Terminal window so the user can see progress
# and Ctrl+C to stop later.
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '$DIR' && ./start.sh"
end tell
EOF

echo "[$(date)] start.sh launched in Terminal" >> "$LOG_FILE"

# Notification when ready
sleep 12
if curl -s http://localhost:5173/ > /dev/null 2>&1; then
    osascript -e 'display notification "Dashboard ready at http://localhost:5173" with title "📈 Stock Portfolio Assistant" sound name "Glass"'
else
    osascript -e 'display notification "Servers starting... check Terminal window for progress" with title "📈 Stock Portfolio Assistant"'
fi
