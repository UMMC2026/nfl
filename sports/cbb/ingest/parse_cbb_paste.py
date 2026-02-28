"""
Parse Underdog raw paste into CBB prop list.
CBB-specific variant of parse_underdog_paste.py for NCAA basketball.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import json

# CBB-specific stat name mapping
STAT_MAP = {
    # Core stats (same as NBA)
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "3-pointers made": "3pm",
    "3-pointers": "3pm",
    "3pm": "3pm",
    "3ptm": "3pm",
    "3pt made": "3pm",
    "turnovers": "turnovers",
    "steals": "steals",
    "blocks": "blocks",
    
    # Combo stats
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

# Skip these markets (not modeled for CBB)
SKIP_MARKETS = [
    "1h", "first half", "2h", "second half",
    "fantasy", "fg attempted", "ft made",
    "3s attempted", "double doubles", "triple doubles",
    "offensive rebounds", "blocks + steals",
    "min.", "fg made", "field goals made", "dunks",
]

# CBB team abbreviation regex (2-5 chars for some schools)
_TEAM_LINE_RE = re.compile(r"^([A-Z]{2,5})\s*-\s*")

# Original matchup patterns (team abbreviations only)
_MATCHUP_RE = re.compile(r"\b(@|vs)\s*([A-Z]{2,5})\b", re.IGNORECASE)
_MATCHUP_FULL_RE = re.compile(r"\b([A-Z]{2,5})\b\s*(?:@|vs)\s*\b([A-Z]{2,5})\b", re.IGNORECASE)

# Enhanced matchup patterns for full team names and mixed formats
# Matches: "Miami Hurricanes @ Florida Gators", "Miami @ Florida", "Duke vs North Carolina"
_MATCHUP_FULL_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:@|vs|at)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
    re.IGNORECASE
)

# Matches team names in parentheses after player: "Peter Suder (Miami @ Florida)"
_MATCHUP_PARENS_RE = re.compile(
    r"\(([A-Z]{2,5}|[A-Z][a-z]+)\s*(?:@|vs|at)\s*([A-Z]{2,5}|[A-Z][a-z]+)\)",
    re.IGNORECASE
)

# Matches slash-separated teams: "MIA/FLA" or "Miami/Florida"
_MATCHUP_SLASH_RE = re.compile(
    r"\b([A-Z]{2,5}|[A-Z][a-z]+)\s*/\s*([A-Z]{2,5}|[A-Z][a-z]+)\b",
    re.IGNORECASE
)
_TAG_SUFFIX_RE = re.compile(r"\s*(goblin|demon|taco)\s*$", re.IGNORECASE)

# Compact one-line formats (for Quick Analyze / report-style input)
_COMPACT_LINE_RE = re.compile(
    r"^\s*(?:[-•*]\s*)?"  # optional bullet
    r"(?P<player>.+?)"  # player name (lazy)
    r"(?:\s*\((?P<team_paren>[^)]+)\))?"  # optional team in parentheses
    r"\s+(?P<stat>points|rebounds|assists|pra|pts\+reb\+ast|pts\+reb|pts\+ast|reb\+ast|3pm|3ptm|3-?pointers?\s+made|turnovers|steals|blocks)"
    r"\s+(?P<direction>higher|lower|over|under|more|less)"
    r"\s+(?P<line>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


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

    return STAT_MAP.get(s) or STAT_MAP.get(s_norm) or STAT_MAP.get(s.replace(" ", ""))


def _parse_line_value(raw: str) -> Optional[float]:
    """Parse a numeric line value with taco-string handling."""
    raw = (raw or "").strip()
    if not raw:
        return None

    # Taco UI double-number handling (e.g., "31.524.5")
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


def sanitize_player_name(name: str) -> str:
    """
    Clean up player names that may have been corrupted during paste.
    Fixes common issues like "MoreThomas" -> "Thomas" from UI copy artifacts.
    """
    if not name:
        return name
    
    # Remove common UI paste artifacts (e.g., "More" button text concatenated with name)
    artifacts = ["More", "Less", "Show", "Hide", "Expand", "Collapse", "View"]
    for artifact in artifacts:
        if name.startswith(artifact) and len(name) > len(artifact):
            # Check if next char is uppercase (indicates concatenation)
            remaining = name[len(artifact):]
            if remaining and remaining[0].isupper():
                name = remaining
                break
    
    return name.strip()


def normalize_team_name(raw_team: str) -> str:
    """
    Convert full team names to abbreviations.
    
    Examples:
        "Miami Hurricanes" → "MIAMI"
        "Florida Gators" → "FLA"
        "North Carolina" → "NC"
        "MIA" → "MIA" (already abbreviated)
    
    If already abbreviated (2-5 uppercase letters), return as-is.
    Otherwise, use CBBStatsCache normalization if available.
    """
    if not raw_team:
        return "UNK"
    
    raw_upper = raw_team.strip().upper()
    
    # Already abbreviated (2-5 uppercase letters with no spaces)
    if re.match(r'^[A-Z]{2,5}$', raw_upper):
        return raw_upper
    
    # Try using CBBStatsCache normalization
    try:
        from sports.cbb.ingest.cbb_data_provider import CBBStatsCache
        cache = CBBStatsCache()
        normalized = cache._normalize_team(raw_team)
        if normalized and normalized != "UNK":
            return normalized
    except Exception:
        pass
    
    # Fallback: take first word (e.g., "Miami Hurricanes" → "MIAMI")
    first_word = raw_upper.split()[0] if raw_upper.split() else raw_upper
    return first_word[:5]  # Cap at 5 chars for consistency
    
    return name.strip()


def parse_lines(lines: List[str]) -> List[Dict]:
    """
    Parse list of lines from Underdog CBB paste into prop dictionaries.
    """
    plays: List[Dict] = []
    current_player: Optional[str] = None
    current_team: Optional[str] = None
    current_game = None
    current_tags = {"goblin": False, "demon": False, "taco": False}
    expect_player_name = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if not line:
            continue

        low = line.lower()
        if low in {"trending", "goblin", "demon", "demons & goblins indicate non-standard payouts. learn more"}:
            continue
        if re.match(r"^\d+(?:\.\d+)?k$", low):
            continue
        
        # Player marker
        if "athlete or team avatar" in low:
            expect_player_name = True
            continue
        
        # Player name (right after marker)
        if expect_player_name:
            m = _TAG_SUFFIX_RE.search(line)
            current_tags = {"goblin": False, "demon": False, "taco": False}
            if m:
                current_tags[m.group(1).lower()] = True
                line = _TAG_SUFFIX_RE.sub("", line).strip()

            current_player = sanitize_player_name(line)
            current_team = None
            current_game = None
            expect_player_name = False
            continue

        # Player name heuristic (no marker)
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if _TEAM_LINE_RE.match(next_line) and not re.search(r"\d", line):
            if low not in {"trending"}:
                m = _TAG_SUFFIX_RE.search(line)
                current_tags = {"goblin": False, "demon": False, "taco": False}
                if m:
                    current_tags[m.group(1).lower()] = True
                    line = _TAG_SUFFIX_RE.sub("", line).strip()

                if current_player != line:
                    current_player = sanitize_player_name(line)
                    current_team = None
                    current_game = None
                    continue

        # Team line (e.g., "DUKE - G")
        m_team = _TEAM_LINE_RE.match(line)
        if m_team:
            current_team = m_team.group(1).upper()
            continue
        
        # Matchup/opponent line - try multiple patterns (most specific first)
        # All extracted team names are normalized via normalize_team_name()
        
        # 1. Full matchup with team abbreviations: "DUKE @ UNC"
        m_full = _MATCHUP_FULL_RE.search(line)
        if m_full:
            current_team = normalize_team_name(m_full.group(1))
            current_game = {"opponent": normalize_team_name(m_full.group(2))}
            continue
        
        # 2. Full matchup with team names: "Miami Hurricanes @ Florida Gators"
        m_full_name = _MATCHUP_FULL_NAME_RE.search(line)
        if m_full_name:
            current_team = normalize_team_name(m_full_name.group(1))
            current_game = {"opponent": normalize_team_name(m_full_name.group(2))}
            continue
        
        # 3. Matchup in parentheses: "(MIA @ FLA)" or "(Miami @ Florida)"
        m_parens = _MATCHUP_PARENS_RE.search(line)
        if m_parens:
            current_team = normalize_team_name(m_parens.group(1))
            current_game = {"opponent": normalize_team_name(m_parens.group(2))}
            continue
        
        # 4. Slash-separated teams: "MIA/FLA" or "Miami/Florida"
        m_slash = _MATCHUP_SLASH_RE.search(line)
        if m_slash:
            current_team = normalize_team_name(m_slash.group(1))
            current_game = {"opponent": normalize_team_name(m_slash.group(2))}
            continue
        
        # 5. Partial matchup (opponent only): "vs UNC" or "@ FLA"
        m_mu = _MATCHUP_RE.search(line)
        if m_mu:
            current_game = {"opponent": normalize_team_name(m_mu.group(2))}
            continue
        
        # Stat line (number)
        stat_value = _parse_line_value(line)
        if stat_value is not None:
            if i + 1 < len(lines):
                stat_name = lines[i + 1].strip()
                stat_key = map_stat_name(stat_name)
                
                if not stat_key:
                    continue
                
                # Look for Higher/Lower
                has_higher = False
                has_lower = False
                
                for j in range(i + 2, min(i + 10, len(lines))):
                    check_line = lines[j].strip()
                    if 'Higher' in check_line or check_line.lower() == 'more':
                        has_higher = True
                    if 'Lower' in check_line or check_line.lower() == 'less':
                        has_lower = True
                    if _parse_line_value(check_line) is not None:
                        break
                
                if current_player and stat_key:
                    opponent = None
                    if current_game:
                        opponent = current_game.get("opponent")
                    
                    base = {
                        "player": current_player,
                        "team": current_team or "UNK",
                        "opponent": opponent or "UNK",
                        "stat": stat_key,
                        "line": stat_value,
                        "league": "CBB",  # CBB-specific
                        "sport": "cbb",   # For routing
                        **({"goblin": True} if current_tags.get("goblin") else {}),
                        **({"demon": True} if current_tags.get("demon") else {}),
                        **({"taco": True} if current_tags.get("taco") else {}),
                    }
                    
                    # Only add both directions if NEITHER was explicitly detected
                    # This happens with raw pastes that don't include Higher/Lower buttons
                    if has_higher and has_lower:
                        # Both detected = store both (user pasted full block)
                        plays.append({**base, "direction": "higher"})
                        plays.append({**base, "direction": "lower"})
                    elif has_higher:
                        plays.append({**base, "direction": "higher"})
                    elif has_lower:
                        plays.append({**base, "direction": "lower"})
                    else:
                        # Neither detected = store both for pipeline analysis
                        plays.append({**base, "direction": "higher"})
                        plays.append({**base, "direction": "lower"})

                    current_tags = {"goblin": False, "demon": False, "taco": False}
    
    return plays


def parse_text(text: str) -> List[Dict]:
    """Parse raw text blob into props."""
    raw = (text or "")
    lines = raw.strip().split("\n") if raw.strip() else []
    plays = parse_lines(lines)
    if plays:
        return plays
    # Fallback: accept compact one-line formats (helps Quick Analyze)
    return parse_compact_lines(lines)


def parse_compact_lines(lines: List[str]) -> List[Dict]:
    """Parse simplified one-line inputs.

    Supported examples:
      - "Otega Oweh points lower 18.5"
      - "Denzel Aberdeen 3pm higher 1.5"
      - "Cooper Flagg (Duke) rebounds higher 7.5"

    Team is optional; when missing we keep team='UNK'. When provided as a
    full school name (e.g., 'Kentucky'), downstream ESPN search can still
    resolve it.
    """
    plays: List[Dict] = []
    for line in lines:
        s = (line or "").strip()
        if not s:
            continue

        m = _COMPACT_LINE_RE.match(s)
        if not m:
            continue

        player = (m.group("player") or "").strip()
        team = (m.group("team_paren") or "").strip()
        stat_raw = (m.group("stat") or "").strip()
        direction_raw = (m.group("direction") or "").strip().lower()
        line_raw = (m.group("line") or "").strip()

        # Normalize direction
        direction = "higher" if direction_raw in {"higher", "over", "more"} else "lower"

        # Normalize stat
        stat_key = map_stat_name(stat_raw)
        if not stat_key:
            continue

        try:
            line_val = float(line_raw)
        except ValueError:
            continue

        plays.append(
            {
                "player": player,
                "team": team or "UNK",
                "opponent": "UNK",
                "stat": stat_key,
                "line": line_val,
                "direction": direction,
                "league": "CBB",
                "sport": "cbb",
            }
        )

    return plays


def save_slate(props: List[Dict], output_dir: Path = None, filename_prefix: str = "cbb_slate") -> Path:
    """Save parsed slate to JSON file with timestamp.
    
    Args:
        props: List of prop dicts
        output_dir: Directory to save to (must be a directory, NOT a file path)
        filename_prefix: Prefix for the timestamped file (e.g. 'cbb_slate_oddsapi')
    """
    if output_dir is None:
        output_dir = Path("sports/cbb/inputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{filename_prefix}_{timestamp}.json"
    
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "count": len(props),
            "props": props
        }, f, indent=2)
    
    # Also save as latest
    latest_path = output_dir / "cbb_slate_latest.json"
    with open(latest_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "count": len(props),
            "props": props
        }, f, indent=2)
    
    return output_path


def load_latest_slate(input_dir: Path = None) -> List[Dict]:
    """Load most recent slate."""
    if input_dir is None:
        input_dir = Path("sports/cbb/inputs")
    
    latest_path = input_dir / "cbb_slate_latest.json"
    if not latest_path.exists():
        return []
    
    with open(latest_path) as f:
        data = json.load(f)
    
    return data.get("props", [])


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("CBB SLATE PARSER - Paste Underdog CBB props")
    print("=" * 60)
    print("Ctrl+Z (Windows) or Ctrl+D (Unix) + Enter when done:\n")
    
    text = sys.stdin.read()
    props = parse_text(text)
    
    if props:
        output_path = save_slate(props)
        print(f"\n✅ Parsed {len(props)} CBB props")
        print(f"📁 Saved to: {output_path}")
        print("\nSample props:")
        for p in props[:5]:
            print(f"  {p['player']} ({p['team']}) - {p['stat']} {p['direction']} {p['line']}")
        if len(props) > 5:
            print(f"  ... and {len(props) - 5} more")
    else:
        print("\n❌ No props parsed. Check paste format.")
