# Quick Start

## Prerequisites
- macOS 10.15 or later
- Python 3.8+ (`python3 --version`)
- Anthropic API key from https://console.anthropic.com/
- Messages app signed into iMessage on this Mac

## Install

```bash
git clone https://github.com/CamoRageaholic1/imessage-claude-monitor.git
cd imessage-claude-monitor
chmod +x install.sh
./install.sh
```

The installer:
- prompts for your API key (or reads `$ANTHROPIC_API_KEY`)
- installs the `anthropic` Python package via `pip --user`
- copies `imessage_claude_monitor.py` to `~/`
- renders `com.user.imessage-claude-monitor.plist` with your paths/key into `~/Library/LaunchAgents/`
- loads the agent with `launchctl`

## Grant Full Disk Access

Reading `~/Library/Messages/chat.db` requires Full Disk Access for the Python binary that runs the daemon. The installer prints the exact path. Add it under **System Settings → Privacy & Security → Full Disk Access**, then reload:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.imessage-claude-monitor.plist
launchctl load   ~/Library/LaunchAgents/com.user.imessage-claude-monitor.plist
```

## Test

From another iMessage-enabled device, send your account:

```
!claude what model are you?
```

You should get a reply within a few seconds. If not:

```bash
tail -n 100 ~/Library/Logs/imessage-claude-monitor.log
tail -n 100 ~/Library/Logs/imessage-claude-monitor-error.log
```

Common failures:
- `sqlite error: ... (Full Disk Access granted?)` — the Python binary in the plist is not in the FDA allow list.
- `osascript failed` — Messages.app is not signed in, or macOS prompted for Automation permission and was denied.

## Configuration

Flags accepted by `imessage_claude_monitor.py` (set in the plist's `ProgramArguments`):

| Flag | Default | Purpose |
|------|---------|---------|
| `--prefix` | `!claude` | Trigger prefix that activates a response |
| `--interval` | `2` | Poll interval (seconds) |
| `--model` | `claude-sonnet-4-6` | Anthropic model id |
| `--log-level` | `INFO` | Python logging level |

Per-chat conversation history is kept in `~/.imessage_claude_state.json`, capped at the most recent 20 turn pairs.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.user.imessage-claude-monitor.plist
rm ~/Library/LaunchAgents/com.user.imessage-claude-monitor.plist
rm ~/imessage_claude_monitor.py
rm -f ~/.imessage_claude_state.json
```

## Notes & Caveats

- The plist contains your API key in plaintext (mode 600). Use a dedicated key with conservative rate limits.
- Only one-on-one chats are supported by the AppleScript send path. Group chats are not handled.
- On Ventura+ some message bodies are stored only in `attributedBody` (a typedstream blob). The monitor uses a heuristic to recover plaintext; if it fails, the message is skipped silently.
- The monitor only acts on inbound messages (`is_from_me = 0`). To trigger from your own Apple ID, send from a different signed-in device.
