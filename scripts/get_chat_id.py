#!/usr/bin/env python3
"""
Get Telegram chat information (numeric chat id, title) for a channel/group.

Usage:
  python scripts/get_chat_id.py <chat> [--token <BOT_TOKEN>]

Examples:
  python scripts/get_chat_id.py @YourChannelName
  python scripts/get_chat_id.py -1001234567890
  python scripts/get_chat_id.py @YourChannelName --token 123456:ABC-DEF...

Notes:
- The bot must be able to access the chat (added to the channel/group).
- For private channels/groups, supply the numeric -100... chat id.
- For public channels, supplying @username is supported by getChat.
"""

import os
import sys
import json
import argparse
import requests

DEFAULT_BASE = "https://api.telegram.org"


def get_token(cli_token: str | None) -> str:
    if cli_token:
        return cli_token
    # Prefer SPORTS_BOT_TOKEN, fallback TELEGRAM_BOT_TOKEN
    token = os.environ.get("SPORTS_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("ERROR: No bot token provided. Set SPORTS_BOT_TOKEN/TELEGRAM_BOT_TOKEN or pass --token.")
    return token


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chat", help="@username or numeric chat id (-100...) of the target channel/group")
    parser.add_argument("--token", dest="token", help="Bot token (overrides env)")
    parser.add_argument("--base", dest="base", default=DEFAULT_BASE, help="Telegram API base URL")
    args = parser.parse_args()

    token = get_token(args.token)
    chat = args.chat

    url = f"{args.base}/bot{token}/getChat"
    resp = requests.get(url, params={"chat_id": chat}, timeout=15)
    try:
        data = resp.json()
    except Exception:
        print(f"ERROR: Non-JSON response, status={resp.status_code}")
        print(resp.text[:500])
        raise SystemExit(1)

    if not data.get("ok"):
        print(f"ERROR: {data.get('description')} (status={resp.status_code})")
        print("Tip: Ensure the bot is added to the channel/group and is an admin.")
        print("      For private chats, use the numeric -100... chat id.")
        raise SystemExit(1)

    chat_info = data["result"]
    # Print a concise summary and the raw JSON for reference
    chat_id = chat_info.get("id")
    title = chat_info.get("title") or chat_info.get("username") or chat_info.get("first_name")
    chat_type = chat_info.get("type")
    print(f"✅ Chat resolved: id={chat_id} type={chat_type} title={title}")
    print(json.dumps(chat_info, indent=2))


if __name__ == "__main__":
    main()
