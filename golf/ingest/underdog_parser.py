"""
Underdog Golf Slate Parser
==========================
Parse pasted text from Underdog Fantasy golf props.

Handles format:
    athlete or team avatar
    Hideki Matsuyama
    Farmers Insura... R2 - 11:32AM CST

    71.5
    Round Strokes

    Higher
    1.04x

    Lower
    0.87x

    20.5
    Tourney Finishing Position

    Better
    0.67x
    
    3.5
    Birdies or Better

    Higher
    0.83x

    Lower
    1.08x
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json


# Market type mappings
MARKET_MAPPINGS = {
    "round strokes": "round_strokes",
    "total strokes": "round_strokes",
    "strokes": "round_strokes",
    "r1 strokes": "round_strokes",
    "r2 strokes": "round_strokes",
    "r3 strokes": "round_strokes",
    "r4 strokes": "round_strokes",
    "tourney finishing position": "finishing_position",
    "tournament finishing position": "finishing_position",
    "finishing position": "finishing_position",
    "finish position": "finishing_position",
    "birdies or better matchup": "birdies_or_better_matchup",  # MATCHUP market
    "birdies or better": "birdies",
    "birdies": "birdies",
    "bogeys": "bogeys",
    "pars": "pars",
    "eagles": "eagles",
}


def parse_underdog_golf_slate(text: str) -> List[Dict]:
    """
    Parse Underdog Fantasy golf slate from pasted text.
    
    Args:
        text: Raw pasted text from Underdog
        
    Returns:
        List of parsed prop dicts
    """
    props = []
    lines = [l.strip() for l in text.strip().split("\n")]
    
    current_player = None
    current_tournament = None
    current_round = None
    current_tee_time = None
    current_opponent = None  # For matchup props
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip empty lines and avatars
        if not line or line.lower() == "athlete or team avatar":
            i += 1
            continue
        
        # Check if this is a player name line
        # Player names don't have numbers at start and aren't market types
        if is_player_name(line, lines, i):
            current_player = clean_player_name(line)
            current_opponent = None  # Reset opponent
            
            # Next line should be tournament info
            if i + 1 < len(lines):
                tournament_info = lines[i + 1]
                current_tournament, current_round, current_tee_time, current_opponent = parse_tournament_info(tournament_info)
                i += 2
                continue
        
        # Check if this is a prop line (starts with number)
        if is_prop_line(line):
            prop_value = parse_prop_value(line)
            
            # Next line should be market type
            if i + 1 < len(lines):
                market_line = lines[i + 1]
                market = parse_market_type(market_line)
                
                if market and current_player:
                    prop = {
                        "player": current_player,
                        "tournament": current_tournament or "Unknown Tournament",
                        "round": current_round or 0,
                        "tee_time": current_tee_time or "",
                        "market": market,
                        "line": prop_value,
                    }
                    
                    # Add opponent for matchup markets
                    if current_opponent and "matchup" in market.lower():
                        prop["opponent"] = current_opponent
                        prop["market"] = "matchup"  # Normalize to matchup
                    
                    # Look for multipliers
                    j = i + 2
                    while j < len(lines) and j < i + 8:  # Look ahead up to 6 lines
                        mult_line = lines[j].strip().lower()
                        
                        if mult_line == "higher":
                            if j + 1 < len(lines):
                                mult = parse_multiplier(lines[j + 1])
                                if mult:
                                    prop["higher_mult"] = mult
                                j += 2
                                continue
                        
                        elif mult_line == "lower":
                            if j + 1 < len(lines):
                                mult = parse_multiplier(lines[j + 1])
                                if mult:
                                    prop["lower_mult"] = mult
                                j += 2
                                continue
                        
                        elif mult_line == "better":
                            if j + 1 < len(lines):
                                mult = parse_multiplier(lines[j + 1])
                                if mult:
                                    prop["better_mult"] = mult
                                j += 2
                                continue
                        
                        # Check if we hit a new prop or player
                        if is_prop_line(lines[j]) or is_player_name(lines[j], lines, j):
                            break
                        
                        j += 1
                    
                    props.append(prop)
                    i = j
                    continue
        
        i += 1
    
    return props


def is_player_name(line: str, all_lines: List[str], idx: int) -> bool:
    """Check if line is likely a player name."""
    line_lower = line.lower()
    
    # Reject if it starts with a number (prop value)
    if re.match(r"^\d", line):
        return False
    
    # Reject "-G" suffix lines (Underdog UI artifact)
    if line.endswith(" - G") or line.endswith("-G"):
        return False
    
    # Reject abbreviated names like "H.Matsuyama - G"
    if re.search(r"\.\w+\s*-\s*G$", line):
        return False
    
    # Reject if it's a known market type
    for market in MARKET_MAPPINGS.keys():
        if market in line_lower:
            return False
    
    # Reject if it's a direction
    if line_lower in ["higher", "lower", "better", "worse", "over", "under", "less", "more", "trending"]:
        return False
    
    # Reject if it's a multiplier
    if "x" in line_lower and re.match(r"[\d.]+x", line_lower):
        return False
    
    # Reject if it's just a number followed by K (e.g. "2.6K")
    if re.match(r"^[\d.]+K?$", line, re.I):
        return False
    
    # Player names typically have 2+ words or are single capitalized names
    words = line.split()
    if len(words) >= 2:
        return True
    
    # Single word that looks like a name (capitalized, no numbers)
    if len(words) == 1 and line[0].isupper() and not any(c.isdigit() for c in line):
        # Check if next line looks like tournament info
        if idx + 1 < len(all_lines):
            next_line = all_lines[idx + 1].lower()
            if any(x in next_line for x in ["r1", "r2", "r3", "r4", "rd", "am", "pm", "cst", "est", "pst", "vs "]):
                return True
    
    return False


def clean_player_name(name: str) -> str:
    """Clean and normalize player name."""
    # Remove common artifacts
    name = re.sub(r"athlete or team avatar\s*", "", name, flags=re.I)
    name = name.strip()
    
    # Title case
    return name.title()


def parse_tournament_info(line: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """
    Parse tournament info line.
    
    Examples:
    - "Farmers Insura... R2 - 11:32AM CST"
    - "vs Austin Eckroat Sun 10:09am"  (MATCHUP)
    - "vs Torrey Pines - South RD 4 Sun 11:37am"  (Course matchup - treat as regular)
    
    Returns:
        (tournament_name, round_number, tee_time, opponent_name)
    """
    tournament = None
    round_num = None
    tee_time = None
    opponent = None
    
    # Check if this is a matchup (vs PLAYER not vs COURSE)
    line_lower = line.lower()
    if line_lower.startswith("vs "):
        # Extract opponent from "vs NAME TIME"
        vs_match = re.match(r"vs\s+(.+?)\s+(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat|\d{1,2}:)", line, re.I)
        if vs_match:
            potential_opponent = vs_match.group(1).strip()
            # Check if it's a course name (contains "Pines", "National", "Club", "CC", etc.)
            course_indicators = ["pines", "national", "club", "country", "golf", "resort", 
                               "links", "beach", "hills", "south", "north", "east", "west"]
            is_course = any(ind in potential_opponent.lower() for ind in course_indicators)
            
            if not is_course:
                # This is a player matchup
                opponent = potential_opponent.title()
                tournament = "Matchup"
                
                # Extract tee time
                time_match = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)", line, re.I)
                if time_match:
                    tee_time = time_match.group(1)
                
                return tournament, round_num, tee_time, opponent
    
    # Regular tournament info parsing
    # Extract round number (R2, RD 4, Round 3, etc.)
    round_match = re.search(r"R(?:D|ound)?\s*(\d)", line, re.I)
    if round_match:
        round_num = int(round_match.group(1))
    
    # Extract tee time
    time_match = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)", line, re.I)
    if time_match:
        tee_time = time_match.group(1)
    
    # Get tournament name (before R# or time)
    # Handle "vs COURSE" format
    if line_lower.startswith("vs "):
        line = line[3:]  # Remove "vs "
    
    parts = re.split(r"\s+R(?:D)?\s*\d|\s+\d{1,2}:", line, flags=re.I)
    if parts:
        tournament = parts[0].strip()
        # Clean up truncation
        tournament = tournament.rstrip(".")
        
        # Expand common abbreviations
        expansions = {
            "Farmers Insura": "Farmers Insurance Open",
            "AT&T Pebble": "AT&T Pebble Beach Pro-Am",
            "WM Phoenix": "WM Phoenix Open",
            "Arnold Palmer": "Arnold Palmer Invitational",
            "Genesis Invit": "Genesis Invitational",
            "Torrey Pines": "Farmers Insurance Open",
            "Torrey Pines - South": "Farmers Insurance Open",
        }
        for abbrev, full in expansions.items():
            if abbrev.lower() in tournament.lower():
                tournament = full
                break
    
    return tournament, round_num, tee_time, opponent


def is_prop_line(line: str) -> bool:
    """Check if line is a prop value (number)."""
    try:
        float(line.replace(",", ""))
        return True
    except ValueError:
        return False


def parse_prop_value(line: str) -> float:
    """Parse prop value from line."""
    try:
        return float(line.replace(",", ""))
    except ValueError:
        return 0.0


def parse_market_type(line: str) -> Optional[str]:
    """Parse market type from line."""
    line_lower = line.lower().strip()
    
    for key, market in MARKET_MAPPINGS.items():
        if key in line_lower:
            return market
    
    return None


def parse_multiplier(line: str) -> Optional[float]:
    """Parse multiplier value (e.g., '1.04x')."""
    match = re.search(r"([\d.]+)x", line.lower())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def load_slate_from_file(file_path: Path) -> List[Dict]:
    """Load slate from text file."""
    with open(file_path) as f:
        text = f.read()
    return parse_underdog_golf_slate(text)


def save_parsed_slate(props: List[Dict], output_path: Path):
    """Save parsed slate to JSON."""
    data = {
        "parsed_at": datetime.now().isoformat(),
        "prop_count": len(props),
        "props": props,
    }
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    return output_path


def display_parsed_props(props: List[Dict]):
    """Display parsed props in readable format."""
    print(f"\n{'='*60}")
    print(f"PARSED GOLF PROPS: {len(props)} props")
    print(f"{'='*60}")
    
    current_player = None
    for prop in props:
        if prop["player"] != current_player:
            current_player = prop["player"]
            print(f"\n⛳ {current_player}")
            print(f"   {prop.get('tournament', 'Unknown')} | Round {prop.get('round', '?')}")
            if prop.get("tee_time"):
                print(f"   Tee Time: {prop['tee_time']}")
        
        market = prop.get("market", "unknown")
        line = prop.get("line", 0)
        
        mults = []
        if prop.get("higher_mult"):
            mults.append(f"Higher: {prop['higher_mult']}x")
        if prop.get("lower_mult"):
            mults.append(f"Lower: {prop['lower_mult']}x")
        if prop.get("better_mult"):
            mults.append(f"Better: {prop['better_mult']}x")
        
        mult_str = " | ".join(mults) if mults else "No multipliers"
        
        print(f"   • {market.replace('_', ' ').title()}: {line} ({mult_str})")


# ============================================================================
# MAIN / TEST
# ============================================================================

if __name__ == "__main__":
    # Test with sample Underdog format
    sample_slate = """
athlete or team avatar
Hideki Matsuyama
Farmers Insura... R2 - 11:32AM CST

71.5
Round Strokes

Higher
1.04x

Lower
0.87x

20.5
Tourney Finishing Position

Better
0.67x
3.5
Birdies or Better

Higher
0.83x

Lower
1.08x
athlete or team avatar
Justin Rose
Farmers Insura... R2 - 11:32AM CST

71.5
Round Strokes

Higher

Lower

20.5
Tourney Finishing Position

Better
0.62x
3.5
Birdies or Better

Higher

Lower
athlete or team avatar
Si Woo Kim
Farmers Insura... R2 - 12:27PM CST

68.5
Round Strokes

Higher
1.03x

Lower
0.94x

20.5
Tourney Finishing Position

Better
0.72x
4.5
Birdies or Better

Higher
0.77x

Lower
1.06x
athlete or team avatar
Patrick Cantlay
Farmers Insura... R2 - 11:32AM CST

68.5
Round Strokes

Higher
1.03x

Lower
0.94x

20.5
Tourney Finishing Position

Better
1.32x
athlete or team avatar
Cameron Young
Farmers Insura... R2 - 11:32AM CST

68.5
Round Strokes

Higher
1.03x

Lower
0.88x

20.5
Tourney Finishing Position

Better
0.97x
5.5
Birdies or Better

Higher

Lower
"""
    
    props = parse_underdog_golf_slate(sample_slate)
    display_parsed_props(props)
    
    # Save to file
    output_dir = Path(__file__).parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"parsed_slate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_parsed_slate(props, output_file)
    print(f"\n✓ Saved to {output_file}")
