"""
SOCCER PLAYER MATCH LOG DOWNLOADER — API-Football via RapidAPI

Downloads real player stats (shots, assists, goals, etc.) for soccer players
and saves as CSV for ingestion into the prop analysis system.

Usage:
    python soccer/scripts/download_player_stats_api.py --player "Bernardo Silva" --team "Manchester City"
    python soccer/scripts/download_player_stats_api.py --team "Manchester City" --all
    python soccer/scripts/download_player_stats_api.py --download-all-est

Requires RAPIDAPI_KEY in .env
"""

import os
import requests
import csv
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    raise ValueError("RAPIDAPI_KEY not found in .env")

# API-Football via RapidAPI
API_HOST = "api-football-v1.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/v3"

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": API_HOST
}

# Output paths
DATA_DIR = Path(__file__).parent.parent / "data"
CSV_OUT = DATA_DIR / "player_stats_api.csv"
STATS_JSON = DATA_DIR / "player_stats.json"

# Premier League ID
PREMIER_LEAGUE_ID = 39
CURRENT_SEASON = 2024  # API uses start year

# Team IDs (API-Football)
TEAM_IDS = {
    "manchester city": 50,
    "man city": 50,
    "mci": 50,
    "newcastle": 34,
    "newcastle united": 34,
    "new": 34,
    "arsenal": 42,
    "liverpool": 40,
    "chelsea": 49,
    "manchester united": 33,
    "man united": 33,
    "tottenham": 47,
    "aston villa": 66,
    "brighton": 51,
    "west ham": 48,
    "bournemouth": 35,
    "fulham": 36,
    "wolves": 39,
    "crystal palace": 52,
    "brentford": 55,
    "everton": 45,
    "nottingham forest": 65,
    "luton": 1359,
    "burnley": 44,
    "sheffield united": 62,
}


def get_team_players(team_id: int, season: int = CURRENT_SEASON) -> list:
    """Get all players for a team"""
    url = f"{BASE_URL}/players/squads"
    params = {"team": team_id}
    
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        print(f"❌ API error: {resp.status_code}")
        return []
    
    data = resp.json()
    if data.get("errors"):
        print(f"❌ API errors: {data['errors']}")
        return []
    
    players = []
    for team_data in data.get("response", []):
        for player in team_data.get("players", []):
            players.append({
                "id": player["id"],
                "name": player["name"],
                "position": player.get("position", "Unknown")
            })
    
    return players


def get_player_stats(player_id: int, season: int = CURRENT_SEASON) -> dict:
    """Get detailed stats for a player"""
    url = f"{BASE_URL}/players"
    params = {
        "id": player_id,
        "season": season
    }
    
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        print(f"❌ API error for player {player_id}: {resp.status_code}")
        return {}
    
    data = resp.json()
    if not data.get("response"):
        return {}
    
    player_data = data["response"][0]
    player_info = player_data.get("player", {})
    
    # Aggregate stats across all competitions
    stats = {
        "name": player_info.get("name", ""),
        "firstname": player_info.get("firstname", ""),
        "lastname": player_info.get("lastname", ""),
        "age": player_info.get("age", 0),
        "nationality": player_info.get("nationality", ""),
        "position": "",
        "games_played": 0,
        "minutes": 0,
        "goals": 0,
        "assists": 0,
        "shots_total": 0,
        "shots_on_target": 0,
        "passes_total": 0,
        "passes_accuracy": 0,
        "tackles": 0,
        "interceptions": 0,
        "fouls_committed": 0,
        "fouls_drawn": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "saves": 0,  # For goalkeepers
        "goals_conceded": 0,
    }
    
    for stat_block in player_data.get("statistics", []):
        league = stat_block.get("league", {})
        # Focus on Premier League
        if league.get("id") != PREMIER_LEAGUE_ID:
            continue
        
        games = stat_block.get("games", {})
        goals_data = stat_block.get("goals", {})
        shots = stat_block.get("shots", {})
        passes = stat_block.get("passes", {})
        tackles = stat_block.get("tackles", {})
        fouls = stat_block.get("fouls", {})
        cards = stat_block.get("cards", {})
        
        stats["position"] = games.get("position", stats["position"])
        stats["games_played"] += games.get("appearences", 0) or 0
        stats["minutes"] += games.get("minutes", 0) or 0
        stats["goals"] += goals_data.get("total", 0) or 0
        stats["assists"] += goals_data.get("assists", 0) or 0
        stats["shots_total"] += shots.get("total", 0) or 0
        stats["shots_on_target"] += shots.get("on", 0) or 0
        stats["passes_total"] += passes.get("total", 0) or 0
        stats["passes_accuracy"] = passes.get("accuracy", 0) or 0
        stats["tackles"] += tackles.get("total", 0) or 0
        stats["interceptions"] += tackles.get("interceptions", 0) or 0
        stats["fouls_committed"] += fouls.get("committed", 0) or 0
        stats["fouls_drawn"] += fouls.get("drawn", 0) or 0
        stats["yellow_cards"] += cards.get("yellow", 0) or 0
        stats["red_cards"] += cards.get("red", 0) or 0
        
        # Goalkeeper stats
        if stat_block.get("goals"):
            stats["saves"] = stat_block["goals"].get("saves", 0) or 0
            stats["goals_conceded"] = stat_block["goals"].get("conceded", 0) or 0
    
    return stats


def calculate_per_game_stats(stats: dict) -> dict:
    """Calculate per-game averages"""
    gp = stats.get("games_played", 0)
    if gp == 0:
        return stats
    
    stats["shots_per_game"] = round(stats["shots_total"] / gp, 2)
    stats["shots_on_target_per_game"] = round(stats["shots_on_target"] / gp, 2)
    stats["goals_per_game"] = round(stats["goals"] / gp, 2)
    stats["assists_per_game"] = round(stats["assists"] / gp, 2)
    stats["saves_per_game"] = round(stats["saves"] / gp, 2) if stats["saves"] else 0
    stats["goals_conceded_per_game"] = round(stats["goals_conceded"] / gp, 2) if stats["goals_conceded"] else 0
    
    return stats


def download_team_stats(team_name: str, save_csv: bool = True) -> list:
    """Download stats for all players on a team"""
    team_key = team_name.lower()
    team_id = TEAM_IDS.get(team_key)
    
    if not team_id:
        print(f"❌ Team not found: {team_name}")
        print(f"Available teams: {', '.join(TEAM_IDS.keys())}")
        return []
    
    print(f"📥 Fetching players for {team_name} (ID: {team_id})...")
    players = get_team_players(team_id)
    
    if not players:
        print(f"❌ No players found for {team_name}")
        return []
    
    print(f"✅ Found {len(players)} players")
    
    all_stats = []
    for i, player in enumerate(players):
        print(f"  [{i+1}/{len(players)}] Fetching {player['name']}...")
        stats = get_player_stats(player["id"])
        
        if stats and stats.get("games_played", 0) > 0:
            stats = calculate_per_game_stats(stats)
            stats["team"] = team_name
            all_stats.append(stats)
            print(f"    ✅ {stats['games_played']} GP, {stats.get('shots_per_game', 0)} shots/gm")
        else:
            print(f"    ⚠️ No PL stats")
        
        time.sleep(0.3)  # Rate limit
    
    if save_csv and all_stats:
        save_stats_csv(all_stats, team_name)
        update_stats_json(all_stats)
    
    return all_stats


def save_stats_csv(stats_list: list, team_name: str):
    """Save stats to CSV"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    filename = DATA_DIR / f"{team_name.lower().replace(' ', '_')}_stats_{datetime.now().strftime('%Y%m%d')}.csv"
    
    if not stats_list:
        return
    
    fieldnames = list(stats_list[0].keys())
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stats_list)
    
    print(f"✅ Saved to {filename}")


def update_stats_json(stats_list: list):
    """Update player_stats.json with new data"""
    # Load existing
    if STATS_JSON.exists():
        with open(STATS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
    
    # Update with new stats
    for stats in stats_list:
        name_key = stats["name"].lower().replace(" ", "_")
        data[name_key] = {
            "name": stats["name"],
            "team": stats.get("team", ""),
            "position": stats.get("position", ""),
            "games_played": stats.get("games_played", 0),
            "shots_per_game": stats.get("shots_per_game", 0),
            "shots_on_target_per_game": stats.get("shots_on_target_per_game", 0),
            "goals_per_game": stats.get("goals_per_game", 0),
            "assists_per_game": stats.get("assists_per_game", 0),
            "saves_per_game": stats.get("saves_per_game", 0),
            "goals_conceded_per_game": stats.get("goals_conceded_per_game", 0),
            "updated": datetime.now().isoformat()
        }
    
    # Save
    STATS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Updated {STATS_JSON}")


def download_all_est_players():
    """Download stats for all players currently showing as EST in reports"""
    # Players from the current report that have EST
    est_players = [
        ("Bernardo Silva", "Manchester City"),
        ("James Trafford", "Manchester City"),
        ("Antoine Semenyo", "Bournemouth"),  # On loan
        ("Sandro Tonali", "Newcastle"),
        ("Anthony Gordon", "Newcastle"),
        ("Yoane Wissa", "Brentford"),  # On loan to Newcastle?
        ("Bruno Guimaraes", "Newcastle"),
        ("Jacob Murphy", "Newcastle"),
        ("Lewis Hall", "Newcastle"),
        ("Abdukodir Khusanov", "Manchester City"),
        ("Malick Thiaw", "AC Milan"),  # On loan
        ("Nicolas Gonzalez", "Manchester City"),
        ("Jacob Ramsey", "Aston Villa"),
        ("Nathan Ake", "Manchester City"),
        ("Nico O'Reilly", "Manchester City"),
        ("Phil Foden", "Manchester City"),
        ("Matheus Nunes", "Manchester City"),
        ("Rayan Ait-Nouri", "Wolves"),
        ("Sven Botman", "Newcastle"),
        ("Lewis Miley", "Newcastle"),
        ("Nick Pope", "Newcastle"),
        ("Erling Haaland", "Manchester City"),
    ]
    
    # Group by team
    teams_to_download = set()
    for _, team in est_players:
        team_key = team.lower()
        if team_key in TEAM_IDS or any(k in team_key for k in TEAM_IDS.keys()):
            teams_to_download.add(team)
    
    print(f"📥 Downloading stats for {len(teams_to_download)} teams...")
    
    all_stats = []
    for team in teams_to_download:
        print(f"\n{'='*50}")
        print(f"📥 {team}")
        print(f"{'='*50}")
        stats = download_team_stats(team)
        all_stats.extend(stats)
        time.sleep(1)  # Rate limit between teams
    
    print(f"\n✅ Downloaded {len(all_stats)} player stats total")
    return all_stats


def main():
    parser = argparse.ArgumentParser(description="Download soccer player stats from API-Football")
    parser.add_argument('--player', help='Player name to search for')
    parser.add_argument('--team', help='Team name (e.g., "Manchester City")')
    parser.add_argument('--all', action='store_true', help='Download all players for team')
    parser.add_argument('--download-all-est', action='store_true', help='Download all EST players from current report')
    parser.add_argument('--season', type=int, default=CURRENT_SEASON, help='Season year (default: 2024)')
    
    args = parser.parse_args()
    
    if args.download_all_est:
        download_all_est_players()
    elif args.team and args.all:
        download_team_stats(args.team)
    elif args.team:
        download_team_stats(args.team)
    else:
        print("Usage:")
        print("  --team 'Manchester City' --all   Download all players for a team")
        print("  --download-all-est               Download all EST players from report")


if __name__ == '__main__':
    main()

