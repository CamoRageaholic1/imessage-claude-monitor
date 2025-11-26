# iMessage Claude Monitor

Automatically respond to iMessages using Claude AI. Send yourself a message with a trigger prefix (like `!claude`) and get an instant AI response.

## Features

- ✅ Monitors iMessage database in real-time
- ✅ Trigger-based activation (only responds to messages with specific prefix)
- ✅ Runs as a background service via launchd
- ✅ Maintains conversation history per session
- ✅ Automatic restart on failure
- ✅ Detailed logging

## Requirements

- macOS 10.15 or later
- Python 3.8+
- Anthropic API key ([Get one here](https://console.anthropic.com/))
- Messages app with iMessage enabled
- Full Disk Access permission for Python/Terminal

## Quick Start

1. **Get your Anthropic API key**
   - Sign up at https://console.anthropic.com/
   - Generate an API key
   - Keep it handy for installation

2. **Run the installer**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Grant Full Disk Access**
   - Open System Settings > Privacy & Security > Full Disk Access
   - Click the '+' button
   - Add Python (`/usr/local/bin/python3` or `/opt/homebrew/bin/python3`)
   - Alternatively, add Terminal if running manually

4. **Test it out**
   - Send yourself an iMessage: `!claude Hello, how are you?`
   - You should receive a response within a few seconds

## How It Works

1. **Monitoring**: The script continuously monitors the iMessage SQLite database (`~/Library/Messages/chat.db`)
2. **Triggering**: When a new message starts with your trigger prefix (default: `!claude`), it's captured
3. **Processing**: The message text (minus the prefix) is sent to Claude's API
4. **Response**: Claude's response is sent back via iMessage to the original sender

## Architecture

```
┌─────────────────┐
│  iMessage DB    │
│  (chat.db)      │
└────────┬────────┘
         │
         │ monitors (SQLite)
         │
┌────────▼────────┐
│  Python Monitor │
│  (daemon)       │
└────────┬────────┘
         │
         │ triggers on prefix
         │
┌────────▼────────┐
│  Claude API     │
│  (Anthropic)    │
└────────┬────────┘
         │
         │ response
         │
┌────────▼────────┐
│  iMessage       │
│  (AppleScript)  │
└─────────────────┘
```

For full documentation, see the complete guides in this repository.

## Management Commands

### Start the service
```bash
launchctl load ~/Library/LaunchAgents/com.user.imessage-claude-monitor.plist
```

### Stop the service
```bash
launchctl unload ~/Library/LaunchAgents/com.user.imessage-claude-monitor.plist
```

### Check status
```bash
launchctl list | grep imessage-claude
```

### View logs
```bash
tail -f ~/Library/Logs/imessage-claude-monitor.log
```

See [QUICKSTART.md](QUICKSTART.md) for quick setup and [full documentation](https://github.com/CamoRageaholic1/imessage-claude-monitor) for advanced usage.

## License

MIT License - Feel free to modify and use as needed

## Disclaimer

This project requires access to your Messages database. Use responsibly and be aware of Anthropic's API usage terms and pricing.