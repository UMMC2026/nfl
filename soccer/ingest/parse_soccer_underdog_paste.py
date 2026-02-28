"""soccer/ingest/parse_soccer_underdog_paste.py

Parse soccer (futbol) Underdog copy/paste blocks into a list of prop dicts.

This is intentionally separate from the NBA-centric root parser (`parse_underdog_paste.py`)
which assumes 2-3 letter team codes.

Supported examples (from Underdog web paste):

Rodrigo Rey
Independiente - Goalkeeper
Rodrigo Rey
@ Newell's Tue 7:15pm
2.5
Goalie Saves
Less
More

Diego BarreraDemon
Córdoba SdE - Attacker
Diego Barrera
@ Atl. Tucumán Tue 7:15pm
3.5
Shots
More

Notes:
- No scraping: caller provides the text.
- Output schema is a lightweight, analysis-agnostic slate format.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# Common noise lines in Underdog copy/paste
_NOISE = {
    "trending",
    "privacy",
    "demons & goblins indicate non-standard payouts. learn more",
}

# e.g. "19.3K", "496.4K", "13h 59m"
_K_COUNT_RE = re.compile(r"^\d+(?:\.\d+)?k$", re.IGNORECASE)
_TIME_AGO_RE = re.compile(r"^\d+\s*h\s*\d+\s*m$", re.IGNORECASE)

# Goblin/Demon/Taco markers sometimes come attached to the player name with no space
_BADGE_RE = re.compile(r"(goblin|demon|taco)\s*$", re.IGNORECASE)

# Team line in soccer paste uses full names:
#   "Independiente - Goalkeeper"
#   "Córdoba SdE - Attacker"
#
# NOTE: We intentionally accept any position token after '-' and validate it
# against ALLOWED_POSITIONS, so we don't silently break if Underdog changes
# labels (e.g., "Forward", "Striker").
_TEAM_POS_RE = re.compile(r"^(?P<team>.+?)\s*-\s*(?P<pos>.+?)\s*$", re.IGNORECASE)

# Matchup line:
#   "@ Newell's Tue 7:15pm"
#   "vs Independiente Tue 7:15pm"
_MATCHUP_RE = re.compile(
    r"^(?P<venue>@|vs)\s+(?P<opponent>.+?)\s+(?P<dow>Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b\s*(?P<time>.*)$",
    re.IGNORECASE,
)

# Numeric line value (2.5, 3, 0.5)
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")


STAT_MAP = {
    "goalie saves": "goalie_saves",
    "saves": "goalie_saves",
    "shots": "shots",
    "shots on target": "shots_on_target",
    "shot on target": "shots_on_target",
    "sot": "shots_on_target",
    "goals": "goals",
    "goal + assist": "goal_plus_assist",
    "goal+assist": "goal_plus_assist",
    "goals + assists": "goal_plus_assist",
    "goal and assist": "goal_plus_assist",

    # Defensive/aux markets seen in Underdog soccer slates
    "tackles": "tackles",
    "tackle": "tackles",
    "clearances": "clearances",
    "clearance": "clearances",
    "shots assisted": "shots_assisted",
    "shot assisted": "shots_assisted",
}


ALLOWED_POSITIONS = {"Goalkeeper", "Defender", "Midfielder", "Attacker"}


def _strip_badge(raw_name: str) -> Tuple[str, Dict[str, bool]]:
    name = (raw_name or "").strip()
    tags = {"goblin": False, "demon": False, "taco": False}

    # Handle "NameDemon" (no space)
    m = _BADGE_RE.search(name)
    if m:
        tags[m.group(1).lower()] = True
        name = _BADGE_RE.sub("", name).strip()

    return name, tags


def _is_noise(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return True
    low = s.lower()
    if low in _NOISE:
        return True
    if _K_COUNT_RE.match(low):
        return True
    if _TIME_AGO_RE.match(low):
        return True
    return False


def _parse_line_value(raw: str) -> Optional[float]:
    s = (raw or "").strip()
    if not s:
        return None
    if _NUM_RE.match(s):
        try:
            return float(s)
        except Exception:
            return None
    # Fallback: extract last float-ish token
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if not nums:
        return None
    try:
        return float(nums[-1])
    except Exception:
        return None


def map_stat_name(raw: str) -> Optional[str]:
    s = (raw or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return STAT_MAP.get(s)


def parse_lines(lines: List[str]) -> List[Dict]:
    """Parse soccer Underdog paste lines into prop dicts.

    Returns a list of props, emitting one row per available direction.
    """

    plays: List[Dict] = []
    seen: set = set()

    current_player: Optional[str] = None
    current_team: Optional[str] = None
    current_position: Optional[str] = None
    current_opponent: Optional[str] = None
    current_venue: Optional[str] = None  # '@' or 'vs'
    current_kickoff: Optional[str] = None
    current_tags = {"goblin": False, "demon": False, "taco": False}
    current_risk_flags: List[str] = []

    for i, raw in enumerate(lines):
        line = (raw or "").strip()
        if _is_noise(line):
            continue

        # Team-position line
        m_tp = _TEAM_POS_RE.match(line)
        if m_tp:
            current_team = (m_tp.group("team") or "").strip()
            pos_raw = (m_tp.group("pos") or "").strip().title()
            if pos_raw in ALLOWED_POSITIONS:
                current_position = pos_raw
            else:
                current_position = "UNKNOWN"
                if "position_unverified" not in current_risk_flags:
                    current_risk_flags.append("position_unverified")
            continue

        # Matchup line
        m_mu = _MATCHUP_RE.match(line)
        if m_mu:
            current_venue = (m_mu.group("venue") or "").strip().lower()
            current_opponent = (m_mu.group("opponent") or "").strip()
            dow = (m_mu.group("dow") or "").strip()
            time_part = (m_mu.group("time") or "").strip()
            current_kickoff = (dow + (" " + time_part if time_part else "")).strip()
            continue

        # Player name heuristic: if next line is a team-position line, treat current as player.
        next_line = (lines[i + 1] if i + 1 < len(lines) else "").strip()
        if _TEAM_POS_RE.match(next_line) and not re.search(r"\d", line):
            p, tags = _strip_badge(line)
            if p and p != current_player:
                current_player = p
                current_tags = tags
                current_risk_flags = []
                # reset per-player context that will be re-filled
                current_team = None
                current_position = None
                current_opponent = None
                current_venue = None
                current_kickoff = None
            continue

        # Some pastes repeat the player name directly after team-position.
        # If it matches current_player (or only differs by badge), ignore.
        if current_player:
            cleaned, _ = _strip_badge(line)
            if cleaned == current_player:
                continue

        # Line value -> expect stat name on next line
        line_val = _parse_line_value(line)
        if line_val is None:
            continue

        if i + 1 >= len(lines):
            continue

        stat_raw = (lines[i + 1] or "").strip()
        stat_key = map_stat_name(stat_raw)
        if not stat_key:
            continue

        # Find direction availability in next few lines
        has_higher = False
        has_lower = False
        for j in range(i + 2, min(i + 10, len(lines))):
            chk = (lines[j] or "").strip()
            if not chk:
                continue
            low = chk.lower()
            if low == "more" or "higher" in low:
                has_higher = True
            if low == "less" or "lower" in low:
                has_lower = True
            if _parse_line_value(chk) is not None:
                break

        # Build base row
        base = {
            "sport": "SOCCER",
            "league": "SOCCER",
            "player": current_player or "UNK",
            "team": current_team or "UNK",
            "position": current_position or "UNK",
            "opponent": current_opponent or "UNK",
            "venue": "away" if (current_venue == "@") else ("home" if current_venue else "UNK"),
            "kickoff": current_kickoff,
            "stat": stat_key,
            "line": float(line_val),
            # Defensive placeholders (hydration/model will fill later)
            "starter_assumed": None,
            "minutes_projection": None,
            # Light validation flags (ingest-only)
            "risk_flags": list(current_risk_flags),
            **({"goblin": True} if current_tags.get("goblin") else {}),
            **({"demon": True} if current_tags.get("demon") else {}),
            **({"taco": True} if current_tags.get("taco") else {}),
        }

        directions: List[str]
        if has_higher or has_lower:
            directions = []
            if has_higher:
                directions.append("higher")
            if has_lower:
                directions.append("lower")
        else:
            directions = ["higher", "lower"]

        for direction in directions:
            row = {**base, "direction": direction}
            key = (
                row.get("player"),
                row.get("team"),
                row.get("opponent"),
                row.get("stat"),
                row.get("line"),
                row.get("direction"),
            )
            if key in seen:
                continue
            seen.add(key)
            plays.append(row)

        # Reset badges after emitting a market (matches behavior in other parsers)
        current_tags = {"goblin": False, "demon": False, "taco": False}

    return plays


def parse_text(text: str) -> List[Dict]:
    raw = (text or "").strip()
    if not raw:
        return []
    return parse_lines(raw.splitlines())
