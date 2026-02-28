"""Parse Underdog "Total Games" market paste (match total games).

This is NOT the same format as `tennis_props_parser.py`.
The user paste often looks like:

  Madison Keys
  Madison Keys - Player
  Madison Keys
  @ Ashlyn Krueger Wed 4:00pm

  20.5
  Total Games
  Less
  More

We parse this into match-level candidates:
- player_a (subject player)
- player_b (opponent)
- line (float)
- allowed_directions: set({"OVER","UNDER"})

Notes:
- We do NOT infer surface/best-of here.
- We treat "More" as OVER and "Less" as UNDER.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Set


@dataclass(frozen=True)
class TotalGamesCandidate:
    player_a: str
    player_b: str
    line: float
    allowed_directions: Set[str]


_NOISE = {
    "trending",
    "player",
}


def _clean_name(s: str) -> str:
    s = s.strip()
    # Remove stray labels like "Goblin" stuck to the end
    s = re.sub(r"goblin$", "", s, flags=re.IGNORECASE).strip()
    return s


def _is_time_line(s: str) -> bool:
    # e.g. "@ Ashlyn Krueger Wed 4:00pm" or "vs Marin Cilic Thu 6:00pm"
    return bool(re.search(r"\b(wed|thu|fri|sat|sun|mon|tue)\b", s, flags=re.IGNORECASE)) and (
        s.strip().startswith("@") or s.strip().lower().startswith("vs")
    )


def _extract_opponent(s: str) -> Optional[str]:
    s = s.strip()
    if s.startswith("@"):  # "@ Opponent ..."
        s = s[1:].strip()
    elif s.lower().startswith("vs"):
        s = s[2:].strip()

    # Trim day/time suffix
    s = re.sub(r"\b(wed|thu|fri|sat|sun|mon|tue)\b.*$", "", s, flags=re.IGNORECASE).strip()
    return _clean_name(s) if s else None


def parse_underdog_total_games_paste(raw_text: str) -> List[TotalGamesCandidate]:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    candidates: List[TotalGamesCandidate] = []

    current_player: Optional[str] = None
    current_opponent: Optional[str] = None

    i = 0
    while i < len(lines):
        line = lines[i]
        low = line.lower()

        # Capture opponent line
        if _is_time_line(line):
            current_opponent = _extract_opponent(line)
            i += 1
            continue

        # Candidate: a float line then "Total Games"
        try:
            value = float(line)
        except ValueError:
            value = None

        if value is not None:
            # Lookahead for "Total Games"
            if i + 1 < len(lines) and lines[i + 1].strip().lower() == "total games":
                allowed: Set[str] = set()

                # scan next few lines for Less/More
                j = i + 2
                while j < len(lines):
                    nxt = lines[j].strip().lower()
                    if nxt in ("less", "more"):
                        allowed.add("UNDER" if nxt == "less" else "OVER")
                        j += 1
                        continue

                    # stop if we hit next numeric block or new player header
                    if re.fullmatch(r"\d+(?:\.\d+)?", lines[j].strip()):
                        break
                    if lines[j].strip().endswith("- Player"):
                        break
                    if _is_time_line(lines[j]):
                        break
                    j += 1

                if current_player and current_opponent:
                    candidates.append(
                        TotalGamesCandidate(
                            player_a=_clean_name(current_player),
                            player_b=_clean_name(current_opponent),
                            line=float(value),
                            allowed_directions=allowed or {"OVER", "UNDER"},
                        )
                    )
                i = j
                continue

        # Update current_player heuristically:
        # prefer explicit "Name - Player" marker; otherwise, accept a non-noise name line.
        if line.endswith("- Player"):
            nm = _clean_name(line.replace("- Player", ""))
            if nm:
                current_player = nm
            i += 1
            continue

        if low not in _NOISE and not line.startswith("@") and not low.startswith("vs"):
            # avoid lines that are clearly not names
            if low not in ("total games", "less", "more") and not re.fullmatch(r"\d+(?:\.\d+)?", line):
                # If we already have a player and this line is identical, no harm.
                if len(line) >= 3 and "@" not in line:
                    current_player = _clean_name(line)

        i += 1

    return candidates
