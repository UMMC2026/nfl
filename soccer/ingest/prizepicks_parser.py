"""
PrizePicks Soccer Parser
========================
Parses soccer props from PrizePicks paste format.

Example format:
Erling Haaland
MCI @ ARS • Today 12:30pm
Shots
More or Less
4.5
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


# Team abbreviation mapping
TEAM_ABBREVS = {
    # Premier League
    "MCI": "Manchester City",
    "ARS": "Arsenal",
    "LIV": "Liverpool",
    "CHE": "Chelsea",
    "MUN": "Manchester United",
    "TOT": "Tottenham",
    "NEW": "Newcastle",
    "AVL": "Aston Villa",
    "BHA": "Brighton",
    "WHU": "West Ham",
    "CRY": "Crystal Palace",
    "BRE": "Brentford",
    "FUL": "Fulham",
    "WOL": "Wolves",
    "EVE": "Everton",
    "BOU": "Bournemouth",
    "NFO": "Nottingham Forest",
    "LEI": "Leicester",
    "IPS": "Ipswich",
    "SOU": "Southampton",
    
    # La Liga
    "RMA": "Real Madrid",
    "BAR": "Barcelona",
    "ATM": "Atletico Madrid",
    "SEV": "Sevilla",
    "RSO": "Real Sociedad",
    "VIL": "Villarreal",
    "ATH": "Athletic Bilbao",
    "BET": "Real Betis",
    
    # Bundesliga
    "BAY": "Bayern Munich",
    "BVB": "Borussia Dortmund",
    "RBL": "RB Leipzig",
    "LEV": "Bayer Leverkusen",
    "BMG": "Borussia Monchengladbach",
    "FRA": "Eintracht Frankfurt",
    
    # Serie A
    "INT": "Inter Milan",
    "MIL": "AC Milan",
    "JUV": "Juventus",
    "NAP": "Napoli",
    "ROM": "AS Roma",
    "LAZ": "Lazio",
    "ATA": "Atalanta",
    "FIO": "Fiorentina",
    
    # MLS
    "LAFC": "LAFC",
    "LAG": "LA Galaxy",
    "NYC": "NYCFC",
    "ATL": "Atlanta United",
    "SEA": "Seattle Sounders",
    "MIA": "Inter Miami",
    "PHI": "Philadelphia Union",
    "CIN": "FC Cincinnati",
}


def parse_prizepicks_soccer(text: str) -> List[SoccerProp]:
    """
    Parse PrizePicks soccer props from pasted text.
    
    Args:
        text: Raw pasted text from PrizePicks
        
    Returns:
        List of SoccerProp objects
    """
    props = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        # Skip common non-data lines
        if lines[i].lower() in ['more or less', 'more', 'less', 'over', 'under']:
            i += 1
            continue
        
        # Look for pattern: Player Name, Match Info, Stat, More or Less, Line
        if i + 4 <= len(lines):
            potential_player = lines[i]
            potential_match = lines[i + 1] if i + 1 < len(lines) else ""
            potential_stat = lines[i + 2] if i + 2 < len(lines) else ""
            
            # Check for match pattern (ABC @ DEF • time)
            match_pattern = re.match(r'([A-Z]{2,4})\s*@\s*([A-Z]{2,4})', potential_match)
            
            if match_pattern:
                away_abbrev = match_pattern.group(1)
                home_abbrev = match_pattern.group(2)
                
                away_team = TEAM_ABBREVS.get(away_abbrev, away_abbrev)
                home_team = TEAM_ABBREVS.get(home_abbrev, home_abbrev)
                
                # Find the line value (look for number in next few lines)
                line_value = None
                stat = potential_stat.lower().strip()
                
                for j in range(i + 3, min(i + 6, len(lines))):
                    try:
                        line_value = float(lines[j])
                        break
                    except ValueError:
                        continue
                
                if line_value is not None and stat:
                    # Normalize stat
                    stat = _normalize_stat(stat)
                    
                    props.append(SoccerProp(
                        player=potential_player,
                        team=away_team,  # Assume player is on away team (first listed)
                        opponent=home_team,
                        match=f"{away_team} @ {home_team}",
                        stat=stat,
                        line=line_value,
                    ))
                    
                    i += 5
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
        "pass": "passes",
        "passes completed": "passes_completed",
        "tackle": "tackles",
        "interception": "interceptions",
        "save": "saves",
    }
    
    return normalize_map.get(stat, stat)


def load_slate_file(filepath: str) -> List[SoccerProp]:
    """Load props from a slate file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Slate file not found: {filepath}")
    
    text = path.read_text(encoding='utf-8')
    return parse_prizepicks_soccer(text)


if __name__ == "__main__":
    # Test parsing
    test_text = """
Erling Haaland
MCI @ ARS • Today 12:30pm
Shots
More or Less
4.5

Mohamed Salah
LIV @ CHE • Today 3:00pm
Shots on Target
More or Less
2.5
"""
    
    props = parse_prizepicks_soccer(test_text)
    for p in props:
        print(f"{p.player}: {p.stat} {p.line} ({p.team} vs {p.opponent})")
