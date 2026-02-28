"""telegram_push.py

Best-effort Telegram push for risk-first reports.

Goals:
- Zero exceptions: report runs should never crash due to Telegram.
- Respect standard:
  - Single game: send top 3 picks (PLAY then LEAN fill).
  - Multi-team: send STRONG/SLAM picks per team.

This uses direct Telegram Bot API (requests), no python-telegram-bot dependency.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List
import re

import requests

from ufa.promo import get_promo_window
from ufa.utils.player_exclusions import is_excluded_player


def _get_token() -> str:
    return os.getenv("SPORTS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""


def _get_chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID") or ""


def _get_chat_ids() -> List[str]:
    """Return broadcast targets.

    Priority:
    - TELEGRAM_CHAT_IDS / TELEGRAM_BROADCAST_CHAT_IDS (comma/space-separated)
    - TELEGRAM_CHAT_ID (single)
    """
    raw = (
        os.getenv("TELEGRAM_CHAT_IDS")
        or os.getenv("TELEGRAM_BROADCAST_CHAT_IDS")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    return [c for c in re.split(r"[\s,]+", raw) if c]


def _sanitize_text_for_telegram(text: str) -> str:
    """Return text that is safe to UTF-8 encode for Telegram.

    Telegram requires valid UTF-8. A common failure mode is accidentally
    constructing strings containing unpaired surrogate code points (e.g.
    from using "\\ud83c\\udfc6" style escapes).

    We replace any invalid sequences rather than raising, because Telegram
    is best-effort and should never crash report runs.
    """

    if not text:
        return ""

    # Round-trip through UTF-8 with replacement to guarantee encodability.
    # This will replace invalid surrogate code points with U+FFFD.
    try:
        return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    except Exception:
        # Absolute last resort: ensure we always return a string.
        return str(text)


def _send(text: str, *, parse_mode: str = "Markdown") -> bool:
    token = _get_token()
    chat_ids = _get_chat_ids()
    if not token or not chat_ids:
        return False

    text = _sanitize_text_for_telegram(text)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent_any = False
    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json() if resp.content else {}
            sent_any = sent_any or bool(data.get("ok"))
        except Exception:
            # best-effort
            continue

    return sent_any


def _fmt_pick(p: Dict[str, Any]) -> str:
    tier = p.get("tier", "")
    player = p.get("player", "?")
    team = p.get("team", "?")
    stat = str(p.get("stat", "")).upper()
    direction = "OVER" if p.get("direction") == "higher" else "UNDER"
    line = p.get("line", "?")
    prob = p.get("probability")

    prob_str = "" if prob is None else f" ({float(prob)*100:.0f}%)"
    return f"- {tier}: {player} ({team}) {stat} {direction} {line}{prob_str}"


def push_signals(signals: List[Dict[str, Any]], *, mode: str = "") -> bool:
    """Best-effort push. Returns True if a message was sent."""
    if not signals:
        return False

    # Hard exclude certain players from Telegram pushes.
    signals = [s for s in signals if not is_excluded_player(s.get("player"))]
    if not signals:
        return False

    promo = get_promo_window()
    max_single_game = 10 if promo.active else 3
    max_per_team = 5 if promo.active else 3

    teams = sorted({s.get("team") for s in signals if s.get("team")})
    multi_team = len(teams) > 2

    if not multi_team:
        header = "*Top 3 Picks (Per Game)*\n"
        if promo.active:
            header = header.replace("Top 3", f"Top {max_single_game}")
        body = "\n".join(_fmt_pick(s) for s in signals[:max_single_game])
        msg = header + body
        ok = _send(msg)
        return ok

    # Multi-team: group by team
    sent_any = False
    for team in teams:
        team_sigs = [s for s in signals if s.get("team") == team]
        # Prefer SLAM/STRONG
        team_sigs = [s for s in team_sigs if s.get("tier") in {"SLAM", "STRONG"}] or team_sigs
        team_sigs = team_sigs[:max_per_team]

        header = f"*{team} Strong Picks*\n"
        body = "\n".join(_fmt_pick(s) for s in team_sigs)
        msg = header + body
        if _send(msg):
            sent_any = True
            time.sleep(0.4)

    return sent_any


def can_send() -> bool:
    return bool(_get_token() and _get_chat_id())
