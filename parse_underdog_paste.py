"""
Parse Underdog raw paste into prop list.
Wraps parse_underdog_slate for menu.py integration.
"""

import re
from typing import List, Dict, Optional

from ufa.utils.player_exclusions import is_excluded_player

# Stat name mapping
STAT_MAP = {
    "points": "points",
    "pts": "points",
    "rebounds": "rebounds", 
    "reb": "rebounds",
    "rebs": "rebounds",
    "assists": "assists",
    "ast": "assists",
    "3-pointers made": "3pm",
    "3-pointers": "3pm",
    "3 pointers made": "3pm",
    "3 pointers": "3pm",
    "3pt": "3pm",
    "3pts": "3pm",
    "3pm": "3pm",
    "3ptm": "3pm",
    "3pt made": "3pm",
    "turnovers": "turnovers",
    "tov": "turnovers",
    "steals": "steals",
    "stl": "steals",
    "blocks": "blocks",
    "blk": "blocks",
    "pts + rebs + asts": "pra",
    "pra": "pra",
    "points + rebounds": "pts+reb",
    "points + assists": "pts+ast",
    "rebounds + assists": "reb+ast",
    "pts+asts": "pts+ast",
    "pts+ast": "pts+ast",
    "rebs+asts": "reb+ast",
    "reb+ast": "reb+ast",
}

# Skip these markets (not modeled)
SKIP_MARKETS = [
    "1q", "1h", "first 5", "fantasy",
    "double doubles", "triple doubles",
    "blocks + steals", "each quarter",
]


_TEAM_LINE_RE = re.compile(r"^([A-Z]{2,3})\s*-\s*")
_MATCHUP_RE = re.compile(r"\b(@|vs)\s*([A-Z]{2,3})\b", re.IGNORECASE)
# Full matchup line (team first) but robust to leading bullets/emoji/etc.
# Example: "NOP vs DET - 7:00PM CST" or "• NOP @ DET - ..."
_MATCHUP_FULL_RE = re.compile(r"\b([A-Z]{2,3})\b\s*(?:@|vs)\s*\b([A-Z]{2,3})\b", re.IGNORECASE)
_TAG_SUFFIX_RE = re.compile(r"\s*(goblin|demon|taco)\s*$", re.IGNORECASE)

# Inline prop formats (common in manual edits / some copy sources)
# Examples we support:
#   "Stephen Curry PTS 28.5 Higher"
#   "Stephen Curry 28.5 Points Higher"
#   "Stephen Curry 4.5 3-Pointers Made More"
#   "Quentin Grimes REB 4.5 Less"
_DIR_TOKENS = {"higher", "lower", "more", "less", "over", "under"}


def _normalize_dir(token: str) -> str:
    t = (token or "").strip().lower()
    if t in {"higher", "more", "over"}:
        return "higher"
    if t in {"lower", "less", "under"}:
        return "lower"
    return t


def _try_parse_inline_prop(line: str) -> Optional[Dict]:
    """Parse a single-line prop like 'Player PTS 18.5 Higher'.

    Returns a base prop dict without team/opponent filled (caller adds those).
    """
    raw = (line or "").strip()
    if not raw:
        return None

    # Quick reject: must contain a number and a direction token
    if not re.search(r"\d", raw):
        return None
    low = raw.lower()
    if not any(tok in low.split() for tok in _DIR_TOKENS):
        return None

    # Tokenize preserving original spacing for player name reconstruction
    parts = raw.split()

    # Find direction token (prefer last occurrence)
    dir_idx = None
    for idx in range(len(parts) - 1, -1, -1):
        if parts[idx].lower() in _DIR_TOKENS:
            dir_idx = idx
            break
    if dir_idx is None:
        return None
    direction = _normalize_dir(parts[dir_idx])

    # Find a numeric token (prefer the one closest to direction)
    num_idx = None
    for idx in range(dir_idx - 1, -1, -1):
        if re.fullmatch(r"\d+(?:\.\d+)?", parts[idx]):
            num_idx = idx
            break
    if num_idx is None:
        # As a fallback, pick the last number anywhere
        for idx in range(len(parts) - 1, -1, -1):
            if re.fullmatch(r"\d+(?:\.\d+)?", parts[idx]):
                num_idx = idx
                break
    if num_idx is None:
        return None

    try:
        line_val = float(parts[num_idx])
    except Exception:
        return None

    # Remaining tokens are player + stat in one of two common orders:
    #   A) Player STAT LINE DIR   -> player before stat, stat between player and line
    #   B) Player LINE STAT DIR   -> player before line, stat between line and dir
    # We decide by looking at whether tokens between player and line look like a stat.

    before_num = parts[:num_idx]
    between_num_dir = parts[num_idx + 1 : dir_idx]

    # Case A: ... <STAT> <LINE> <DIR>
    # Heuristic: if the immediate token before the number is a known stat abbreviation,
    # treat that as stat and everything before it as player.
    stat_tokens: List[str] = []
    player_tokens: List[str] = []

    if before_num:
        possible_stat = before_num[-1]
        stat_key = map_stat_name(possible_stat)
        if stat_key:
            stat_tokens = [possible_stat]
            player_tokens = before_num[:-1]
        else:
            # Case B (or longer stat): assume player is before number, stat after number
            stat_tokens = between_num_dir
            player_tokens = before_num
    else:
        stat_tokens = between_num_dir

    player = " ".join(player_tokens).strip()
    stat_name = " ".join(stat_tokens).strip()

    # If stat_name is empty but we have something before the number, try taking the last 2 tokens as stat
    if player and not stat_name and len(player_tokens) >= 3:
        # e.g. "Player 3-Pointers Made 4.5 Higher" might have been tokenized oddly in upstream sources
        stat_name = " ".join(player_tokens[-2:])
        player = " ".join(player_tokens[:-2]).strip()

    if not player:
        return None

    # Strip tag suffixes like "(Goblin)" if present (rare in inline)
    m = _TAG_SUFFIX_RE.search(player)
    tags = {"goblin": False, "demon": False, "taco": False}
    if m:
        tags[m.group(1).lower()] = True
        player = _TAG_SUFFIX_RE.sub("", player).strip()

    # Map stat
    stat_key = map_stat_name(stat_name)
    if not stat_key:
        # Some sources put stat as uppercase abbrev like PTS/REB/AST etc; map_stat_name handles that now.
        return None

    # Exclusions
    if is_excluded_player(player):
        return None

    base = {
        "player": player,
        "stat": stat_key,
        "line": line_val,
        "direction": direction,
        "league": "NBA",
        **({"goblin": True} if tags.get("goblin") else {}),
        **({"demon": True} if tags.get("demon") else {}),
        **({"taco": True} if tags.get("taco") else {}),
    }
    return base


def map_stat_name(stat_name: str) -> Optional[str]:
    """Map Underdog stat name to our format."""
    s = (stat_name or "").strip().lower()
    
    # Skip unsupported markets
    if any(k in s for k in SKIP_MARKETS):
        return None

    # Normalize common separators
    s_norm = s
    s_norm = s_norm.replace("rebs", "rebounds").replace("asts", "assists")
    s_norm = s_norm.replace("+", " + ")
    s_norm = re.sub(r"\s+", " ", s_norm).strip()

    # Try direct + normalized lookup
    return STAT_MAP.get(s) or STAT_MAP.get(s_norm) or STAT_MAP.get(s.replace(" ", ""))


def _parse_line_value(raw: str) -> Optional[float]:
    """Parse a numeric line value.

    Handles normal floats ("24.5") and taco style strings that contain
    multiple numbers stuck together ("31.524.5" -> 24.5).
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    # Taco UI sometimes copy/pastes two numbers stuck together, e.g.:
    #   "31.524.5" meaning "31.5" (old) and "24.5" (new/active)
    # Heuristic: if we see two decimal points and the middle chunk is 3 digits,
    # interpret the last two digits of the middle chunk as the integer part.
    if raw.count(".") == 2:
        parts = raw.split(".")
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            if len(parts[1]) == 3 and len(parts[2]) == 1:
                try:
                    return float(f"{parts[1][-2:]}.{parts[2]}")
                except ValueError:
                    pass

    # Accept plain float
    if re.match(r"^\d+\.?\d*$", raw):
        return float(raw)

    # Extract floats and take the last one as the active line
    nums = re.findall(r"\d+\.?\d*", raw)
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return None


def parse_lines(lines: List[str]) -> List[Dict]:
    """
    Parse list of lines from Underdog paste into prop dictionaries.
    
    Expected format (from Underdog website copy-paste):
    - "athlete or team avatar" marks next line is player name
    - "TEAM @ OPP - TIME CST" or "TEAM vs OPP - TIME CST" for matchup/team
    - Numeric line followed by stat name on next line
    - "Higher" / "Lower" on subsequent lines
    """
    plays: List[Dict] = []
    current_player: Optional[str] = None
    current_team: Optional[str] = None
    current_game = None
    current_tags = {"goblin": False, "demon": False, "taco": False}
    expect_player_name = False
    skip_current_player = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if not line:
            continue

        # Inline one-line prop format (common when users manually type/paste simplified lines)
        inline = _try_parse_inline_prop(line)
        if inline is not None:
            # Fill team/opponent + matchup context if we have it
            opponent = None
            matchup_away = None
            matchup_home = None
            if current_game:
                opponent = current_game.get("opponent")
                matchup_away = current_game.get("away")
                matchup_home = current_game.get("home")
            base_inline = {
                **inline,
                "team": current_team or "UNK",
                "opponent": opponent or "UNK",
            }
            if matchup_away and matchup_home:
                base_inline["matchup_away"] = matchup_away
                base_inline["matchup_home"] = matchup_home
            plays.append(base_inline)
            # Reset per-player tags once we emitted a market.
            current_tags = {"goblin": False, "demon": False, "taco": False}
            continue

        # Ignore noise lines common in copy/paste
        low = line.lower()
        if low in {"trending", "goblin", "demon", "demons & goblins indicate non-standard payouts. learn more"}:
            continue
        if re.match(r"^\d+(?:\.\d+)?k$", low):
            # e.g. "90.9K"
            continue
        
        # Player marker
        if "athlete or team avatar" in line.lower():
            expect_player_name = True
            continue
        
        # Player name (right after marker)
        if expect_player_name:
            # Strip tag suffix if present
            m = _TAG_SUFFIX_RE.search(line)
            current_tags = {"goblin": False, "demon": False, "taco": False}
            if m:
                current_tags[m.group(1).lower()] = True
                line = _TAG_SUFFIX_RE.sub("", line).strip()

            current_player = line
            current_team = None
            current_game = None
            expect_player_name = False
            skip_current_player = is_excluded_player(current_player)
            continue

        # Player name heuristic: many pastes are:
        #   PlayerName(Goblin/Demon/Taco)
        #   TEAM - POS
        #
        # IMPORTANT: some raw pastes do NOT include the explicit "athlete or team avatar"
        # marker and may contain many players back-to-back. In those cases, we must be able
        # to detect a *new* player even if current_player is already set.
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if _TEAM_LINE_RE.match(next_line) and not re.search(r"\d", line):
            # Avoid re-triggering on noise lines.
            if low not in {"trending"}:
                m = _TAG_SUFFIX_RE.search(line)
                current_tags = {"goblin": False, "demon": False, "taco": False}
                if m:
                    current_tags[m.group(1).lower()] = True
                    line = _TAG_SUFFIX_RE.sub("", line).strip()

                # Only treat this as a new player if it actually changes context.
                if current_player != line:
                    current_player = line
                    current_team = None
                    current_game = None
                    skip_current_player = is_excluded_player(current_player)
                    continue

        # Team line (e.g., "SAS - F-C")
        m_team = _TEAM_LINE_RE.match(line)
        if m_team:
            current_team = m_team.group(1).upper()
            continue
        
        # Matchup/opponent line. Common pastes include:
        #   "NOP vs DET - 7:00PM CST" (player team first)
        #   "DET @ NOP - 7:00PM CST" (player team first)
        # Some older formats include only "@ HOU ..." or "vs MIN ...".
        m_full = _MATCHUP_FULL_RE.search(line)
        if m_full:
            team1 = m_full.group(1).upper()
            team2 = m_full.group(2).upper()

            # Infer away/home using the separator between teams (@ or vs)
            sep_match = re.search(rf"{team1}\\s*(@|vs)\\s*{team2}", line, re.IGNORECASE)
            sep = (sep_match.group(1).lower() if sep_match else "@")
            if sep == "@":
                away, home = team1, team2
            else:
                # "vs" -> first team is home by convention
                home, away = team1, team2

            current_team = team1
            current_game = {"opponent": team2, "away": away, "home": home}
            continue

        m_mu = _MATCHUP_RE.search(line)
        if m_mu:
            # Fallback: opponent only
            current_game = {"opponent": m_mu.group(2).upper()}
            continue
        
        # Stat line (number). Supports taco strings like "31.524.5".
        stat_value = _parse_line_value(line)
        if stat_value is not None:

            # Hard exclude certain players from ever entering analysis.
            if skip_current_player:
                continue
            
            # Next line should be stat name
            if i + 1 < len(lines):
                stat_name = lines[i + 1].strip()
                stat_key = map_stat_name(stat_name)
                
                if not stat_key:
                    continue
                
                # Look for Higher/Lower or More/Less in next few lines
                has_higher = False
                has_lower = False
                
                for j in range(i + 2, min(i + 10, len(lines))):
                    check_line = lines[j].strip()
                    if 'Higher' in check_line or check_line.lower() == 'more':
                        has_higher = True
                    if 'Lower' in check_line or check_line.lower() == 'less':
                        has_lower = True
                    # Stop at next stat line
                    if _parse_line_value(check_line) is not None:
                        break
                
                if current_player and stat_key:
                    opponent = None
                    matchup_away = None
                    matchup_home = None
                    if current_game:
                        opponent = current_game.get("opponent")
                        matchup_away = current_game.get("away")
                        matchup_home = current_game.get("home")

                    base = {
                        "player": current_player,
                        "team": current_team or "UNK",
                        "opponent": opponent or "UNK",
                        "stat": stat_key,
                        "line": stat_value,
                        "league": "NBA",
                        **({"goblin": True} if current_tags.get("goblin") else {}),
                        **({"demon": True} if current_tags.get("demon") else {}),
                        **({"taco": True} if current_tags.get("taco") else {}),
                    }

                    if matchup_away and matchup_home:
                        base["matchup_away"] = matchup_away
                        base["matchup_home"] = matchup_home
                    
                    if has_higher:
                        plays.append({**base, "direction": "higher"})
                    if has_lower:
                        plays.append({**base, "direction": "lower"})
                    # If neither marked, add both directions
                    if not has_higher and not has_lower:
                        plays.append({**base, "direction": "higher"})
                        plays.append({**base, "direction": "lower"})

                    # Reset per-player tags once we emitted a market.
                    current_tags = {"goblin": False, "demon": False, "taco": False}
    
    return plays


def parse_text(text: str) -> List[Dict]:
    """Parse raw text blob into props."""
    lines = text.strip().split('\n')
    return parse_lines(lines)


if __name__ == "__main__":
    import sys
    print("Paste Underdog slate, then Ctrl+Z (Windows) or Ctrl+D (Unix) + Enter:")
    text = sys.stdin.read()
    props = parse_text(text)
    print(f"\nParsed {len(props)} props:")
    for p in props[:10]:
        print(f"  {p['player']} - {p['stat']} {p['direction']} {p['line']}")
    if len(props) > 10:
        print(f"  ... and {len(props) - 10} more")
