"""
UNIVERSAL NHL PROP PARSER
==========================
Supports multiple platforms:
    - Underdog (standard format with tags)
    - Underdog (new format with odds multipliers)
    - PrizePicks (TOI and stat format)

Auto-detects format and normalizes to NHLProp dataclass.

Author: Risk-First Quant Engine
Version: 2.1.0
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class UniversalProp:
    """Normalized prop from any platform."""
    player: str
    team: str
    position: str  # F, D, G, or UNK
    opponent: str
    game_time: str
    stat: str  # SOG, Goals, Points, Assists, TOI, etc.
    line: float
    direction: str  # More/Less or Over/Under → normalized to "More"/"Less"
    
    # Platform-specific
    source: str = "UNKNOWN"  # UNDERDOG, PRIZEPICKS
    odds_higher: Optional[float] = None  # e.g., 0.88x
    odds_lower: Optional[float] = None   # e.g., 1.02x
    trending: Optional[int] = None
    tag: Optional[str] = None  # Demon, Goblin, etc.
    
    # Analysis fields (filled later)
    model_prob: Optional[float] = None
    implied_prob: float = 0.50
    edge: Optional[float] = None
    tier: str = "PENDING"
    pick_state: str = "PENDING"
    risk_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "player": self.player,
            "team": self.team,
            "position": self.position,
            "opponent": self.opponent,
            "game_time": self.game_time,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "source": self.source,
            "odds_higher": self.odds_higher,
            "odds_lower": self.odds_lower,
            "tag": self.tag,
            "model_prob": self.model_prob,
            "edge": self.edge,
            "tier": self.tier,
        }


# ═══════════════════════════════════════════════════════════════
# STAT NORMALIZATION
# ═══════════════════════════════════════════════════════════════

STAT_ALIASES = {
    # SOG variations
    "shots on goal": "SOG",
    "sog": "SOG",
    "shots": "SOG",
    "1st period shots on goal": "1P_SOG",
    "1st period sog": "1P_SOG",
    
    # Goals
    "goals": "Goals",
    "goal": "Goals",
    "first goal scorer": "FGS",
    "1st goal scorer": "FGS",
    "anytime goal scorer": "AGS",
    
    # Points/Assists
    "points": "Points",
    "assists": "Assists",
    "assist": "Assists",
    "power play points": "PPP",
    "powerplay points": "PPP",
    "pp points": "PPP",
    "goals + assists": "Points",  # Same as points
    
    # Time on Ice
    "time on ice": "TOI",
    "toi": "TOI",
    
    # Plus/Minus
    "plus minus": "PM",
    "plus/minus": "PM",
    "+/-": "PM",
    "plus-minus": "PM",
    
    # Other
    "blocked shots": "Blocked Shots",
    "blocks": "Blocked Shots",
    "hits": "Hits",
    "hit": "Hits",
    "faceoffs won": "FOW",
    "faceoff wins": "FOW",
    "faceoffs": "FOW",
    "fo wins": "FOW",
    "fantasy points": "FPTS",
    "saves": "Saves",
    "goalie saves": "Saves",
    "save": "Saves",
    
    # Game props
    "total goals": "Total Goals",
    "game total": "Total Goals",
}

def normalize_stat(stat: str) -> str:
    """Normalize stat name to standard format."""
    stat_lower = stat.strip().lower()
    return STAT_ALIASES.get(stat_lower, stat.strip())


def normalize_direction(direction: str) -> str:
    """Normalize direction to More/Less."""
    d = direction.strip().lower()
    if d in ("more", "higher", "over", "o"):
        return "More"
    elif d in ("less", "lower", "under", "u", "fewer"):
        return "Less"
    return direction


# ═══════════════════════════════════════════════════════════════
# TEAM MAPPINGS
# ═══════════════════════════════════════════════════════════════

TEAM_ALIASES = {
    "ANA": "ANA", "ARI": "UTA", "BOS": "BOS", "BUF": "BUF",
    "CGY": "CGY", "CAR": "CAR", "CHI": "CHI", "COL": "COL",
    "CBJ": "CBJ", "DAL": "DAL", "DET": "DET", "EDM": "EDM",
    "FLA": "FLA", "LA": "LA", "LAK": "LA", "MIN": "MIN",
    "MTL": "MTL", "MON": "MTL", "NSH": "NSH", "NJ": "NJ",
    "NJD": "NJ", "NYI": "NYI", "NYR": "NYR", "OTT": "OTT",
    "PHI": "PHI", "PIT": "PIT", "SJ": "SJ", "SJS": "SJ",
    "SEA": "SEA", "STL": "STL", "TB": "TB", "TBL": "TB",
    "TOR": "TOR", "UTA": "UTA", "VAN": "VAN", "VGK": "VGK",
    "WSH": "WSH", "WAS": "WSH", "WPG": "WPG", "WIN": "WPG",
}

def normalize_team(team: str) -> str:
    """Normalize team abbreviation."""
    return TEAM_ALIASES.get(team.upper().strip(), team.upper().strip())


# ═══════════════════════════════════════════════════════════════
# FORMAT DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_format(text: str) -> str:
    """Detect which platform format the text is in."""
    lines = text.strip().split('\n')
    
    # Check for Underdog odds format (has multipliers like 0.88x)
    if re.search(r'\d+\.\d+x', text):
        return "UNDERDOG_ODDS"
    
    # Check for PrizePicks TOI format
    if "Time On Ice" in text or "time on ice" in text.lower():
        return "PRIZEPICKS"
    
    # Check for standard Underdog format (has Demon/Goblin tags)
    if re.search(r'(Demon|Goblin|Fire|Ice)\n', text):
        return "UNDERDOG_STANDARD"
    
    # Check for team - position format
    if re.search(r'[A-Z]{2,3}\s*-\s*[FDG]', text):
        return "UNDERDOG_STANDARD"
    
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# UNDERDOG ODDS FORMAT PARSER
# ═══════════════════════════════════════════════════════════════

def parse_underdog_odds(text: str) -> List[UniversalProp]:
    """
    Parse Underdog format with odds multipliers.
    
    Example:
        Macklin Celebrini
        SJ @ CHI - 7:30PM CST
        
        3.5
        Shots on Goal
        Higher
        0.88x
        Lower
        1.02x
    """
    props = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    i = 0
    current_player = None
    current_team = None
    current_opponent = None
    current_game_time = None
    
    while i < len(lines):
        line = lines[i]
        
        # Skip navigation/UI elements
        if line in ("Fewer picks", "athlete or team avatar", "Trending"):
            i += 1
            continue
        
        # Detect game info line: "SJ @ CHI - 7:30PM CST"
        game_match = re.match(r'^([A-Z]{2,3})\s*[@vs]+\s*([A-Z]{2,3})\s*-?\s*(.+)$', line, re.IGNORECASE)
        if game_match:
            team1 = normalize_team(game_match.group(1))
            team2 = normalize_team(game_match.group(2))
            game_time = game_match.group(3).strip()
            
            # Previous line is ALWAYS the player name for this format
            if i > 0:
                prev_line = lines[i-1].strip()
                # Only update if it looks like a player name (no numbers, not a stat)
                if not re.search(r'\d', prev_line) and prev_line.lower() not in STAT_ALIASES:
                    current_player = prev_line
                
            # Determine home/away (@ means first team is away)
            if "@" in line:
                current_team = team1
                current_opponent = team2
            else:
                current_team = team1
                current_opponent = team2
            current_game_time = game_time
            i += 1
            continue
        
        # Detect player name (starts prop sequence)
        # Player name: typically 2-3 words, no numbers
        name_match = re.match(r'^([A-Za-z\'\-\.\s]+)$', line)
        if name_match and not re.search(r'\d', line) and len(line) > 3:
            # Check if this looks like a stat name
            if line.lower() not in STAT_ALIASES and not any(s in line.lower() for s in ["higher", "lower", "more", "less"]):
                current_player = line.strip()
                i += 1
                continue
        
        # Detect line + stat + direction + odds sequence
        # Line is a number (e.g., 3.5)
        line_match = re.match(r'^(\d+\.?\d*)$', line)
        if line_match and current_player:
            try:
                prop_line = float(line_match.group(1))
                
                # Next line should be stat
                if i + 1 < len(lines):
                    stat_line = lines[i + 1]
                    stat = normalize_stat(stat_line)
                    
                    # Look for Higher/Lower and odds
                    j = i + 2
                    directions_found = []  # Track both directions
                    odds_higher = None
                    odds_lower = None
                    
                    while j < len(lines) and j < i + 10:
                        check_line = lines[j].strip()
                        
                        # Direction
                        if check_line.lower() in ("higher", "more"):
                            if "More" not in directions_found:
                                directions_found.append("More")
                        elif check_line.lower() in ("lower", "less", "fewer"):
                            if "Less" not in directions_found:
                                directions_found.append("Less")
                        
                        # Odds multiplier (e.g., 0.88x)
                        odds_match = re.match(r'^(\d+\.?\d*)x$', check_line)
                        if odds_match:
                            odds_val = float(odds_match.group(1))
                            # Determine which direction this odds is for
                            if j > 0 and lines[j-1].strip().lower() in ("higher", "more"):
                                odds_higher = odds_val
                            elif j > 0 and lines[j-1].strip().lower() in ("lower", "less"):
                                odds_lower = odds_val
                        
                        # Stop at next line number or new player
                        if re.match(r'^\d+\.?\d*$', check_line) and check_line != str(prop_line):
                            break
                        if re.match(r'^[A-Z]{2,3}\s*[@vs]', check_line, re.IGNORECASE):
                            break
                            
                        j += 1
                    
                    # Create props for EACH direction found
                    for direction in directions_found:
                        prop = UniversalProp(
                            player=current_player,
                            team=current_team or "UNK",
                            position="F",  # Default, will be enriched later
                            opponent=current_opponent or "UNK",
                            game_time=current_game_time or "",
                            stat=stat,
                            line=prop_line,
                            direction=direction,
                            source="UNDERDOG",
                            odds_higher=odds_higher,
                            odds_lower=odds_lower,
                        )
                        props.append(prop)
                    
                    i = j
                    continue
                    
            except (ValueError, IndexError):
                pass
        
        i += 1
    
    return props


# ═══════════════════════════════════════════════════════════════
# PRIZEPICKS FORMAT PARSER
# ═══════════════════════════════════════════════════════════════

def parse_prizepicks(text: str) -> List[UniversalProp]:
    """
    Parse PrizePicks format.
    
    Example:
        Tim Stutzle
        OTT - F
        Tim Stutzle
        @ PIT Mon 6:00pm
        20.25
        Time On Ice
        Less
        More
    """
    props = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip trending numbers and navigation
        if line.isdigit() or line == "Trending":
            i += 1
            continue
        
        # Detect team - position line: "OTT - F"
        team_pos_match = re.match(r'^([A-Z]{2,3})\s*-\s*([FDG])$', line)
        if team_pos_match and i > 0:
            team = normalize_team(team_pos_match.group(1))
            position = team_pos_match.group(2)
            player = lines[i - 1].strip()
            
            # Remove any tag suffix from player name
            for tag in ["Demon", "Goblin", "Fire", "Ice"]:
                if player.endswith(tag):
                    player = player[:-len(tag)].strip()
            
            # Look for game info and props
            j = i + 1
            opponent = "UNK"
            game_time = ""
            
            # Skip duplicate player name
            if j < len(lines) and lines[j].strip() == player:
                j += 1
            
            # Get game info: "@ PIT Mon 6:00pm" or "vs STL Mon 7:08pm"
            if j < len(lines):
                game_match = re.match(r'^[@vs]+\s*([A-Z]{2,3})\s+(.+)$', lines[j], re.IGNORECASE)
                if game_match:
                    opponent = normalize_team(game_match.group(1))
                    game_time = game_match.group(2).strip()
                    j += 1
            
            # Now parse stat lines until we hit another player
            while j < len(lines):
                check_line = lines[j].strip()
                
                # Check for line number
                line_match = re.match(r'^(\d+\.?\d*)$', check_line)
                if line_match:
                    prop_line = float(line_match.group(1))
                    
                    # Next should be stat
                    if j + 1 < len(lines):
                        stat = normalize_stat(lines[j + 1])
                        
                        # Look for directions
                        k = j + 2
                        directions_found = []
                        while k < len(lines) and k < j + 5:
                            dir_line = lines[k].strip().lower()
                            if dir_line in ("less", "lower", "under"):
                                directions_found.append("Less")
                            elif dir_line in ("more", "higher", "over"):
                                directions_found.append("More")
                            elif re.match(r'^\d+\.?\d*$', lines[k].strip()):
                                break  # Next line number
                            elif re.match(r'^[A-Z]{2,3}\s*-\s*[FDG]$', lines[k].strip()):
                                break  # Next player
                            k += 1
                        
                        # Create prop for each direction
                        for direction in directions_found:
                            prop = UniversalProp(
                                player=player,
                                team=team,
                                position=position,
                                opponent=opponent,
                                game_time=game_time,
                                stat=stat,
                                line=prop_line,
                                direction=direction,
                                source="PRIZEPICKS",
                            )
                            props.append(prop)
                        
                        j = k
                        continue
                
                # Check if we've hit another player (team - position line)
                if re.match(r'^[A-Z]{2,3}\s*-\s*[FDG]$', check_line):
                    break
                
                j += 1
            
            i = j
            continue
        
        i += 1
    
    return props


# ═══════════════════════════════════════════════════════════════
# UNDERDOG STANDARD FORMAT PARSER
# ═══════════════════════════════════════════════════════════════

def parse_underdog_standard(text: str) -> List[UniversalProp]:
    """
    Parse standard Underdog format with tags.
    
    Example:
        Jonathan MarchessaultDemon
        NSH - F
        Jonathan Marchessault
        vs STL Mon 7:08pm
        2.5
        SOG
        More
        Trending
        748
    """
    props = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip navigation
        if line == "Trending" or line.isdigit():
            i += 1
            continue
        
        # Detect player name (possibly with tag)
        tag = None
        player_name = line
        for t in ["Demon", "Goblin", "Fire", "Ice"]:
            if line.endswith(t):
                tag = t
                player_name = line[:-len(t)].strip()
                break
        
        # Next line should be team - position
        if i + 1 >= len(lines):
            i += 1
            continue
        
        team_pos_match = re.match(r'^([A-Z]{2,3})\s*-\s*([FDG])$', lines[i + 1])
        if not team_pos_match:
            i += 1
            continue
        
        team = normalize_team(team_pos_match.group(1))
        position = team_pos_match.group(2)
        
        # Skip duplicate player name
        j = i + 2
        if j < len(lines) and lines[j].strip() == player_name:
            j += 1
        
        # Get game info
        opponent = "UNK"
        game_time = ""
        if j < len(lines):
            game_match = re.match(r'^(vs|@)\s*([A-Z]{2,3})\s+(.+)$', lines[j], re.IGNORECASE)
            if game_match:
                opponent = normalize_team(game_match.group(2))
                game_time = game_match.group(3).strip()
                j += 1
        
        # Parse props
        while j < len(lines):
            check_line = lines[j].strip()
            
            # Line number
            line_match = re.match(r'^(\d+\.?\d*)$', check_line)
            if line_match:
                prop_line = float(line_match.group(1))
                
                # Stat
                if j + 1 < len(lines):
                    stat = normalize_stat(lines[j + 1])
                    
                    # Direction
                    k = j + 2
                    direction = None
                    trending = None
                    
                    while k < len(lines) and k < j + 6:
                        dir_line = lines[k].strip()
                        
                        if dir_line.lower() in ("more", "higher"):
                            direction = "More"
                        elif dir_line.lower() in ("less", "lower"):
                            direction = "Less"
                        elif dir_line == "Trending" and k + 1 < len(lines):
                            try:
                                trending = int(lines[k + 1].replace(",", ""))
                            except:
                                pass
                        elif re.match(r'^\d+\.?\d*$', dir_line) and dir_line != str(prop_line):
                            break
                        elif re.match(r'^[A-Z]{2,3}\s*-\s*[FDG]$', dir_line):
                            break
                        
                        k += 1
                    
                    if direction:
                        prop = UniversalProp(
                            player=player_name,
                            team=team,
                            position=position,
                            opponent=opponent,
                            game_time=game_time,
                            stat=stat,
                            line=prop_line,
                            direction=direction,
                            source="UNDERDOG",
                            tag=tag,
                            trending=trending,
                        )
                        props.append(prop)
                    
                    j = k
                    continue
            
            # Next player - detected by team-pos line (means PREVIOUS line is new player)
            if re.match(r'^[A-Z]{2,3}\s*-\s*[FDG]$', check_line):
                # Go back one line to point to the player name
                i = j - 1
                break
            
            # New player with tag - point to this line for reparse
            has_tag = any(check_line.endswith(t) for t in ["Demon", "Goblin", "Fire", "Ice"])
            if has_tag:
                i = j  # Point to this new player
                break
            
            j += 1
        else:
            # Reached end of lines without breaking
            i = j if j > i else i + 1
    
    return props


# ═══════════════════════════════════════════════════════════════
# UNIVERSAL PARSER
# ═══════════════════════════════════════════════════════════════

def parse_universal(text: str) -> Tuple[List[UniversalProp], Dict]:
    """
    Universal parser that auto-detects format and parses props.
    
    Returns:
        Tuple of (props list, metadata dict)
    """
    # Split input in case user pasted multiple formats
    # Try to detect sections
    
    all_props = []
    metadata = {
        "formats_detected": [],
        "total_parsed": 0,
        "underdog_count": 0,
        "prizepicks_count": 0,
        "stats_breakdown": {},
    }
    
    # Detect primary format
    fmt = detect_format(text)
    metadata["formats_detected"].append(fmt)
    
    if fmt == "UNDERDOG_ODDS":
        props = parse_underdog_odds(text)
        all_props.extend(props)
        metadata["underdog_count"] += len(props)
        
    elif fmt == "PRIZEPICKS":
        props = parse_prizepicks(text)
        all_props.extend(props)
        metadata["prizepicks_count"] += len(props)
        
    elif fmt == "UNDERDOG_STANDARD":
        props = parse_underdog_standard(text)
        all_props.extend(props)
        metadata["underdog_count"] += len(props)
        
    else:
        # Try all parsers
        props1 = parse_underdog_standard(text)
        props2 = parse_prizepicks(text)
        props3 = parse_underdog_odds(text)
        
        # Use whichever got the most results
        all_results = [(props1, "UNDERDOG_STANDARD"), (props2, "PRIZEPICKS"), (props3, "UNDERDOG_ODDS")]
        all_results.sort(key=lambda x: len(x[0]), reverse=True)
        
        if all_results[0][0]:
            all_props = all_results[0][0]
            metadata["formats_detected"] = [all_results[0][1]]
    
    # Deduplicate
    seen = set()
    unique_props = []
    for prop in all_props:
        key = (prop.player.lower(), prop.stat, prop.line, prop.direction)
        if key not in seen:
            seen.add(key)
            unique_props.append(prop)
    
    # Update metadata
    metadata["total_parsed"] = len(unique_props)
    for prop in unique_props:
        stat = prop.stat
        metadata["stats_breakdown"][stat] = metadata["stats_breakdown"].get(stat, 0) + 1
    
    return unique_props, metadata


def deduplicate_props(props: List[UniversalProp]) -> List[UniversalProp]:
    """Remove duplicate props keeping first occurrence."""
    seen = set()
    unique = []
    for prop in props:
        key = (prop.player.lower(), prop.stat, prop.line, prop.direction)
        if key not in seen:
            seen.add(key)
            unique.append(prop)
    return unique


# ═══════════════════════════════════════════════════════════════
# CONVERSION TO NHL MENU FORMAT
# ═══════════════════════════════════════════════════════════════

def convert_to_nhl_prop(uprop: UniversalProp):
    """Convert UniversalProp to NHLProp for menu compatibility."""
    from sports.nhl.nhl_menu import NHLProp
    
    return NHLProp(
        player=uprop.player,
        team=uprop.team,
        position=uprop.position,
        opponent=uprop.opponent,
        game_time=uprop.game_time,
        stat=uprop.stat,
        line=uprop.line,
        direction=uprop.direction,
        trending=uprop.trending,
        tag=uprop.tag,
    )


def convert_all_to_nhl_props(uprops: List[UniversalProp]) -> List:
    """Convert list of UniversalProps to NHLProps."""
    return [convert_to_nhl_prop(up) for up in uprops]


# ═══════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test with sample data
    test_underdog_odds = """
Macklin Celebrini
SJ @ CHI - 7:30PM CST

3.5
Shots on Goal
Higher
0.88x
Lower
1.02x

1.5
Points
Higher
1.09x
Lower
0.79x
"""
    
    test_prizepicks = """
Tim Stutzle
OTT - F
Tim Stutzle
@ PIT Mon 6:00pm
20.25
Time On Ice
Less
More

Sidney Crosby
PIT - F
Sidney Crosby
vs OTT Mon 6:00pm
19.75
Time On Ice
Less
More
"""
    
    test_underdog_standard = """
Jonathan MarchessaultDemon
NSH - F
Jonathan Marchessault
vs STL Mon 7:08pm
2.5
SOG
More
Trending
748

Brady TkachukGoblin
OTT - F
Brady Tkachuk
@ PIT Mon 6:08pm
2.5
SOG
More
"""
    
    print("=" * 60)
    print("  UNIVERSAL NHL PARSER - TEST")
    print("=" * 60)
    
    # Test Underdog Odds
    print("\n[TEST 1] Underdog Odds Format:")
    props, meta = parse_universal(test_underdog_odds)
    print(f"  Detected: {meta['formats_detected']}")
    print(f"  Parsed: {len(props)} props")
    for p in props[:3]:
        print(f"    - {p.player}: {p.stat} {p.direction} {p.line}")
    
    # Test PrizePicks
    print("\n[TEST 2] PrizePicks Format:")
    props, meta = parse_universal(test_prizepicks)
    print(f"  Detected: {meta['formats_detected']}")
    print(f"  Parsed: {len(props)} props")
    for p in props[:3]:
        print(f"    - {p.player}: {p.stat} {p.direction} {p.line}")
    
    # Test Underdog Standard
    print("\n[TEST 3] Underdog Standard Format:")
    props, meta = parse_universal(test_underdog_standard)
    print(f"  Detected: {meta['formats_detected']}")
    print(f"  Parsed: {len(props)} props")
    for p in props[:3]:
        print(f"    - {p.player}: {p.stat} {p.direction} {p.line} [{p.tag}]")
    
    print("\n" + "=" * 60)
    print("  All tests complete!")
    print("=" * 60)
