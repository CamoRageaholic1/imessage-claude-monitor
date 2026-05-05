#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.user.imessage-claude-monitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
SCRIPT_NAME="imessage_claude_monitor.py"
SCRIPT_DEST="$HOME/$SCRIPT_NAME"
LOG_DIR="$HOME/Library/Logs"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This installer is macOS only." >&2
  exit 1
fi

PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "python3 not found on PATH. Install Python 3.8+ first." >&2
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  read -r -s -p "Anthropic API key: " ANTHROPIC_API_KEY
  echo
fi
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
  echo "API key required." >&2
  exit 1
fi

echo "==> Installing Python dependencies with $PYTHON_BIN"
"$PYTHON_BIN" -m pip install --user -r "$REPO_DIR/requirements.txt"

echo "==> Copying $SCRIPT_NAME to $SCRIPT_DEST"
cp "$REPO_DIR/$SCRIPT_NAME" "$SCRIPT_DEST"
chmod +x "$SCRIPT_DEST"

echo "==> Writing launch agent to $PLIST_DEST"
mkdir -p "$(dirname "$PLIST_DEST")" "$LOG_DIR"

# sed delimiter '|' avoids clashing with '/' in paths.
sed \
  -e "s|/usr/local/bin/python3|$PYTHON_BIN|g" \
  -e "s|/Users/YOUR_USERNAME|$HOME|g" \
  -e "s|YOUR_API_KEY_HERE|$ANTHROPIC_API_KEY|g" \
  "$REPO_DIR/$PLIST_NAME" > "$PLIST_DEST"
chmod 600 "$PLIST_DEST"  # plist holds the API key

if launchctl list 2>/dev/null | grep -q com.user.imessage-claude-monitor; then
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi
launchctl load "$PLIST_DEST"

cat <<EOF

Installed.

Next steps:
  1. Grant Full Disk Access to: $PYTHON_BIN
     System Settings -> Privacy & Security -> Full Disk Access
     Then reload:
       launchctl unload  $PLIST_DEST
       launchctl load    $PLIST_DEST
  2. Test from another iMessage device:  !claude hello
  3. Logs:
       tail -f $LOG_DIR/imessage-claude-monitor.log
       tail -f $LOG_DIR/imessage-claude-monitor-error.log
EOF
