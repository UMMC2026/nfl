"""
Manual Golf Data Ingestion
==========================
Parse Underdog Fantasy slates and manual prop entry.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_underdog_slate(text: str) -> List[Dict]:
    """
    Parse Underdog Fantasy golf props from pasted text.
    
    Expected format variations:
    - "Scottie Scheffler Top 10 Finish Higher/Lower"
    - "Rory McIlroy vs Xander Schauffele (H2H Tournament)"
    - "Jon Rahm Make Cut Yes/No"
    - "Tiger Woods Round 1 Score O/U 71.5"
    
    Args:
        text: Raw pasted text from Underdog
        
    Returns:
        List of parsed prop dicts
    """
    props = []
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip headers/separators
        if any(x in line.lower() for x in ["underdog", "golf", "---", "===", "prop"]):
            i += 1
            continue
        
        prop = parse_single_prop_line(line)
        if prop:
            props.append(prop)
        
        i += 1
    
    return props


def parse_single_prop_line(line: str) -> Optional[Dict]:
    """Parse a single prop line into structured data."""
    
    line_lower = line.lower()
    
    # Head-to-head matchup
    if " vs " in line_lower or " v " in line_lower:
        return parse_h2h_prop(line)
    
    # Top X finish
    top_match = re.search(r"(.+?)\s+top\s*(\d+)\s+finish", line_lower)
    if top_match:
        return {
            "player": clean_player_name(top_match.group(1)),
            "market": f"top_{top_match.group(2)}",
            "line": int(top_match.group(2)),
            "direction": "higher",  # Higher = yes, finishes in top X
            "raw": line,
        }
    
    # Make/miss cut
    if "make cut" in line_lower or "made cut" in line_lower:
        player = re.sub(r"\s*(make|made)\s*cut.*", "", line, flags=re.I).strip()
        return {
            "player": clean_player_name(player),
            "market": "make_cut",
            "line": 0.5,
            "direction": "higher",
            "raw": line,
        }
    
    if "miss cut" in line_lower:
        player = re.sub(r"\s*miss\s*cut.*", "", line, flags=re.I).strip()
        return {
            "player": clean_player_name(player),
            "market": "miss_cut",
            "line": 0.5,
            "direction": "higher",
            "raw": line,
        }
    
    # Round score over/under
    round_match = re.search(
        r"(.+?)\s+round\s*(\d)\s+score\s+(?:o/?u|over/?under)?\s*([\d.]+)",
        line_lower
    )
    if round_match:
        return {
            "player": clean_player_name(round_match.group(1)),
            "market": f"round_{round_match.group(2)}_score",
            "line": float(round_match.group(3)),
            "direction": None,  # Needs direction from context
            "raw": line,
        }
    
    # Tournament total
    total_match = re.search(
        r"(.+?)\s+(?:tournament\s+)?total\s+(?:score\s+)?(?:o/?u|over/?under)?\s*([\d.]+)",
        line_lower
    )
    if total_match:
        return {
            "player": clean_player_name(total_match.group(1)),
            "market": "tournament_total",
            "line": float(total_match.group(2)),
            "direction": None,
            "raw": line,
        }
    
    # Birdies prop
    birdie_match = re.search(r"(.+?)\s+birdies\s+(?:o/?u)?\s*([\d.]+)", line_lower)
    if birdie_match:
        return {
            "player": clean_player_name(birdie_match.group(1)),
            "market": "birdies",
            "line": float(birdie_match.group(2)),
            "direction": None,
            "raw": line,
        }
    
    # Bogeys prop
    bogey_match = re.search(r"(.+?)\s+bogeys\s+(?:o/?u)?\s*([\d.]+)", line_lower)
    if bogey_match:
        return {
            "player": clean_player_name(bogey_match.group(1)),
            "market": "bogeys",
            "line": float(bogey_match.group(2)),
            "direction": None,
            "raw": line,
        }
    
    return None


def parse_h2h_prop(line: str) -> Dict:
    """Parse head-to-head matchup prop."""
    # "Scottie Scheffler vs Rory McIlroy (Tournament)"
    # "Scheffler v McIlroy Round 1"
    
    # Split on vs/v
    parts = re.split(r"\s+(?:vs?\.?|versus)\s+", line, flags=re.I)
    
    if len(parts) != 2:
        return {
            "market": "h2h_tournament",
            "raw": line,
            "parse_error": True,
        }
    
    player_1 = clean_player_name(parts[0])
    
    # Extract player 2 and round info
    player_2_part = parts[1]
    round_match = re.search(r"\(?round\s*(\d)\)?", player_2_part, re.I)
    
    if round_match:
        market = f"h2h_round_{round_match.group(1)}"
        player_2 = clean_player_name(re.sub(r"\(?round\s*\d\)?", "", player_2_part, flags=re.I))
    elif "tournament" in player_2_part.lower():
        market = "h2h_tournament"
        player_2 = clean_player_name(re.sub(r"\(?tournament\)?", "", player_2_part, flags=re.I))
    else:
        market = "h2h_tournament"
        player_2 = clean_player_name(player_2_part)
    
    return {
        "player": player_1,
        "opponent": player_2,
        "market": market,
        "direction": None,  # Pick side later
        "raw": line,
    }


def clean_player_name(name: str) -> str:
    """Clean and normalize player name."""
    # Remove common suffixes
    name = re.sub(r"\s*\(.*\)", "", name)  # Remove parentheticals
    name = re.sub(r"\s+$", "", name)       # Trailing whitespace
    name = re.sub(r"^\s+", "", name)       # Leading whitespace
    
    # Normalize common abbreviations
    name = re.sub(r"^jr\.?\s*", "", name, flags=re.I)
    
    # Title case
    return name.title()


def load_tournament_field(file_path: Path) -> List[Dict]:
    """
    Load tournament field from JSON file.
    
    Expected format:
    {
        "tournament": "The Masters",
        "course": "augusta_national",
        "date": "2026-04-10",
        "field": [
            {"player": "Scottie Scheffler", "world_rank": 1, "odds": 600},
            ...
        ]
    }
    """
    with open(file_path) as f:
        data = json.load(f)
    
    return data.get("field", [])


def load_weather_forecast(
    location: str,
    date_str: str,
    api_key: Optional[str] = None
) -> Dict:
    """
    Load weather forecast for tournament.
    
    Returns:
        {
            "temperature_f": int,
            "wind_mph": int,
            "wind_direction": str,
            "precipitation_pct": int,
            "conditions": str,  # "sunny", "cloudy", "rain"
            "wave_differential": float,  # AM vs PM scoring advantage
        }
    """
    # TODO: Implement actual weather API
    # For now, return placeholder
    return {
        "temperature_f": 72,
        "wind_mph": 10,
        "wind_direction": "SW",
        "precipitation_pct": 10,
        "conditions": "sunny",
        "wave_differential": 0.0,
    }


def create_sample_slate():
    """Create sample slate file for testing."""
    sample = """
    Scottie Scheffler Top 10 Finish Higher
    Rory McIlroy Top 5 Finish Higher
    Jon Rahm Make Cut Yes
    Xander Schauffele vs Collin Morikawa (Tournament)
    Viktor Hovland Round 1 Score O/U 69.5
    Tiger Woods Top 20 Finish Higher
    Brooks Koepka vs Bryson DeChambeau (Round 1)
    Patrick Cantlay Tournament Total O/U 275.5
    """
    
    props = parse_underdog_slate(sample)
    return props


if __name__ == "__main__":
    # Test parser
    print("=== Testing Golf Prop Parser ===\n")
    
    props = create_sample_slate()
    
    for prop in props:
        print(f"Player: {prop.get('player', 'N/A')}")
        print(f"Market: {prop.get('market', 'N/A')}")
        if prop.get('opponent'):
            print(f"Opponent: {prop['opponent']}")
        if prop.get('line'):
            print(f"Line: {prop['line']}")
        print(f"Direction: {prop.get('direction', 'TBD')}")
        print("-" * 40)
