#!/usr/bin/env python3
"""
Load picks from picks.json and group them by game for Monte Carlo analysis.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

def load_picks_from_json(filepath: str = "picks.json") -> List[Dict]:
    """Load all picks from picks.json."""
    try:
        with open(filepath, 'r') as f:
            picks = json.load(f)
        return picks
    except FileNotFoundError:
        print(f"❌ picks.json not found at {filepath}")
        return []

def infer_game_from_pick(pick: Dict) -> str:
    """
    Infer game matchup from player and team.
    Uses mapping of known players to their games.
    """
    # Known game matchups for current slate
    games = {
        "IND @ HOU": ["Jonathan Taylor", "Michael Pittman Jr.", "Colts", "C.J. Stroud", "Nico Collins", "Christian Kirk", "Texans"],
        "KC @ LV": ["Chris Oladokun", "Travis Kelce", "Gardner Minshew"],
        "LAC @ DEN": ["Bo Nix", "Trey Lance", "Javonte Williams"],
        "JAX @ TEN": ["Trevor Lawrence", "Cam Ward", "Travis Etienne"],
        "GSW @ LAL": ["Stephen Curry", "LeBron James", "Anthony Davis"],
        "MIL @ TOR": ["Giannis Antetokounmpo", "Damian Lillard", "Scottie Barnes"],
        "OKC @ NOP": ["Shai Gilgeous-Alexander", "Jalen Williams", "Zion Williamson"],
    }
    
    player = pick.get("player", "")
    team = pick.get("team", "")
    
    # Match by player name
    for game, players in games.items():
        if any(p.lower() in player.lower() for p in players):
            return game
    
    # Fallback: match by team
    for game, players in games.items():
        if team.upper() in game:
            return game
    
    return None

def group_picks_by_game(picks: List[Dict]) -> Dict[str, List[Dict]]:
    """Group picks by game matchup."""
    games = defaultdict(list)
    
    for pick in picks:
        game = infer_game_from_pick(pick)
        if game:
            games[game].append(pick)
    
    return dict(games)

def convert_picks_to_game_slate(picks_by_game: Dict[str, List[Dict]]) -> Dict:
    """
    Convert grouped picks to GAMES_SLATE format for Monte Carlo.
    """
    slate = {"NFL": [], "NBA": []}
    
    # Game info mapping
    game_info = {
        "IND @ HOU": {"type": "NFL", "kickoff": "Sunday 12:00 PM CST"},
        "KC @ LV": {"type": "NFL", "kickoff": "Sunday 3:25 PM PST"},
        "LAC @ DEN": {"type": "NFL", "kickoff": "Sunday 3:25 PM PST"},
        "JAX @ TEN": {"type": "NFL", "kickoff": "Sunday 12:00 PM CST"},
        "GSW @ LAL": {"type": "NBA", "tipoff": "Monday 10:30 PM ET"},
        "MIL @ TOR": {"type": "NBA", "tipoff": "Monday 7:30 PM ET"},
        "OKC @ NOP": {"type": "NBA", "tipoff": "Monday 9:00 PM ET"},
    }
    
    game_counter = {"NFL": 0, "NBA": 0}
    
    for game, picks in picks_by_game.items():
        if not picks:
            continue
        
        info = game_info.get(game, {})
        game_type = info.get("type", "NFL")
        
        # Convert pick format
        approved_bets = []
        for pick in picks:
            bet = {
                "player": pick.get("player", "Unknown"),
                "stat": pick.get("stat", "").replace("_", " ").title(),
                "line": float(pick.get("line", 0)),
                "dir": pick.get("direction", "higher").upper(),
                "conf": 0.65,  # Default confidence
            }
            approved_bets.append(bet)
        
        # Build game object
        game_id = f"{game_type}_{game_counter[game_type]}"
        game_counter[game_type] += 1
        
        game_obj = {
            "id": game_id,
            "matchup": game,
            "approved_bets": approved_bets,
            "correlations": {},
        }
        
        if game_type == "NFL":
            game_obj["kickoff"] = info.get("kickoff", "TBA")
        else:
            game_obj["tipoff"] = info.get("tipoff", "TBA")
        
        slate[game_type].append(game_obj)
    
    return slate

def load_dynamic_slate() -> Dict:
    """Load picks from picks.json and build GAMES_SLATE dynamically."""
    picks = load_picks_from_json()
    
    if not picks:
        print("❌ No picks found in picks.json, using defaults")
        return None
    
    picks_by_game = group_picks_by_game(picks)
    print(f"\n📊 Loaded {len(picks)} picks from {len(picks_by_game)} games:")
    
    for game, game_picks in picks_by_game.items():
        print(f"   {game}: {len(game_picks)} picks")
    
    slate = convert_picks_to_game_slate(picks_by_game)
    return slate

if __name__ == "__main__":
    # Test the loader
    slate = load_dynamic_slate()
    if slate:
        print(f"\n✅ Built GAMES_SLATE with {len(slate['NFL'])} NFL + {len(slate['NBA'])} NBA games")
        
        for game in slate['NFL']:
            print(f"\n{game['matchup']}:")
            for bet in game['approved_bets']:
                print(f"  - {bet['player']}: {bet['stat']} {bet['line']} {bet['dir']}")
