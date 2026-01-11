"""
Hydrate picks.json with real recent game data from NBA API
Improves probability calculations from default 50% to actual probabilities
"""
import json
import time
import sys
import io
from pathlib import Path
from typing import Optional, List
from statistics import mean, stdev

# Fix UTF-8 encoding on Windows
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Try to import nba_api
try:
    from nba_api.stats.endpoints import playergamelog, commonplayerinfo
    from nba_api.stats.static import players
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    print("WARNING: nba_api not installed. Run: pip install nba_api")

# Stat mapping from Underdog to NBA API columns
STAT_MAP = {
    "points": "PTS",
    "rebounds": "REB", 
    "assists": "AST",
    "3pm": "FG3M",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TOV",
    "pts+reb+ast": ["PTS", "REB", "AST"],
    "pts+reb": ["PTS", "REB"],
    "pts+ast": ["PTS", "AST"],
    "reb+ast": ["REB", "AST"],
    "stl+blk": ["STL", "BLK"],
}

def find_player_id(player_name: str) -> Optional[int]:
    """Find NBA player ID by name."""
    if not NBA_API_AVAILABLE:
        return None
    
    all_players = players.get_players()
    # Try exact match first
    for p in all_players:
        if p['full_name'].lower() == player_name.lower():
            return p['id']
    
    # Try partial match
    for p in all_players:
        if player_name.lower() in p['full_name'].lower():
            return p['id']
    
    # Handle common name variations
    name_fixes = {
        "shai gilgeous-alexander": "Shai Gilgeous-Alexander",
        "karl-anthony towns": "Karl-Anthony Towns",
        "og anunoby": "OG Anunoby",
    }
    fixed_name = name_fixes.get(player_name.lower())
    if fixed_name:
        for p in all_players:
            if p['full_name'] == fixed_name:
                return p['id']
    
    return None


def get_recent_values(player_id: int, stat: str, num_games: int = 10) -> List[float]:
    """Get recent game values for a stat."""
    if not NBA_API_AVAILABLE:
        return []
    
    try:
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season="2024-25",
            season_type_all_star="Regular Season"
        )
        df = gamelog.get_data_frames()[0]
        
        if df.empty:
            return []
        
        # Get stat column(s)
        stat_cols = STAT_MAP.get(stat.lower())
        if stat_cols is None:
            print(f"  Unknown stat: {stat}")
            return []
        
        if isinstance(stat_cols, list):
            # Combo stat - sum multiple columns
            values = df[stat_cols].sum(axis=1).head(num_games).tolist()
        else:
            values = df[stat_cols].head(num_games).tolist()
        
        return [float(v) for v in values]
    
    except Exception as e:
        print(f"  Error fetching gamelog: {e}")
        return []


def hydrate_picks(input_file: str = "picks.json", output_file: str = "picks_hydrated.json"):
    """Hydrate picks with recent game data."""
    
    if not NBA_API_AVAILABLE:
        print("ERROR: nba_api required. Install with: pip install nba_api")
        return
    
    # Load picks
    with open(input_file, "r") as f:
        picks = json.load(f)
    
    print(f"Loaded {len(picks)} picks from {input_file}")
    
    # Cache player IDs to avoid repeated lookups
    player_cache = {}
    hydrated = []
    
    for i, pick in enumerate(picks):
        player = pick["player"]
        stat = pick["stat"]
        
        print(f"[{i+1}/{len(picks)}] {player} - {stat}...", end=" ")
        
        # Get or lookup player ID
        if player not in player_cache:
            player_id = find_player_id(player)
            player_cache[player] = player_id
            time.sleep(0.6)  # Rate limiting
        else:
            player_id = player_cache[player]
        
        if player_id is None:
            print(f"NOT FOUND")
            hydrated.append(pick)  # Keep original
            continue
        
        # Get recent values
        recent = get_recent_values(player_id, stat)
        time.sleep(0.6)  # Rate limiting
        
        if recent:
            pick["recent_values"] = recent
            avg = mean(recent)
            std = stdev(recent) if len(recent) > 1 else 5.0
            pick["mu"] = round(avg, 2)
            pick["sigma"] = round(std, 2)
            print(f"✓ avg={avg:.1f}, std={std:.1f}, n={len(recent)}")
        else:
            print(f"NO DATA")
        
        hydrated.append(pick)
    
    # Save hydrated picks
    with open(output_file, "w") as f:
        json.dump(hydrated, f, indent=2)
    
    print(f"\n✅ Saved {len(hydrated)} hydrated picks to {output_file}")
    
    # Stats
    with_data = sum(1 for p in hydrated if p.get("recent_values"))
    print(f"   {with_data}/{len(hydrated)} picks have real data ({100*with_data/len(hydrated):.0f}%)")


if __name__ == "__main__":
    hydrate_picks()
