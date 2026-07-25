#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# install_morning_launcher.sh — One-command install for login auto-launch
#
# Installs a macOS LaunchAgent that, on every user login, shows a dialog:
#   "Start Stock Portfolio Assistant? [Yes / Not now]"
# If yes → opens Terminal and runs start.sh → opens browser when ready.
#
# Usage:
#   bash install_morning_launcher.sh         # install
#   bash install_morning_launcher.sh remove  # uninstall
# ──────────────────────────────────────────────────────────────────────

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.user.stock-portfolio"
PLIST_SRC="$DIR/${PLIST_NAME}.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LAUNCH_SCRIPT="$DIR/morning_launch.sh"

# ── Uninstall path ────────────────────────────────────────────────────
if [ "$1" = "remove" ] || [ "$1" = "uninstall" ]; then
    echo "🗑  Removing morning launcher..."
    if [ -f "$PLIST_DEST" ]; then
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
        rm "$PLIST_DEST"
        echo "✅ Removed $PLIST_DEST"
    else
        echo "ℹ  Not installed."
    fi
    exit 0
fi

# ── Install path ──────────────────────────────────────────────────────
echo "📦 Installing morning launcher..."

if [ ! -f "$PLIST_SRC" ]; then
    echo "❌ $PLIST_SRC not found"
    exit 1
fi

if [ ! -f "$LAUNCH_SCRIPT" ]; then
    echo "❌ $LAUNCH_SCRIPT not found"
    exit 1
fi

chmod +x "$LAUNCH_SCRIPT"
chmod +x "$DIR/start.sh" 2>/dev/null || true
chmod +x "$DIR/stop.sh"  2>/dev/null || true

mkdir -p "$HOME/Library/LaunchAgents"

# Write plist with absolute path substituted in
sed "s|YOUR_REPO_PATH|$DIR|g" "$PLIST_SRC" > "$PLIST_DEST"

# Reload (unload first in case it's already loaded)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "✅ Installed: $PLIST_DEST"
echo "✅ Script:    $LAUNCH_SCRIPT"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  The launcher will show a dialog at next login."
echo ""
echo "  Test it right now without logging out:"
echo "    bash morning_launch.sh"
echo ""
echo "  To remove later:"
echo "    bash install_morning_launcher.sh remove"
echo "════════════════════════════════════════════════════════════════"
