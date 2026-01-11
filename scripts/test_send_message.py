#!/usr/bin/env python3
"""
Send a test message to a Telegram channel/group to verify that the bot can post.

Usage:
  python scripts/test_send_message.py <chat> [--text "Hello"] [--token <BOT_TOKEN>]

Examples:
  python scripts/test_send_message.py @YourChannelName --text "Cheatsheet test"
  python scripts/test_send_message.py -1001234567890 --text "Hello world"
"""

import os
import sys
import argparse
import requests

DEFAULT_BASE = "https://api.telegram.org"


def get_token(cli_token: str | None) -> str:
    if cli_token:
        return cli_token
    token = os.environ.get("SPORTS_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("ERROR: No bot token provided. Set SPORTS_BOT_TOKEN/TELEGRAM_BOT_TOKEN or pass --token.")
    return token


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chat", help="@username or numeric chat id (-100...) of the target channel/group")
    parser.add_argument("--text", dest="text", default="Test message from sports bot", help="Message text")
    parser.add_argument("--token", dest="token", help="Bot token (overrides env)")
    parser.add_argument("--base", dest="base", default=DEFAULT_BASE, help="Telegram API base URL")
    args = parser.parse_args()

    token = get_token(args.token)
    url = f"{args.base}/bot{token}/sendMessage"
    payload = {
        "chat_id": args.chat,
        "text": args.text,
        # Avoid parse_mode to prevent markdown entity errors in testing
        # "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
        "disable_notification": False,
    }

    resp = requests.post(url, json=payload, timeout=15)
    try:
        data = resp.json()
    except Exception:
        print(f"ERROR: Non-JSON response, status={resp.status_code}")
        print(resp.text[:500])
        raise SystemExit(1)

    if not data.get("ok"):
        print(f"ERROR: {data.get('description')} (status={resp.status_code})")
        print("Tip: Ensure the bot is an admin of the target channel/group.")
        raise SystemExit(1)

    msg = data["result"]
    print(f"✅ Message sent: chat_id={msg['chat']['id']} message_id={msg['message_id']}")


if __name__ == "__main__":
    main()
