"""ufa.utils.player_exclusions

Central place to exclude specific players from analysis/sending.

Why:
- Sometimes you want to hard-exclude a player (e.g., injury uncertainty, personal rule).
- This keeps behavior consistent across parsers, analyzers, and Telegram senders.

NOTE: Keep this conservative and explicit. Only add exclusions when you really mean it.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, List, Mapping, Optional


def _compile_patterns_from_env() -> List[re.Pattern[str]]:
    """Build exclusion patterns from env.

    Default is intentionally EMPTY (exclude nobody).

    Supported:
      - UFA_EXCLUDE_PLAYERS: comma/space/newline separated names (matched as whole words)
      - UFA_EXCLUDE_PLAYERS_REGEX: optional extra regex patterns (comma/space/newline separated)
    """
    raw_names = (os.getenv("UFA_EXCLUDE_PLAYERS") or "").strip()
    raw_regex = (os.getenv("UFA_EXCLUDE_PLAYERS_REGEX") or "").strip()

    parts: List[str] = []
    if raw_names:
        parts.extend([p for p in re.split(r"[\s,;]+", raw_names) if p])

    patterns: List[re.Pattern[str]] = []

    # Name parts: match as whole words (safe escaping)
    for name in parts:
        # allow multi-token names to be provided via quoting? keep simple:
        # if user wants exact multi-word match, use regex env.
        escaped = re.escape(name)
        patterns.append(re.compile(rf"\\b{escaped}\\b", re.IGNORECASE))

    # Regex parts: advanced control
    if raw_regex:
        for pat in [p for p in re.split(r"[\s,;]+", raw_regex) if p]:
            try:
                patterns.append(re.compile(pat, re.IGNORECASE))
            except re.error:
                # Ignore invalid patterns (fail-open).
                continue

    return patterns


# Compiled once at import time.
# Default: no exclusions unless env vars explicitly set.
EXCLUDED_PLAYER_PATTERNS: List[re.Pattern[str]] = _compile_patterns_from_env()


def is_excluded_player(player_name: Optional[str]) -> bool:
    """Return True if the player should be excluded everywhere."""
    name = (player_name or "").strip()
    if not name:
        return False
    return any(p.search(name) for p in EXCLUDED_PLAYER_PATTERNS)


def filter_excluded_players(items: Iterable[Mapping[str, Any]], *, player_key: str = "player") -> List[Mapping[str, Any]]:
    """Filter out items whose player name matches an excluded player pattern."""
    out: List[Mapping[str, Any]] = []
    for it in items:
        try:
            player = it.get(player_key)  # type: ignore[union-attr]
        except Exception:
            player = None
        if is_excluded_player(str(player) if player is not None else None):
            continue
        out.append(it)
    return out
