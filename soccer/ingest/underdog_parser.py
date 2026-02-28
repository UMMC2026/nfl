"""
Underdog Fantasy Soccer Parser
==============================
Parses soccer props from Underdog paste format.

Example format:
Erling Haaland
Manchester City vs Arsenal
Shots: 4.5
Higher | Lower

Mohamed Salah
Liverpool vs Chelsea
Shots on Target: 2.5
Higher | Lower
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass
class SoccerProp:
    """Represents a single soccer prop."""
    player: str
    team: str
    opponent: str
    match: str
    stat: str
    line: float
    league: str = "premier_league"
    position: Optional[str] = None


def parse_underdog_soccer(text: str) -> List[SoccerProp]:
    """
    Parse Underdog Fantasy soccer props from pasted text.
    
    Args:
        text: Raw pasted text from Underdog
        
    Returns:
        List of SoccerProp objects
    """
    props = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        # Skip "Higher | Lower" lines
        if lines[i].lower() in ['higher | lower', 'higher', 'lower', 'more | less']:
            i += 1
            continue
            
        # Look for player name (line without "vs" or ":")
        if i + 2 < len(lines):
            potential_player = lines[i]
            potential_match = lines[i + 1] if i + 1 < len(lines) else ""
            potential_prop = lines[i + 2] if i + 2 < len(lines) else ""
            
            # Check if this is a valid prop block
            if 'vs' in potential_match.lower() and ':' in potential_prop:
                player = potential_player
                match = potential_match
                
                # Parse match (Team A vs Team B)
                match_parts = re.split(r'\s+vs\.?\s+', match, flags=re.IGNORECASE)
                if len(match_parts) == 2:
                    team1, team2 = match_parts[0].strip(), match_parts[1].strip()
                else:
                    team1, team2 = match, "Unknown"
                
                # Parse prop (Stat: Line)
                prop_match = re.match(r'(.+?):\s*([\d.]+)', potential_prop)
                if prop_match:
                    stat = prop_match.group(1).strip().lower()
                    line = float(prop_match.group(2))
                    
                    # Normalize stat name
                    stat = _normalize_stat(stat)
                    
                    # Determine player's team (first team listed is usually home)
                    # We'll assume player belongs to team1 for now
                    team = team1
                    opponent = team2
                    
                    props.append(SoccerProp(
                        player=player,
                        team=team,
                        opponent=opponent,
                        match=match,
                        stat=stat,
                        line=line,
                    ))
                
                i += 3
                continue
        
        i += 1
    
    return props


def _normalize_stat(stat: str) -> str:
    """Normalize stat names to canonical form."""
    stat = stat.lower().strip()
    
    normalize_map = {
        "shot": "shots",
        "sog": "shots_on_target",
        "shots on goal": "shots_on_target",
        "shots on target": "shots_on_target",
        "goal": "goals",
        "assist": "assists",
        "g+a": "goal_contributions",
        "goals + assists": "goal_contributions",
        "goals+assists": "goal_contributions",
        "pass": "passes",
        "passes completed": "passes_completed",
        "tackle": "tackles",
        "interception": "interceptions",
        "save": "saves",
        "foul": "fouls_committed",
    }
    
    return normalize_map.get(stat, stat)


def load_slate_file(filepath: str) -> List[SoccerProp]:
    """Load props from a slate file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Slate file not found: {filepath}")
    
    text = path.read_text(encoding='utf-8')
    return parse_underdog_soccer(text)


if __name__ == "__main__":
    # Test parsing
    test_text = """
Erling Haaland
Manchester City vs Arsenal
Shots: 4.5
Higher | Lower

Mohamed Salah
Liverpool vs Chelsea
Shots on Target: 2.5
Higher | Lower

Bruno Fernandes
Manchester United vs Tottenham
Passes: 45.5
Higher | Lower
"""
    
    props = parse_underdog_soccer(test_text)
    for p in props:
        print(f"{p.player}: {p.stat} {p.line} ({p.team} vs {p.opponent})")
