#!/usr/bin/env python3
"""
Broadcast the latest cheatsheet text to Telegram channel/group and admins.

Behavior:
- Loads bot token from SPORTS_BOT_TOKEN (preferred) or TELEGRAM_BOT_TOKEN.
- Sends to TELEGRAM_CHAT_ID (channel/group) if set and valid, plus ADMIN_TELEGRAM_IDS.
- Picks the most recent outputs/CHEATSHEET_*.txt and sends a concise summary
  (header + Slam/Strong/Lean sections) to stay under Telegram’s message limits.

Usage:
  python scripts/broadcast_cheatsheet.py [--file <path>] [--token <BOT_TOKEN>]

Notes:
- Ensure the bot is added to the channel/group and is an admin.
"""

from __future__ import annotations

import os
import re
import glob
import json
import argparse
from pathlib import Path
from typing import List

import requests
from dotenv import load_dotenv


def load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_token(override: str | None) -> str:
    if override:
        return override
    token = os.environ.get("SPORTS_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("ERROR: No bot token set. Configure SPORTS_BOT_TOKEN or TELEGRAM_BOT_TOKEN in .env or pass --token.")
    return token


def get_recipients() -> List[str]:
    recips: List[str] = []
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if chat:
        # Reject bot handles by convention
        if chat.startswith("@") and chat.lower().endswith("_bot"):
            print(f"⚠️  TELEGRAM_CHAT_ID looks like a bot handle ({chat}); skipping as a destination.")
        else:
            recips.append(chat)
    admins = os.environ.get("ADMIN_TELEGRAM_IDS") or ""
    for item in re.split(r"[\s,;]+", admins.strip()):
        if item:
            recips.append(item)
    # De-dup while preserving order
    seen = set()
    uniq: List[str] = []
    for r in recips:
        if r not in seen:
            uniq.append(r)
            seen.add(r)
    if not uniq:
        raise SystemExit("ERROR: No recipients configured. Set TELEGRAM_CHAT_ID and/or ADMIN_TELEGRAM_IDS in .env.")
    return uniq


def pick_latest_file(provided: str | None) -> Path:
    if provided:
        p = Path(provided)
        if not p.exists():
            raise SystemExit(f"ERROR: File not found: {p}")
        return p
    candidates = sorted(glob.glob("outputs/CHEATSHEET_*.txt"))
    if not candidates:
        raise SystemExit("ERROR: No cheatsheet files found in outputs/.")
    return Path(candidates[-1])


def build_summary(text: str, max_len: int = 3500) -> str:
    # Extract up to the Lean Plays section for a concise message
    sections = [
        ("UNDERDOG FANTASY", None),
        ("🔥 SLAM PLAYS", "💪 STRONG"),
        ("💪 STRONG PLAYS", "📊 LEAN"),
        ("📊 LEAN PLAYS", None),
    ]
    out_lines: List[str] = []
    for start_marker, next_marker in sections:
        start_idx = text.find(start_marker)
        if start_idx == -1:
            continue
        if next_marker:
            end_idx = text.find(next_marker, start_idx)
            chunk = text[start_idx:end_idx if end_idx != -1 else None]
        else:
            chunk = text[start_idx:]
        out_lines.append(chunk.strip())
    combined = "\n\n".join([s for s in out_lines if s])
    # Truncate defensively
    if len(combined) > max_len:
        combined = combined[: max_len - 50].rstrip() + "\n… (truncated)"
    return combined


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
        # Intentionally omit parse_mode to avoid markdown entity issues
    }
    resp = requests.post(url, json=payload, timeout=20)
    try:
        data = resp.json()
    except Exception:
        print(f"❌ Non-JSON response for {chat_id}: status={resp.status_code}")
        print(resp.text[:300])
        return
    if not data.get("ok"):
        print(f"❌ Send failed for {chat_id}: {data.get('description')} (status={resp.status_code})")
    else:
        print(f"✅ Sent to {chat_id}")


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", dest="file")
    ap.add_argument("--token", dest="token")
    args = ap.parse_args()

    token = get_token(args.token)
    recipients = get_recipients()
    path = pick_latest_file(args.file)
    text = Path(path).read_text(encoding="utf-8")
    summary = build_summary(text)

    print(f"Broadcasting {path} to {len(recipients)} recipient(s)…")
    for r in recipients:
        send_message(token, r, summary)


if __name__ == "__main__":
    main()
