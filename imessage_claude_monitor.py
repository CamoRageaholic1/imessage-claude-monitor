#!/usr/bin/env python3
"""iMessage to Claude monitor daemon.

Polls the local iMessage database for new incoming messages whose body starts
with a trigger prefix, sends the remainder to Claude, and replies back through
the Messages app via osascript.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

from anthropic import Anthropic

CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"
STATE_FILE = Path.home() / ".imessage_claude_state.json"
DEFAULT_PREFIX = "!claude"
DEFAULT_INTERVAL = 2.0
DEFAULT_MODEL = "claude-sonnet-4-6"
HISTORY_LIMIT = 20  # user/assistant turn pairs kept per chat

SYSTEM_PROMPT = (
    "You are replying inside an iMessage thread. Keep responses short, "
    "conversational, and free of markdown unless the user asks for it."
)

log = logging.getLogger("imessage-claude-monitor")


# ---- state ----------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            data.setdefault("last_rowid", 0)
            data.setdefault("history", {})
            return data
        except json.JSONDecodeError:
            log.warning("State file corrupt; starting fresh")
    return {"last_rowid": 0, "history": {}}


def save_state(state: dict) -> None:
    tmp = STATE_FILE.parent / (STATE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE_FILE)


# ---- iMessage db ----------------------------------------------------------

def open_db() -> sqlite3.Connection:
    if not CHAT_DB.exists():
        raise SystemExit(f"chat.db not found at {CHAT_DB}; is iMessage enabled?")
    uri = f"file:{CHAT_DB}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5.0)


def initial_rowid(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(ROWID), 0) FROM message").fetchone()
    return int(row[0])


def fetch_new_messages(
    conn: sqlite3.Connection, last_rowid: int
) -> Iterator[tuple[int, str | None, bytes | None, str, str]]:
    cursor = conn.execute(
        """
        SELECT m.ROWID, m.text, m.attributedBody, c.guid, c.chat_identifier
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        JOIN chat c ON c.ROWID = cmj.chat_id
        WHERE m.ROWID > ?
          AND m.is_from_me = 0
        ORDER BY m.ROWID ASC
        """,
        (last_rowid,),
    )
    yield from cursor


def extract_attributed_text(blob: bytes | None) -> str | None:
    """Best-effort plaintext extraction from a typedstream attributedBody blob.

    On Ventura+ the message body is sometimes only in attributedBody. A full
    typedstream parser is overkill here; we locate the NSString marker and pull
    the printable run that follows it.
    """
    if not blob:
        return None
    marker = b"NSString"
    idx = blob.find(marker)
    if idx < 0:
        return None
    i = idx + len(marker) + 1
    while i < len(blob) and blob[i] < 0x20 and blob[i] not in (0x09, 0x0A, 0x0D):
        i += 1
    end = i
    while end < len(blob) and blob[end] != 0x86:  # typedstream end-of-object
        end += 1
    text = blob[i:end].decode("utf-8", errors="ignore").rstrip("\x00").strip()
    return text or None


# ---- AppleScript send -----------------------------------------------------

SEND_SCRIPT = """
on run argv
    set targetId to item 1 of argv
    set theText to item 2 of argv
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy targetId of targetService
        send theText to targetBuddy
    end tell
end run
"""


def send_imessage(target: str, text: str) -> None:
    result = subprocess.run(
        ["osascript", "-e", SEND_SCRIPT, target, text],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "osascript failed")


# ---- Claude ----------------------------------------------------------------

def ask_claude(client: Anthropic, model: str, history: list[dict], user_text: str) -> str:
    messages = history + [{"role": "user", "content": user_text}]
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()


# ---- main loop -------------------------------------------------------------

def run(prefix: str, interval: float, model: str) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)

    state = load_state()
    conn = open_db()
    if state["last_rowid"] == 0:
        state["last_rowid"] = initial_rowid(conn)
        save_state(state)
    log.info(
        "Starting at ROWID=%d, prefix=%r, interval=%.1fs, model=%s",
        state["last_rowid"], prefix, interval, model,
    )

    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while not stop:
        try:
            for rowid, text, attributed, chat_guid, chat_identifier in fetch_new_messages(
                conn, state["last_rowid"]
            ):
                state["last_rowid"] = max(state["last_rowid"], rowid)
                body = (text or extract_attributed_text(attributed) or "").strip()
                if not body.startswith(prefix):
                    continue
                user_text = body[len(prefix):].strip()
                if not user_text:
                    continue
                log.info("Trigger from %s (rowid=%d): %s", chat_identifier, rowid, user_text)
                history = state["history"].setdefault(chat_guid, [])
                try:
                    reply = ask_claude(client, model, history, user_text)
                except Exception as e:
                    log.exception("Claude API error")
                    reply = f"[Claude error: {e}]"
                if not reply:
                    reply = "[Claude returned no text]"
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": reply})
                if len(history) > HISTORY_LIMIT * 2:
                    state["history"][chat_guid] = history[-HISTORY_LIMIT * 2:]
                save_state(state)
                try:
                    send_imessage(chat_identifier, reply)
                    log.info("Replied to %s (%d chars)", chat_identifier, len(reply))
                except Exception:
                    log.exception("Failed to send reply via osascript")
        except sqlite3.OperationalError as e:
            log.error("sqlite error: %s (Full Disk Access granted?)", e)
        save_state(state)
        slept = 0.0
        while slept < interval and not stop:
            time.sleep(min(0.25, interval - slept))
            slept += 0.25


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prefix", default=DEFAULT_PREFIX,
                   help=f"trigger prefix (default: {DEFAULT_PREFIX})")
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                   help=f"poll interval in seconds (default: {DEFAULT_INTERVAL})")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Anthropic model id (default: {DEFAULT_MODEL})")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    run(prefix=args.prefix, interval=args.interval, model=args.model)


if __name__ == "__main__":
    main()
