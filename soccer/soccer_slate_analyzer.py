#!/usr/bin/env python3
"""
SOCCER SLATE ANALYZER - RISK-FIRST APPROACH (v3 — MC + Bayesian)
=================================================================
Parses Underdog/PrizePicks soccer slates and generates probability-based edges.

v3 Upgrade:
1. SQLite database for player stats (like Tennis)
2. Position-based estimates for unknown players
3. **Monte Carlo simulation (10k)** with stat-appropriate distributions:
   - Poisson for count stats (shots, SOT, saves, tackles)
   - Zero-Inflated Poisson for rare events (goals, assists)
   - Normal for high-volume stats (passes)
4. **Bayesian Gamma-Poisson** lambda estimation (xG priors when available)
5. Percentile distribution bands (p10/p25/p50/p75/p90) in output
"""

import re
import math
import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, List, Dict, Tuple, Optional
from pathlib import Path
import sys

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Bayesian xG adjustment
try:
    from soccer.models.dr_soccer_bayes import estimate_team_lambda, LambdaEstimate
    from soccer.data.team_xg_reference import get_bayesian_context, LEAGUE_AVG_LAMBDA
    _HAS_BAYES = True
except ImportError:
    _HAS_BAYES = False

# Try SQLite database first, fall back to dict if not available
try:
    from soccer.data.soccer_stats_db import SoccerStatsDB, PlayerStats
    _db = SoccerStatsDB()
    if _db.count() > 0:
        KNOWN_PLAYERS = _db.get_all_players()
        # Silent load - no print to avoid encoding issues
    else:
        from soccer.data.player_database import KNOWN_PLAYERS, PlayerStats
except ImportError:
    from soccer.data.player_database import KNOWN_PLAYERS, PlayerStats

# Canonical tier thresholds live in config/thresholds.py (single source of truth).
from config.thresholds import implied_tier, get_all_thresholds

SOCCER_SPORT_CODE = "SOCCER"

# =============================================================================
# POSITION-BASED STAT DEFAULTS (per 90 mins)
# =============================================================================
POSITION_DEFAULTS = {
    "striker": {
        "shots": 3.5, "shots_on_target": 1.5, "passes": 25, "dribbles": 2.0,
        "crosses": 0.3, "tackles": 0.5, "clearances": 0.3
    },
    "winger": {
        "shots": 2.2, "shots_on_target": 0.9, "passes": 32, "dribbles": 4.0,
        "crosses": 2.0, "tackles": 1.0, "clearances": 0.3
    },
    "attacking_mid": {
        "shots": 2.0, "shots_on_target": 0.8, "passes": 45, "dribbles": 2.5,
        "crosses": 1.5, "tackles": 1.5, "clearances": 0.5
    },
    "midfielder": {
        "shots": 1.2, "shots_on_target": 0.5, "passes": 55, "dribbles": 1.5,
        "crosses": 1.0, "tackles": 2.5, "clearances": 1.0
    },
    "defensive_mid": {
        "shots": 0.8, "shots_on_target": 0.3, "passes": 60, "dribbles": 0.8,
        "crosses": 0.5, "tackles": 3.5, "clearances": 2.0
    },
    "defender": {
        "shots": 0.4, "shots_on_target": 0.15, "passes": 65, "dribbles": 0.5,
        "crosses": 0.8, "tackles": 2.5, "clearances": 5.0
    },
    "center_back": {
        "shots": 0.3, "shots_on_target": 0.1, "passes": 75, "dribbles": 0.3,
        "crosses": 0.2, "tackles": 2.0, "clearances": 6.0
    },
    "goalkeeper": {
        "saves": 3.0, "passes": 30, "shots": 0, "shots_on_target": 0
    },
    "attacker": {  # Generic
        "shots": 3.0, "shots_on_target": 1.3, "passes": 28, "dribbles": 2.5,
        "crosses": 0.8, "tackles": 0.6, "clearances": 0.3
    }
}

# Stat name normalization
STAT_ALIASES = {
    "sot": "shots_on_target",
    "shots on target": "shots_on_target",
    "shots on goal": "shots_on_target",  # soccer synonym; also seen as NHL SOG
    "shots attempted": "shots",
    "shots_attempted": "shots",           # underscore variant (scraper safety)
    "passes attempted": "passes",
    "passes_attempted": "passes",         # underscore variant
    "attempted dribbles": "dribbles",
    "goalie saves": "saves",
    "goalkeeper saves": "saves",
    # Composite stat aliases
    "goals+assists": "goals_assists",
    "goals + assists": "goals_assists",
    "goals_and_assists": "goals_assists",
    "g+a": "goals_assists",
    "fouls committed": "fouls_committed",
    "fouls_committed": "fouls_committed",
}


def _parse_match_teams(line: str) -> tuple[str, str]:
    """Best-effort parse of match info into (team, opponent).

    Underdog/Pick6 slates have had a few formats over time:
      - "ROM @ UDI - 1:45PM CST"
      - "ARS vs CHE"
      - "Brighton @ Chelsea" (full names)
      - "TeamA at TeamB" (some feeds)

    This function intentionally prioritizes robustness over perfection.
    """
    raw = (line or "").strip()
    ll = raw.lower()

    # Common separators; order matters ("@" is unambiguous).
    sep = None
    if "@" in raw:
        sep = "@"
    elif " vs " in ll:
        sep = "vs"
    elif " at " in ll:
        sep = "at"

    if not sep:
        return "", ""

    if sep == "@":
        left, right = raw.split("@", 1)
    else:
        # Split case-insensitively by word separator.
        parts = re.split(rf"\b{sep}\b", raw, maxsplit=1, flags=re.I)
        if len(parts) < 2:
            return "", ""
        left, right = parts[0], parts[1]

    def _clean_side(s: str) -> str:
        s = (s or "").strip()
        # Drop trailing time / extra descriptors after dash-like separators.
        s = re.split(r"\s+[-–—]\s+", s, maxsplit=1)[0].strip()
        # Collapse internal whitespace.
        s = re.sub(r"\s+", " ", s).strip()
        return s

    return _clean_side(left), _clean_side(right)


def _dedupe_parsed_props(props: List["ParsedProp"]) -> List["ParsedProp"]:
    """Dedupe parsed props while preserving order.

    Some upstream slates repeat the same prop (e.g., multiple times in one feed).
    We collapse exact duplicates to keep reports, signals, and DB writes clean.
    """
    seen: set[tuple[str, str, float, str, str]] = set()
    out: List[ParsedProp] = []
    for p in props or []:
        try:
            key = (
                _remove_accents((p.player or "").lower().strip()),
                (p.normalized_stat or "").lower().strip(),
                float(p.line),
                (p.team or "").strip(),
                (p.opponent or "").strip(),
            )
        except Exception:
            continue

        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _remove_accents(s: str) -> str:
    """Normalize a string for robust player-key lookup."""
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


@dataclass
class ParsedProp:
    """Parsed prop from slate."""
    player: str
    team: str
    position: str
    opponent: str
    line: float
    stat: str
    normalized_stat: str
    scraped_direction: str = ""  # "higher"/"lower" from platform (empty if paste-parsed)
    

@dataclass  
class AnalyzedProp:
    """Prop with calculated probabilities (v3 — MC enhanced)."""
    player: str
    team: str
    position: str
    stat: str
    line: float
    avg_per_game: float
    prob_over: float
    prob_under: float
    tier: str
    direction: str
    data_source: str  # "DATABASE" or "ESTIMATE"
    games_played: int
    avoid_reason: str = ""           # Why AVOID ("trivial_estimate"/"variance_kill"/"direction_conflict")
    scraped_direction: str = ""      # Original platform direction
    flip_direction: str = ""         # Recommended flip direction (if viable)
    flip_probability: float = 0.0    # Probability of the flip direction
    # ── MC v3 fields ──────────────────────────────────────────
    prob_method: str = "closed-form"  # "mc_poisson"/"mc_zip"/"mc_normal"/"closed-form"
    mc_simulations: int = 0
    p10: float = 0.0
    p25: float = 0.0
    p50: float = 0.0   # median
    p75: float = 0.0
    p90: float = 0.0
    mc_std: float = 0.0
    # ── Bayesian fields ───────────────────────────────────────
    bayesian_adj: float = 1.0    # Multiplier applied to avg (1.0 = no adjustment)
    bayesian_lambda: float = 0.0 # Bayesian posterior λ (0 = not computed)
    

def normalize_stat(stat: str) -> str:
    """Normalize stat name to internal format."""
    s = stat.lower().strip()
    return STAT_ALIASES.get(s, s)


def parse_underdog_slate(text: str) -> List[ParsedProp]:
    """
    Parse Underdog/PrizePicks slate format.
    
    ACTUAL UNDERDOG FORMAT (2026):
    [Line] (2.5, 1.5, 0.5) - FIRST
    [Stat] (Shots Attempted)
    [blank line]
    [Direction] (Higher/Lower)
    [Multiplier] (0.83x)
    "athlete or team avatar"
    [Player Name]
    [Match Info] (ROM @ UDI - 1:45PM CST)
    
    Then next prop starts with line again...
    """
    props = []
    lines = text.strip().split('\n')
    
    # Patterns
    line_pattern = re.compile(r'^(\d+\.?\d*)$')  # 0.5, 1.5, 2.5
    multiplier_pattern = re.compile(r'^(\d+\.?\d*)x$', re.I)  # 0.8x, 1.2x
    # Best-effort match parsing is handled by _parse_match_teams(); keep a light regex here
    # for quickly spotting match-info lines.
    match_hint_pattern = re.compile(r'\b(vs|@|at)\b', re.I)
    
    # Stat keywords for detection  
    stat_keywords = [
        'shots attempted', 'shots on target', 'shots', 'sot',
        'goals', 'assists', 'goals + assists',
        'passes', 'passes attempted',
        'saves', 'goalie saves', 'goalkeeper saves',
        '1h saves', '1h goals', '1h goals allowed', 'goals allowed',
        'dribbles', 'attempted dribbles',
        'crosses', 'tackles', 'clearances'
    ]
    
    def is_stat(line: str) -> bool:
        ll = line.lower().strip()
        return any(kw == ll or kw in ll for kw in stat_keywords)
    
    def is_direction(line: str) -> bool:
        return line.strip().lower() in ['higher', 'lower', 'over', 'under', 'more', 'less']
    
    def is_noise(line: str) -> bool:
        ll = line.lower().strip()
        if not ll:
            return True
        if 'avatar' in ll or 'trending' in ll:
            return True
        if re.match(r'^\d+\.?\d*[KkMm]$', line.strip()):
            return True
        return False
    
    def is_multiplier(line: str) -> bool:
        return bool(multiplier_pattern.match(line.strip()))
    
    def is_line_val(line: str) -> bool:
        return bool(line_pattern.match(line.strip()))
    
    def has_match_info(line: str) -> bool:
        ll = (line or "").lower()
        if not ll:
            return False
        if "@" in line:
            return True
        if " vs " in ll or " at " in ll:
            return True
        return bool(match_hint_pattern.search(line))
    
    def is_valid_player_name(name: str) -> bool:
        if not name or not name.strip():
            return False
        name = name.strip()
        if not any(c.isalpha() for c in name):
            return False
        if re.match(r'^\d+\.?\d*[KkMm]?$', name):
            return False
        if name.lower().startswith('more') or name.lower().startswith('less'):
            return False
        if 'avatar' in name.lower():
            return False
        return True
    
    # Parse using block detection - find sequences of: line -> stat -> player -> match
    current_line = None
    current_stat = None
    current_player = None
    current_match = None
    current_team = ""
    current_opponent = ""
    
    for raw_line in lines:
        line = raw_line.strip()
        
        # Skip empty and noise
        if not line or is_noise(line):
            continue
        
        # Skip directions and multipliers (not needed for analysis)
        if is_direction(line) or is_multiplier(line):
            continue
        
        # Line value - starts a new prop or continues current
        if is_line_val(line):
            # If we have a complete prop, save it first
            if current_stat and current_player and current_match:
                props.append(ParsedProp(
                    player=current_player,
                    team=current_team,
                    position="midfielder",
                    opponent=current_opponent,
                    line=current_line if current_line else 0.5,
                    stat=current_stat,
                    normalized_stat=normalize_stat(current_stat)
                ))
                # Reset for next prop
                current_stat = None
                current_player = None
                current_match = None
                current_team = ""
                current_opponent = ""
            
            current_line = float(line)
            continue
        
        # Stat type
        if is_stat(line):
            current_stat = line
            continue
        
        # Match info
        if has_match_info(line):
            current_match = line
            team_guess, opp_guess = _parse_match_teams(line)
            if team_guess:
                current_team = team_guess
            if opp_guess:
                current_opponent = opp_guess
            
            # We now have a complete prop, save it
            if current_stat and current_player:
                props.append(ParsedProp(
                    player=current_player,
                    team=current_team,
                    position="midfielder",
                    opponent=current_opponent,
                    line=current_line if current_line else 0.5,
                    stat=current_stat,
                    normalized_stat=normalize_stat(current_stat)
                ))
                # Reset for next prop
                current_line = None
                current_stat = None
                current_player = None
                current_match = None
                current_team = ""
                current_opponent = ""
            continue
        
        # If we get here and have a stat, this is likely the player name
        if current_stat and is_valid_player_name(line):
            current_player = line
            continue
    
    # Don't forget last prop if incomplete save didn't happen
    if current_stat and current_player and current_match:
        props.append(ParsedProp(
            player=current_player,
            team=current_team,
            position="midfielder",
            opponent=current_opponent,
            line=current_line if current_line else 0.5,
            stat=current_stat,
            normalized_stat=normalize_stat(current_stat)
        ))

    return _dedupe_parsed_props(props)


def parse_pick6_slate(text: str) -> List[ParsedProp]:
    """
    Parse Pick6/DraftKings slate format.
    
    PICK6 FORMAT (2026):
    "More" or "Less" (noise/direction)
    "Player NameDemon" or "Player NameGoblin" (player + label)
    "Team - Position" (Roma - Defender)
    "Player Name" (clean name)
    "@ Team Day Time" or "vs Team Day Time" (match info)
    "0.5" or "1.5" etc (line)
    "SOT" or "Passes Attempted" etc (stat)
    "Less" / "More" (direction options)
    
    Also handles condensed format:
    "Player Name"
    "@ Team Day Time"
    "52.5"
    "Passes Attempted"
    "Less"
    "More"
    """
    props = []
    lines = text.strip().split('\n')
    
    # Patterns
    line_pattern = re.compile(r'^(\d+\.?\d*)$')  # 0.5, 1.5, 52.5
    match_pattern = re.compile(r'(vs|@)\s+(\w+)', re.I)  # vs Roma, @ Udinese
    team_position_pattern = re.compile(r'^(\w+(?:\s+\w+)?)\s*-\s*(Defender|Midfielder|Attacker|Goalkeeper|Forward)$', re.I)
    demon_goblin_pattern = re.compile(r'^(.+?)(Demon|Goblin)$')  # Player NameDemon
    trending_pattern = re.compile(r'^Trending$|^\d+\.?\d*[KkMm]$')  # Trending, 1.6K
    
    # Stat keywords
    stat_keywords = [
        'sot', 'shots on target', 'shots attempted', 'shots',
        'passes attempted', 'passes',
        'goalie saves', 'saves',
        'goals', 'assists', 'goals + assists',
        'dribbles', 'crosses', 'tackles', 'clearances'
    ]
    
    def is_stat(line: str) -> bool:
        ll = line.lower().strip()
        return ll in stat_keywords or any(kw == ll for kw in stat_keywords)
    
    def is_direction(line: str) -> bool:
        return line.strip().lower() in ['more', 'less', 'higher', 'lower', 'over', 'under', 'swap']
    
    def is_noise(line: str) -> bool:
        ll = line.strip().lower()
        if not ll:
            return True
        if trending_pattern.match(line.strip()):
            return True
        if ll == 'end':
            return True
        return False
    
    def is_line_val(line: str) -> bool:
        return bool(line_pattern.match(line.strip()))
    
    def has_match_info(line: str) -> bool:
        return bool(match_pattern.search(line))
    
    def clean_player_name(name: str) -> str:
        """Remove Demon/Goblin suffix from player name."""
        m = demon_goblin_pattern.match(name.strip())
        if m:
            return m.group(1).strip()
        return name.strip()
    
    def is_valid_player_name(name: str) -> bool:
        if not name or not name.strip():
            return False
        name = name.strip()
        if not any(c.isalpha() for c in name):
            return False
        if is_direction(name) or is_stat(name) or is_line_val(name):
            return False
        if team_position_pattern.match(name):
            return False
        if has_match_info(name):
            return False
        if is_noise(name):
            return False
        return True
    
    # State machine for parsing
    i = 0
    pending_team = ""  # Track team from "Team - Position" lines
    pending_position = "midfielder"
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty, noise, and direction lines
        if not line or is_noise(line) or is_direction(line):
            i += 1
            continue
        
        # Capture "Team - Position" lines for next player
        if team_position_pattern.match(line):
            m = team_position_pattern.match(line)
            if m:
                pending_team = m.group(1) if m.lastindex >= 1 else ""
                # Extract team from the full match (everything before " - ")
                parts = line.split(' - ')
                if len(parts) >= 2:
                    pending_team = parts[0].strip()
                pending_position = m.group(2).lower() if m.lastindex >= 2 else "midfielder"
            i += 1
            continue
        
        # Skip Demon/Goblin header lines (we'll get the clean name later)
        if demon_goblin_pattern.match(line):
            i += 1
            continue
        
        # Look for a player name followed by match info, line, stat
        if is_valid_player_name(line):
            player_name = clean_player_name(line)
            match_info = None
            line_val = None
            stat_type = None
            team = pending_team  # Use pending team from previous "Team - Position" line
            opponent = ""
            position = pending_position
            
            # Reset pending for next prop
            pending_team = ""
            pending_position = "midfielder"
            
            # Scan forward for match info, line, and stat
            j = i + 1
            while j < len(lines) and j < i + 8:  # Look ahead up to 8 lines
                next_line = lines[j].strip()
                
                # Skip noise/direction
                if not next_line or is_noise(next_line) or is_direction(next_line):
                    j += 1
                    continue
                
                # Skip team-position (only update if team not already set)
                if team_position_pattern.match(next_line):
                    # Extract team and position from "Team - Position" format
                    if not team:  # Only set if not already from pending
                        parts = next_line.split(' - ')
                        if len(parts) >= 2:
                            team = parts[0].strip()
                    m = team_position_pattern.match(next_line)
                    if m and m.lastindex >= 2:
                        position = m.group(2).lower()
                    j += 1
                    continue
                
                # Skip Demon/Goblin headers
                if demon_goblin_pattern.match(next_line):
                    j += 1
                    continue
                
                # Match info
                if has_match_info(next_line) and not match_info:
                    match_info = next_line
                    m = match_pattern.search(next_line)
                    if m:
                        opponent = m.group(2)
                    j += 1
                    continue
                
                # Line value
                if is_line_val(next_line) and line_val is None:
                    line_val = float(next_line)
                    j += 1
                    continue
                
                # Stat type
                if is_stat(next_line) and stat_type is None:
                    stat_type = next_line
                    j += 1
                    break  # We have what we need
                
                # If we hit another player name, stop
                if is_valid_player_name(next_line) and next_line != player_name:
                    break
                
                j += 1
            
            # Create prop if we have enough info
            if player_name and stat_type and line_val is not None:
                props.append(ParsedProp(
                    player=player_name,
                    team=team,
                    position=position,
                    opponent=opponent,
                    line=line_val,
                    stat=stat_type,
                    normalized_stat=normalize_stat(stat_type)
                ))
            
            i = j if j > i else i + 1
        else:
            i += 1
    
    return props


def parse_slate_auto(text: str) -> List[ParsedProp]:
    """
    Auto-detect format and parse slate.
    Tries Pick6 first (has team-position lines), then Underdog format.
    """
    # Detect Pick6/Underdog 2026 format by looking for:
    # - Demon/Goblin markers
    # - SOT stat
    # - "Team - Position" pattern (Qadsiah - Attacker, Roma - Defender)
    team_position_pattern = re.compile(r'^\w+(?:\s+\w+)?\s*-\s*(Defender|Midfielder|Attacker|Goalkeeper|Forward)$', re.I | re.MULTILINE)
    
    if 'Demon' in text or 'Goblin' in text or '\nSOT\n' in text or team_position_pattern.search(text):
        props = parse_pick6_slate(text)
        if props:
            return _dedupe_parsed_props(props)
    
    # Try Underdog format
    props = parse_underdog_slate(text)
    if props:
        return _dedupe_parsed_props(props)
    
    # Last resort: try Pick6 anyway
    return _dedupe_parsed_props(parse_pick6_slate(text))


# Stats this analyzer can model end-to-end.
SOCCER_MODEL_STATS = {
    "shots",
    "shots_on_target",
    "passes",
    "dribbles",
    "crosses",
    "tackles",
    "clearances",
    "saves",
    "goals",
    "assists",
    "goals_assists",
    "interceptions",
    "fouls_committed",
}

# ── Cross-sport collision guard ──────────────────────────────────
# Stats whose names collide with NHL (SOG, saves, goals, G+A),
# NBA/CBB (assists), or PWHL (shots on goal).
# For these stats, only include the prop if the player exists in
# the soccer database — unknown players are almost certainly from
# another sport's scrape page.
SOCCER_SHARED_STATS = {
    "goals", "assists", "saves", "shots_on_target", "shots",
    "goals_assists",
}

# Stats that are unique enough to soccer that non-DB players are OK
# (no other sport on Underdog/PP/DK uses these exact labels).
SOCCER_UNIQUE_STATS = SOCCER_MODEL_STATS - SOCCER_SHARED_STATS

# Maximum realistic line values in soccer for shared stats.
# Lines above these are virtually impossible in soccer and indicate
# the prop is from another sport (e.g. NHL saves 25.5, NBA assists 8.5).
_SOCCER_MAX_LINE = {
    "goals": 2.5,
    "assists": 1.5,
    "goals_assists": 3.5,
    "saves": 8.5,
    "shots_on_target": 5.5,
    "shots": 7.5,
}


def parsed_props_from_scraped_props(props: List[Dict[str, Any]]) -> List[ParsedProp]:
    """Convert normalized scraped props into ParsedProp records.

    This lets us run soccer analysis directly from `outputs/props_latest.json`
    (Playwright scrape or Odds API ingestion) without needing paste-format text.
    """

    out: List[ParsedProp] = []
    _rejected_other_sport = 0
    for p in props or []:
        if not isinstance(p, dict):
            continue

        player = str(p.get("player") or "").strip()
        stat = str(p.get("stat") or "").strip()
        line = p.get("line")

        if not player or not stat or line is None:
            continue

        try:
            line_f = float(line)
        except Exception:
            continue

        normalized_stat = normalize_stat(stat)
        if normalized_stat not in SOCCER_MODEL_STATS:
            continue

        # ── Cross-sport collision guard ───────────────────────
        # Playwright scrapes ALL sports from Underdog in one pass.
        # Stats like "assists", "goals", "shots on goal", "saves"
        # collide with NHL/NBA/CBB/PWHL. For these shared stats,
        # require the player to be in the soccer database; unknown
        # players are rejected as likely non-soccer.
        lookup_name = _remove_accents(player.lower().strip())
        in_soccer_db = False
        team = ""
        position = "midfielder"  # safe generic default
        try:
            if isinstance(KNOWN_PLAYERS, dict) and lookup_name in KNOWN_PLAYERS:
                in_soccer_db = True
                rec = KNOWN_PLAYERS[lookup_name]
                team = getattr(rec, "team", "") or ""
                position = getattr(rec, "position", position) or position
        except Exception:
            pass

        # Check sport metadata if available (Odds API path)
        prop_sport = str(p.get("sport") or p.get("meta", {}).get("sport", "")).strip().upper()
        if prop_sport and prop_sport not in ("", "SOCCER", "FOOTBALL"):
            # Explicit non-soccer sport tag → skip
            _rejected_other_sport += 1
            continue

        if normalized_stat in SOCCER_SHARED_STATS and not in_soccer_db:
            # Line-based sanity check: absurdly high lines are definite non-soccer
            max_line = _SOCCER_MAX_LINE.get(normalized_stat, 999)
            if line_f > max_line:
                _rejected_other_sport += 1
                continue
            # Even within plausible range, unknown players + shared stats = skip
            _rejected_other_sport += 1
            continue

        # Preserve scraped direction for flip analysis ("higher"/"lower")
        scraped_dir = str(p.get("direction") or "").strip().lower()

        out.append(
            ParsedProp(
                player=player,
                team=team,
                position=position,
                opponent="",
                line=line_f,
                stat=stat,
                normalized_stat=normalized_stat,
                scraped_direction=scraped_dir,
            )
        )

    if _rejected_other_sport:
        print(f"[FILTER] Rejected {_rejected_other_sport} non-soccer props (NHL/NBA/CBB/PWHL collision)")

    return _dedupe_parsed_props(out)


def analyze_scraped_props(props: List[Dict[str, Any]], show_no_play: bool = False) -> str:
    """Analyze a list of normalized scraped props and return a formatted report."""
    parsed = parsed_props_from_scraped_props(props)
    print(f"[INFO] Converted {len(parsed)} soccer-modelable props from scraped JSON")
    analyzed = [analyze_prop(p) for p in parsed]
    return format_report(analyzed, show_no_play=show_no_play)


def analyze_scraped_props_structured(
    props: List[Dict[str, Any]], *, show_no_play: bool = False
) -> tuple[str, List[AnalyzedProp]]:
    """Structured variant of analyze_scraped_props().

    Returns:
        (report_text, analyzed_props)
    """
    parsed = parsed_props_from_scraped_props(props)
    print(f"[INFO] Converted {len(parsed)} soccer-modelable props from scraped JSON")
    analyzed = [analyze_prop(p) for p in parsed]
    return format_report(analyzed, show_no_play=show_no_play), analyzed


def _stable_edge_id(*, player: str, team: str, opponent: str, stat: str, direction: str, line: float) -> str:
    key = f"{player}|{team}|{opponent}|{stat}|{direction}|{line}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def build_quant_edges_from_analyzed(
    analyzed: List[AnalyzedProp],
    *,
    sport: str = SOCCER_SPORT_CODE,
    source: str = "soccer_slate_analyzer",
) -> List[Dict[str, Any]]:
    """Convert analyzed soccer props into canonical edge dicts.

    Output is designed to be compatible with:
      - engine.daily_picks_db.save_top_picks
      - cross-sport parlay builder
      - sport-scoped signals export

    Notes:
      - Direction uses the repo-standard "higher"/"lower" strings.
      - Picks below the sport LEAN threshold are marked REJECTED.
      - ESTIMATE-based picks are flagged FRAGILE (VETTED) via the eligibility gate.
    """
    # Lazy import to keep soccer analyzer usable in isolation.
    try:
        from core.decision_governance import EligibilityGate
    except Exception:
        EligibilityGate = None  # type: ignore[assignment]

    gate = EligibilityGate() if EligibilityGate else None

    edges: List[Dict[str, Any]] = []
    for a in analyzed or []:
        best_prob = a.prob_over if a.direction == "OVER" else a.prob_under
        best_prob = float(best_prob)

        direction = "higher" if a.direction == "OVER" else "lower"
        tier = str(a.tier or "AVOID").upper()

        # Soccer-specific fragility: any ESTIMATE-based stat should never be optimizable.
        is_fragile = bool(a.data_source == "ESTIMATE" or (a.games_played and a.games_played < 3))

        eligibility_dict: Optional[Dict[str, Any]] = None
        pick_state = "OPTIMIZABLE"

        # Enforce tier gate: below LEAN threshold = do not export as playable.
        if tier == "AVOID":
            pick_state = "REJECTED"
        elif gate is not None:
            try:
                elig = gate.evaluate(
                    {
                        "sport": sport,
                        "player": a.player,
                        "team": a.team,
                        "opponent": "",
                        "stat": a.stat,
                        "line": a.line,
                        "direction": direction,
                        "probability": best_prob,
                        "is_fragile": is_fragile,
                        "matchup_games_vs": 99,
                    }
                )
                eligibility_dict = elig.to_dict()
                pick_state = str(elig.state.value)
            except Exception:
                # Fail safe: never mark ungoverned picks as optimizable
                pick_state = "VETTED" if is_fragile else "REJECTED"

        normalized_stat = normalize_stat(a.stat)
        edge = {
            "edge_id": _stable_edge_id(
                player=a.player,
                team=a.team or "",
                opponent="",
                stat=normalized_stat,
                direction=direction,
                line=float(a.line),
            ),
            "sport": sport,
            "entity": a.player,
            "player": a.player,
            "team": a.team or "",
            "opponent": "",
            "market": normalized_stat,
            "stat": normalized_stat,
            "line": float(a.line),
            "direction": direction,
            "probability": best_prob,
            "tier": tier,
            "pick_state": pick_state,
            "data_source": a.data_source,
            "mu": float(a.avg_per_game),
            "sample_n": int(a.games_played or 0),
            "source": source,
        }

        if eligibility_dict is not None:
            edge["eligibility"] = eligibility_dict

        edges.append(edge)

    return edges


def export_soccer_quant_artifacts(
    analyzed: List[AnalyzedProp],
    *,
    league_tag: str = "",
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write soccer quant artifacts (signals + governance) without clobbering global NBA outputs.

    Files written:
      - outputs/soccer_signals_latest.json (sport-scoped, stable)
      - outputs/soccer_signals_<timestamp>.json (sport-scoped, timestamped)
      - soccer/outputs/governance_*.json + allowed/blocked edges (stable + timestamped)
      - soccer/outputs/signals_latest.json (legacy, for soccer-local tooling)
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stamp = datetime.now().strftime("%Y%m%d")

    tag = (league_tag or "").strip().upper()
    slug = f"SOCCER_{tag}" if tag else "SOCCER"

    edges = build_quant_edges_from_analyzed(analyzed, sport=SOCCER_SPORT_CODE, source="soccer")

    # Signals should include only optimizable picks (LEAN+) so downstream parlay tools stay governed.
    signals = [
        e
        for e in edges
        if e.get("pick_state") == "OPTIMIZABLE" and e.get("tier") in {"LEAN", "STRONG", "SLAM"}
    ]

    root_outputs = Path("outputs")
    root_outputs.mkdir(parents=True, exist_ok=True)
    soccer_outputs = Path(__file__).resolve().parent / "outputs"
    soccer_outputs.mkdir(parents=True, exist_ok=True)

    signals_latest = root_outputs / "soccer_signals_latest.json"
    signals_ts = root_outputs / f"soccer_signals_{ts}.json"
    soccer_signals_latest = soccer_outputs / "signals_latest.json"

    signals_latest.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    signals_ts.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    soccer_signals_latest.write_text(json.dumps(signals, indent=2), encoding="utf-8")

    # Build a governance-style analysis payload for soccer/outputs (sport-local)
    results: List[Dict[str, Any]] = []
    for e in edges:
        p = float(e.get("probability") or 0.0)
        tier = str(e.get("tier") or "AVOID").upper()
        state = str(e.get("pick_state") or "REJECTED").upper()

        if state != "OPTIMIZABLE":
            decision = "BLOCKED"
            block_reason = f"pick_state={state}"
        elif tier in {"SLAM", "STRONG"}:
            decision = "PLAY"
            block_reason = None
        elif tier == "LEAN":
            decision = "LEAN"
            block_reason = None
        else:
            decision = "BLOCKED"
            block_reason = f"tier={tier}"

        normalized_stat = str(e.get("stat") or "")
        mu = float(e.get("mu") or 0.0)
        # Reasonable default sigma for audit: Poisson std sqrt(mu) for count stats, else 0.2*mu for passes.
        if normalized_stat == "passes":
            sigma = abs(mu) * 0.20
            prob_method = "normal"
        else:
            sigma = math.sqrt(mu) if mu > 0 else 0.0
            prob_method = "poisson"

        results.append(
            {
                "player": e.get("player"),
                "team": e.get("team"),
                "opponent": e.get("opponent"),
                "stat": normalized_stat,
                "line": e.get("line"),
                "direction": e.get("direction"),
                "decision": decision,
                "block_reason": block_reason,
                "model_confidence": p * 100.0,
                "effective_confidence": p * 100.0,
                "mu": mu,
                "sigma": sigma,
                "sample_n": e.get("sample_n", 0),
                "prob_method": prob_method,
                "gate_details": [e.get("eligibility")] if e.get("eligibility") else [],
                "source": e.get("source"),
            }
        )

    analysis_payload = {
        "sport": SOCCER_SPORT_CODE,
        "slug": slug,
        "stamp": stamp,
        "created_at_local": datetime.now().isoformat(),
        "source": source or {},
        "results": results,
    }

    try:
        from governance_artifacts import export_governance_artifacts

        exported = export_governance_artifacts(
            analysis_payload,
            slug=slug,
            stamp=stamp,
            out_dir=soccer_outputs,
            run_settings=None,
            source=source or {},
        )
    except Exception:
        exported = {}

    return {
        "slug": slug,
        "stamp": stamp,
        "edges": edges,
        "signals": signals,
        "signals_latest": signals_latest,
        "signals_timestamped": signals_ts,
        "soccer_signals_latest": soccer_signals_latest,
        "governance_exports": exported,
    }


# Composite stat definitions: stat_key → list of component attrs to sum
_COMPOSITE_STATS = {
    "goals_assists": ["goals", "assists"],
}


def _resolve_composite_avg(player_obj, stat: str) -> float:
    """Sum component attributes for composite stats (e.g. goals_assists = goals + assists)."""
    components = _COMPOSITE_STATS.get(stat)
    if not components:
        return 0.0
    total = 0.0
    found_any = False
    for comp in components:
        val = getattr(player_obj, comp, 0) or 0
        if val > 0:
            found_any = True
        total += val
    return total if found_any else 0.0


def get_player_avg(player_name: str, stat: str, position: str) -> Tuple[float, str, int]:
    """
    Get player's average for stat.
    Returns: (avg_per_game, data_source, games_played)
    """
    # Normalize player name for lookup - remove all accents
    lookup_name = _remove_accents(player_name.lower().strip())
    
    is_composite = stat in _COMPOSITE_STATS
    
    # Try database lookup
    if lookup_name in KNOWN_PLAYERS:
        p = KNOWN_PLAYERS[lookup_name]
        avg = _resolve_composite_avg(p, stat) if is_composite else (getattr(p, stat, 0) or 0)
        if avg > 0:
            return avg, "DATABASE", p.games_played
    
    # Try partial match
    for key, player in KNOWN_PLAYERS.items():
        key_normalized = _remove_accents(key)
        name_normalized = _remove_accents(player.name.lower())
        
        if lookup_name in key_normalized or key_normalized in lookup_name:
            avg = _resolve_composite_avg(player, stat) if is_composite else (getattr(player, stat, 0) or 0)
            if avg > 0:
                return avg, "DATABASE", player.games_played
        # Also try matching by display name
        if lookup_name in name_normalized or name_normalized in lookup_name:
            avg = _resolve_composite_avg(player, stat) if is_composite else (getattr(player, stat, 0) or 0)
            if avg > 0:
                return avg, "DATABASE", player.games_played
    
    # Fall back to position-based estimate
    pos_key = position.lower().replace(" ", "_")
    if pos_key in POSITION_DEFAULTS:
        if is_composite:
            # Sum component defaults
            avg = sum(POSITION_DEFAULTS[pos_key].get(c, 0) for c in _COMPOSITE_STATS[stat])
        else:
            avg = POSITION_DEFAULTS[pos_key].get(stat, 0)
        return avg, "ESTIMATE", 0
    
    # Last resort: generic defaults
    defaults = {"shots": 1.5, "shots_on_target": 0.6, "passes": 40, "dribbles": 1.5, "saves": 3.0, "crosses": 0.8,
                "goals_assists": 0.25, "interceptions": 1.0, "fouls_committed": 1.0}
    return defaults.get(stat, 1.0), "ESTIMATE", 0


def poisson_over_probability(avg: float, line: float) -> float:
    """P(X > line) using Poisson distribution."""
    if avg <= 0:
        return 0.0
    
    # P(X > line) = 1 - P(X <= floor(line))
    k_max = int(line)  # For "over 1.5", we need P(X >= 2) = 1 - P(X <= 1)
    
    cumulative = 0.0
    for k in range(k_max + 1):
        cumulative += (avg ** k) * math.exp(-avg) / math.factorial(k)
    
    return 1.0 - cumulative


def normal_over_probability(avg: float, line: float, std_ratio: float = 0.25) -> float:
    """P(X > line) using Normal distribution (for high-count stats like passes)."""
    if avg <= 0:
        return 0.0
    
    std = avg * std_ratio
    z = (line - avg) / std
    
    # Standard normal CDF approximation
    def norm_cdf(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    return 1.0 - norm_cdf(z)


def get_tier(prob: float) -> str:
    """Tier implied by probability using canonical thresholds.

    NOTE: This intentionally uses the repo-wide thresholds (with sport overrides)
    rather than hardcoded soccer-specific numbers.
    """
    return implied_tier(float(prob), sport=SOCCER_SPORT_CODE)


# Minimum averages by stat type (can't have 0 avg - leads to 100% UNDER)
STAT_MINIMUM_AVG = {
    "goals": 0.15,           # Most players avg ~0.15-0.3 goals/game
    "assists": 0.10,
    "shots": 1.0,
    "shots_on_target": 0.4,
    "passes": 20,
    "saves": 2.0,            # Goalies face shots
    "clearances": 1.0,
    "tackles": 1.0,
    "dribbles": 0.5,
    "crosses": 0.5,
    "goals_assists": 0.25,   # Composite: goals + assists
    "interceptions": 0.5,
    "fouls_committed": 0.5,
}

# Confidence caps by data source
ESTIMATE_CONFIDENCE_CAP = 0.72   # Max 72% for estimated data (no real stats)
DATABASE_CONFIDENCE_CAP = 0.92  # Max 92% even with real data (variance exists)

# TRIVIAL PICKS: These combos with ESTIMATES should be NO_PLAY (mathematically true but not actionable)
# Format: (stat, direction, line) - if data_source is ESTIMATE, auto-reject
TRIVIAL_ESTIMATE_PICKS = [
    ("goals", "UNDER", 0.5),       # Everyone scores <0.5 goals - trivial
    ("goals", "UNDER", 1.5),       # Most players score <1.5 - trivial
    ("assists", "UNDER", 0.5),     # Everyone gets <0.5 assists - trivial
    ("assists", "UNDER", 1.5),     # Most get <1.5 assists - trivial
]


def is_trivial_estimate_pick(stat: str, direction: str, line: float, source: str) -> bool:
    """Check if this is a trivial estimate pick that should be downgraded."""
    if source != "ESTIMATE":
        return False
    stat_lower = stat.lower().strip()
    for trivial_stat, trivial_dir, trivial_line in TRIVIAL_ESTIMATE_PICKS:
        # Match if stat contains trivial_stat (handles "Goals", "goals", "Goalie Saves", etc.)
        if trivial_stat in stat_lower and direction.upper() == trivial_dir.upper() and line <= trivial_line:
            return True
    return False


def analyze_prop(prop: ParsedProp) -> AnalyzedProp:
    """Analyze a single prop and calculate probabilities.

    v3 — Monte Carlo + Bayesian upgrade:
    - Uses 10k MC simulations with stat-appropriate distributions
    - Poisson for count stats (shots, SOT, saves, tackles)
    - Zero-Inflated Poisson for rare events (goals, assists)
    - Normal for high-volume stats (passes)
    - Falls back to closed-form if numpy unavailable
    - Tracks avoid reasons and direction flips
    """
    avg, source, gp = get_player_avg(prop.player, prop.normalized_stat, prop.position)

    # CRITICAL FIX: Apply minimum average floor to prevent 100% probabilities
    stat_key = prop.normalized_stat.lower()
    min_avg = STAT_MINIMUM_AVG.get(stat_key, 0.5)
    if avg < min_avg:
        avg = min_avg

    # ── Distribution selection ───────────────────────────────────
    # Map stat to distribution type (mirrors soccer_config.py)
    _ZIP_STATS = {"goals", "assists", "goals_assists", "goal_contributions"}
    _NORMAL_STATS = {"passes", "passes_completed", "touches"}

    if stat_key in _NORMAL_STATS:
        dist_type = "normal"
    elif stat_key in _ZIP_STATS:
        dist_type = "zip"
    else:
        dist_type = "poisson"

    # ── Bayesian opponent adjustment (goals/assists only) ────────
    bayesian_adj = 1.0
    bayesian_lambda = 0.0
    _BAYESIAN_ELIGIBLE = {"goals", "assists", "goals_assists", "goal_contributions",
                          "shots", "shots_on_target"}

    if _HAS_BAYES and stat_key in _BAYESIAN_ELIGIBLE and prop.team and prop.opponent:
        ctx = get_bayesian_context(prop.team, prop.opponent)
        if ctx:
            try:
                # Bayesian posterior: blend team xG_for with opponent xGA
                bayes_est = estimate_team_lambda(
                    xg_for=ctx["team_xg_for"],
                    xg_against=ctx["opp_xga"],
                    matches_played=ctx["team_matches"],
                )
                bayesian_lambda = bayes_est.lam
                league_avg = ctx["league_avg_lambda"]

                # Multiplier: how much does this matchup deviate from league avg?
                # Capped at [0.75, 1.35] to prevent extreme swings
                if league_avg > 0:
                    raw_mult = bayesian_lambda / league_avg
                    bayesian_adj = max(0.75, min(1.35, raw_mult))
                    avg = avg * bayesian_adj
            except Exception:
                pass  # Bayes failure is non-fatal; use raw avg

    # Tag prob_method with +bayes suffix when Bayesian adjustment applied
    _bayes_tag = "+bayes" if bayesian_adj != 1.0 else ""

    # ── Monte Carlo simulation (10k) ─────────────────────────────
    N_SIMS = 10000
    mc_percentiles = {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0}
    mc_std = 0.0
    prob_method = "closed-form"

    if _HAS_NUMPY:
        rng = np.random.default_rng()
        games_for_var = max(gp, 5) if gp > 0 else 10  # sample-size uncertainty

        if dist_type == "poisson":
            # Hierarchical: sample λ from Gamma(shape, 1/rate) to capture uncertainty
            # shape ~ avg * games, rate ~ games  =>  E[λ]=avg, Var[λ]=avg/games
            shape = avg * games_for_var
            rate = float(games_for_var)
            lambda_samples = rng.gamma(shape, 1.0 / rate, N_SIMS)
            sims = rng.poisson(np.maximum(lambda_samples, 0.01))
            prob_method = "mc_poisson" + _bayes_tag

        elif dist_type == "zip":
            # Zero-Inflated Poisson  —  structural-zero + Poisson
            # π estimated from position + stat
            pos_lower = (prop.position or "").lower().replace(" ", "_")
            if stat_key in ("goals", "goal_contributions"):
                pi_map = {"striker": 0.30, "attacker": 0.35, "winger": 0.50,
                          "attacking_mid": 0.55, "midfielder": 0.70,
                          "defensive_mid": 0.80, "defender": 0.85,
                          "center_back": 0.88, "goalkeeper": 0.95}
            else:  # assists
                pi_map = {"winger": 0.45, "attacking_mid": 0.40,
                          "striker": 0.55, "attacker": 0.50,
                          "midfielder": 0.55, "defensive_mid": 0.65,
                          "defender": 0.75, "center_back": 0.80,
                          "goalkeeper": 0.90}
            pi = pi_map.get(pos_lower, 0.60)

            # λ for the non-zero component: avg / (1-π)
            lam_nz = avg / max(1.0 - pi, 0.05)
            shape = lam_nz * games_for_var
            rate = float(games_for_var)
            lambda_samples = rng.gamma(max(shape, 0.5), 1.0 / max(rate, 1.0), N_SIMS)
            poisson_part = rng.poisson(np.maximum(lambda_samples, 0.01))
            is_struct_zero = rng.random(N_SIMS) < pi
            sims = np.where(is_struct_zero, 0, poisson_part)
            prob_method = "mc_zip" + _bayes_tag

        else:  # normal
            std_ratio = 0.20
            sigma = avg * std_ratio
            mu_std = sigma / np.sqrt(games_for_var)
            mu_samples = rng.normal(avg, mu_std, N_SIMS)
            sigma_samples = sigma * rng.uniform(0.85, 1.15, N_SIMS)
            sims = np.maximum(rng.normal(mu_samples, sigma_samples), 0)
            prob_method = "mc_normal" + _bayes_tag

        # Probabilities from MC
        prob_over = float(np.mean(sims > prop.line))
        prob_under = float(np.mean(sims < prop.line))
        # Handle the edge-case where sims == line exactly (push)
        push_frac = float(np.mean(sims == prop.line))
        if prob_over + prob_under < 0.999:
            # Split pushes evenly
            prob_over += push_frac / 2
            prob_under += push_frac / 2

        mc_percentiles = {
            "p10": float(np.percentile(sims, 10)),
            "p25": float(np.percentile(sims, 25)),
            "p50": float(np.percentile(sims, 50)),
            "p75": float(np.percentile(sims, 75)),
            "p90": float(np.percentile(sims, 90)),
        }
        mc_std = float(np.std(sims))
    else:
        # Fallback: closed-form (original code path)
        if stat_key in _NORMAL_STATS:
            prob_over = normal_over_probability(avg, prop.line, std_ratio=0.20)
        else:
            prob_over = poisson_over_probability(avg, prop.line)
        prob_under = 1.0 - prob_over

    # ---------- raw (uncapped) best direction ----------
    raw_over = prob_over
    raw_under = prob_under

    # Determine best direction
    if prob_over >= prob_under:
        direction = "OVER"
        best_prob = prob_over
    else:
        direction = "UNDER"
        best_prob = prob_under

    # CRITICAL FIX: Apply confidence caps based on data source
    if source == "ESTIMATE":
        best_prob = min(best_prob, ESTIMATE_CONFIDENCE_CAP)
    else:
        best_prob = min(best_prob, DATABASE_CONFIDENCE_CAP)

    # ---------- Avoid-reason + direction-flip detection ----------
    avoid_reason = ""
    flip_direction = ""
    flip_probability = 0.0

    # Normalize scraped direction to OVER/UNDER for comparison
    scraped_dir_norm = ""
    sd = prop.scraped_direction.lower().strip()
    if sd in ("higher", "over"):
        scraped_dir_norm = "OVER"
    elif sd in ("lower", "under"):
        scraped_dir_norm = "UNDER"

    # Get tiering threshold for LEAN
    try:
        lean_threshold = get_all_thresholds(SOCCER_SPORT_CODE).get("LEAN", 0.56)
    except Exception:
        lean_threshold = 0.56

    # CRITICAL FIX #2: Trivial estimate picks get downgraded to NO_PLAY
    if is_trivial_estimate_pick(prop.normalized_stat, direction, prop.line, source):
        tier = "AVOID"
        avoid_reason = "trivial_estimate"
        opp_prob = raw_under if direction == "OVER" else raw_over
        opp_dir = "UNDER" if direction == "OVER" else "OVER"
        if opp_prob >= lean_threshold:
            flip_direction = opp_dir
            flip_probability = opp_prob
    else:
        tier = get_tier(best_prob)

    # If AVOID from tier threshold (not trivial), classify the reason
    if tier == "AVOID" and not avoid_reason:
        if scraped_dir_norm and scraped_dir_norm != direction:
            avoid_reason = "direction_conflict"
            flip_direction = direction
            flip_probability = best_prob
        elif max(raw_over, raw_under) < lean_threshold:
            avoid_reason = "variance_kill"
        else:
            avoid_reason = "capped_estimate"

    # Direction-flip annotation for NON-AVOID picks too
    if scraped_dir_norm and scraped_dir_norm != direction and tier != "AVOID":
        flip_direction = direction
        flip_probability = best_prob

    # Recalculate prob_over/under with cap applied
    if direction == "OVER":
        prob_over = best_prob
        prob_under = 1.0 - best_prob
    else:
        prob_under = best_prob
        prob_over = 1.0 - best_prob

    return AnalyzedProp(
        player=prop.player,
        team=prop.team,
        position=prop.position,
        stat=prop.stat,
        line=prop.line,
        avg_per_game=avg,
        prob_over=prob_over,
        prob_under=prob_under,
        tier=tier,
        direction=direction,
        data_source=source,
        games_played=gp,
        avoid_reason=avoid_reason,
        scraped_direction=prop.scraped_direction,
        flip_direction=flip_direction,
        flip_probability=flip_probability,
        prob_method=prob_method,
        mc_simulations=N_SIMS if _HAS_NUMPY else 0,
        p10=mc_percentiles["p10"],
        p25=mc_percentiles["p25"],
        p50=mc_percentiles["p50"],
        p75=mc_percentiles["p75"],
        p90=mc_percentiles["p90"],
        mc_std=mc_std,
        bayesian_adj=bayesian_adj,
        bayesian_lambda=bayesian_lambda,
    )


def format_report(analyzed: List[AnalyzedProp], show_no_play: bool = False) -> str:
    """Format analysis report with tiers (ASCII-safe for Windows terminals)."""
    report = []
    report.append("=" * 70)
    report.append("[SOCCER] PROP ANALYSIS - RISK-FIRST REPORT")
    report.append("=" * 70)

    # MC engine indicator
    mc_props = [a for a in analyzed if a.mc_simulations > 0]
    bayes_count = sum(1 for a in analyzed if a.bayesian_adj != 1.0)
    if mc_props:
        method_set = set(a.prob_method for a in mc_props)
        report.append(f"[ENGINE] Monte Carlo ({mc_props[0].mc_simulations:,} sims) | Distributions: {', '.join(sorted(method_set))}")
    else:
        report.append("[ENGINE] Closed-form (numpy unavailable)")
    if bayes_count > 0:
        report.append(f"[BAYES] Gamma-Poisson xG adjustment applied to {bayes_count}/{len(analyzed)} props")

    # Thresholds snapshot (sport overrides + runtime overrides)
    try:
        th = get_all_thresholds(SOCCER_SPORT_CODE)
    except Exception:
        th = {}
    
    # Count by data source
    db_count = sum(1 for a in analyzed if a.data_source == "DATABASE")
    est_count = sum(1 for a in analyzed if a.data_source == "ESTIMATE")
    
    report.append(f"\n[DATA] Sources: {db_count} from DATABASE | {est_count} from ESTIMATES")
    
    if est_count > 0:
        report.append("[!] ESTIMATES are position-based averages - treat with caution!")
    
    report.append("\n")
    
    # Group by tier (canonical)
    tiers = {"SLAM": [], "STRONG": [], "LEAN": [], "AVOID": []}
    for prop in analyzed:
        tiers.setdefault(prop.tier, []).append(prop)
    
    # SLAM
    if tiers["SLAM"]:
        slam_t = th.get("SLAM")
        slam_label = f"{(slam_t * 100):.0f}%+" if isinstance(slam_t, (int, float)) else "(enabled)"
        report.append(f"[SLAM] ({slam_label}) - ELITE CONFIDENCE")
        report.append("-" * 50)
        for p in tiers["SLAM"]:
            prob = p.prob_over if p.direction == "OVER" else p.prob_under
            source_icon = "[DB]" if p.data_source == "DATABASE" else "[EST]"
            team_display = f" ({p.team})" if (p.team or "").strip() else ""
            report.append(f"  {source_icon} {p.player}{team_display}")
            report.append(f"     {p.stat} {p.direction} {p.line} - {prob*100:.1f}%")
            report.append(f"     Avg: {p.avg_per_game:.1f}/game | GP: {p.games_played or 'EST'}")
            if p.mc_simulations > 0:
                report.append(f"     Range: p10={p.p10:.1f} | p50={p.p50:.1f} | p90={p.p90:.1f} [{p.prob_method}]")
            if p.bayesian_adj != 1.0:
                report.append(f"     [B] Bayesian adj: x{p.bayesian_adj:.2f} (lam={p.bayesian_lambda:.2f})")
            if p.flip_direction:
                report.append(f"     [!] Platform offered opposite -- model says {p.direction}")
            report.append("")

    # STRONG
    if tiers["STRONG"]:
        strong_t = th.get("STRONG")
        strong_label = f"{(strong_t * 100):.0f}%+" if isinstance(strong_t, (int, float)) else "(enabled)"
        report.append(f"[STRONG] ({strong_label}) - HIGH CONFIDENCE")
        report.append("-" * 50)
        for p in tiers["STRONG"]:
            prob = p.prob_over if p.direction == "OVER" else p.prob_under
            source_icon = "[DB]" if p.data_source == "DATABASE" else "[EST]"
            team_display = f" ({p.team})" if (p.team or "").strip() else ""
            report.append(f"  {source_icon} {p.player}{team_display}")
            report.append(f"     {p.stat} {p.direction} {p.line} - {prob*100:.1f}%")
            report.append(f"     Avg: {p.avg_per_game:.1f}/game | GP: {p.games_played or 'EST'}")
            if p.mc_simulations > 0:
                report.append(f"     Range: p10={p.p10:.1f} | p50={p.p50:.1f} | p90={p.p90:.1f} [{p.prob_method}]")
            if p.bayesian_adj != 1.0:
                report.append(f"     [B] Bayesian adj: x{p.bayesian_adj:.2f} (lam={p.bayesian_lambda:.2f})")
            if p.flip_direction:
                report.append(f"     [!] Platform offered opposite -- model says {p.direction}")
            report.append("")
    
    # LEAN
    if tiers["LEAN"]:
        lean_t = th.get("LEAN")
        lean_label = f"{(lean_t * 100):.0f}%+" if isinstance(lean_t, (int, float)) else "(enabled)"
        report.append(f"\n[LEAN] ({lean_label}) - ACTIONABLE")
        report.append("-" * 50)
        for p in tiers["LEAN"]:
            prob = p.prob_over if p.direction == "OVER" else p.prob_under
            source_icon = "[DB]" if p.data_source == "DATABASE" else "[EST]"
            team_display = f" ({p.team})" if (p.team or "").strip() else ""
            report.append(f"  {source_icon} {p.player}{team_display}")
            report.append(f"     {p.stat} {p.direction} {p.line} - {prob*100:.1f}%")
            report.append(f"     Avg: {p.avg_per_game:.1f}/game | GP: {p.games_played or 'EST'}")
            if p.mc_simulations > 0:
                report.append(f"     Range: p10={p.p10:.1f} | p50={p.p50:.1f} | p90={p.p90:.1f} [{p.prob_method}]")
            if p.bayesian_adj != 1.0:
                report.append(f"     [B] Bayesian adj: x{p.bayesian_adj:.2f} (lam={p.bayesian_lambda:.2f})")
            if p.flip_direction:
                report.append(f"     [!] Platform offered opposite -- model says {p.direction}")
            report.append("")

    # AVOID — enhanced with avoid_reason + flip annotations
    if tiers["AVOID"]:
        if show_no_play:
            report.append(f"\n[AVOID] (below LEAN threshold) - SKIP")
            report.append("-" * 50)
            
            # Human-readable reason labels
            _REASON_LABELS = {
                "trivial_estimate": "TRIVIAL (EST)",
                "variance_kill": "NO EDGE",
                "direction_conflict": "WRONG DIR",
                "capped_estimate": "CAP-LIMITED",
            }
            
            for p in tiers["AVOID"]:
                prob = p.prob_over if p.direction == "OVER" else p.prob_under
                reason_tag = _REASON_LABELS.get(p.avoid_reason, "")
                reason_suffix = f"  [{reason_tag}]" if reason_tag else ""
                report.append(f"  [X] {p.player} - {p.stat} {p.direction} {p.line} - {prob*100:.1f}%{reason_suffix}")
                
                # Show scraped direction mismatch if detected
                if p.scraped_direction:
                    sd_norm = "OVER" if p.scraped_direction in ("higher", "over") else "UNDER" if p.scraped_direction in ("lower", "under") else ""
                    if sd_norm and sd_norm != p.direction:
                        report.append(f"       Platform offered: {sd_norm} | Model best: {p.direction}")
                
                # Show flip recommendation if viable
                if p.flip_direction and p.flip_probability > 0:
                    flip_tier = get_tier(p.flip_probability)
                    if flip_tier != "AVOID":
                        report.append(f"       -> FLIP: {p.flip_direction} @ {p.flip_probability*100:.1f}% ({flip_tier})")
                    else:
                        report.append(f"       -> Flip {p.flip_direction} also weak: {p.flip_probability*100:.1f}%")
                
                # Show both-sides summary for variance kills
                if p.avoid_reason == "variance_kill":
                    report.append(f"       OVER: {p.prob_over*100:.1f}% | UNDER: {p.prob_under*100:.1f}% -- coin flip")
        else:
            report.append(f"\n[AVOID] - {len(tiers['AVOID'])} props skipped")
    
    # Summary
    report.append("\n" + "=" * 70)
    actionable = len(tiers["SLAM"]) + len(tiers["STRONG"]) + len(tiers["LEAN"])
    report.append(f"[SUMMARY] ACTIONABLE PICKS: {actionable}")
    report.append(f"   SLAM: {len(tiers['SLAM'])} | STRONG: {len(tiers['STRONG'])} | LEAN: {len(tiers['LEAN'])}")
    
    if actionable > 0 and est_count > 0:
        report.append("\n[!] NOTE: Some picks use ESTIMATES. Prioritize DATABASE picks.")
    
    # CHEAT SHEET
    report.append("\n" + "=" * 70)
    report.append("[CHEAT SHEET] - Copy/Paste Ready")
    report.append("=" * 70)
    
    for tier_name in ["SLAM", "STRONG", "LEAN"]:
        for p in tiers[tier_name]:
            prob = p.prob_over if p.direction == "OVER" else p.prob_under
            icon = "**" if tier_name in {"SLAM", "STRONG"} else "*"
            report.append(f"{icon} {p.player} {p.stat} {p.direction} {p.line} ({prob*100:.0f}%)")
    
    report.append("=" * 70)
    
    return "\n".join(report)


def analyze_slate_file(filepath: str, show_no_play: bool = False) -> str:
    """Analyze a slate file and return formatted report."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Use auto-detect parser (handles both Pick6 and Underdog formats)
    props = parse_slate_auto(text)
    print(f"[INFO] Parsed {len(props)} props from slate")
    
    analyzed = [analyze_prop(p) for p in props]
    return format_report(analyzed, show_no_play=show_no_play)


if __name__ == "__main__":
    import sys
    
    show_all = "--all" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    
    if args:
        filepath = args[0]
    else:
        # Default to today's slate
        filepath = Path(__file__).parent / "inputs" / "slate_20260201.txt"
    
    if Path(filepath).exists():
        report = analyze_slate_file(str(filepath), show_no_play=show_all)
        print(report)
    else:
        print(f"[ERROR] File not found: {filepath}")
        print("Usage: python soccer_slate_analyzer.py <slate_file> [--all]")
