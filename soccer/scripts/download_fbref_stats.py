"""
SOCCER PLAYER STATS DOWNLOADER — FBref Public Data

Downloads real player stats from FBref (free, public data).
Saves as CSV and updates player_stats.json for prop analysis.

Usage:
    python soccer/scripts/download_fbref_stats.py --team "Manchester City"
    python soccer/scripts/download_fbref_stats.py --league "Premier-League"
    python soccer/scripts/download_fbref_stats.py --download-pl-stats

No API key required - uses public FBref data.
"""

import os
import csv
import json
import argparse
import time
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
CSV_OUT = DATA_DIR / "fbref_player_stats.csv"
STATS_JSON = DATA_DIR / "player_stats.json"

# FBref URLs
FBREF_BASE = "https://fbref.com/en/comps/9"  # Premier League

# Premier League squad IDs (FBref)
TEAM_SQUAD_IDS = {
    "manchester city": "b8fd03ef",
    "newcastle": "b2b47a98",
    "arsenal": "18bb7c10",
    "liverpool": "822bd0ba",
    "chelsea": "cff3d9bb",
    "manchester united": "19538871",
    "tottenham": "361ca564",
    "aston villa": "8602292d",
    "brighton": "d07537b9",
    "west ham": "7c21e445",
    "bournemouth": "4ba7cbea",
    "fulham": "fd962109",
    "wolves": "8cec06e1",
    "crystal palace": "47c64c55",
    "brentford": "cd051869",
    "everton": "d3fd31cc",
    "nottingham forest": "e4a775cb",
    "leicester": "a2d435b3",
    "ipswich": "b74092de",
    "southampton": "33c895d4",
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_league_shooting_stats() -> list:
    """
    Fetch the Premier League shooting stats table from FBref.
    Returns list of player dicts with stats.
    """
    url = "https://fbref.com/en/comps/9/shooting/Premier-League-Stats"
    headers = {"User-Agent": USER_AGENT}
    
    print(f"📥 Fetching PL shooting stats from FBref...")
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []
    
    # Parse HTML table (simple approach - look for key data)
    from html.parser import HTMLParser
    import re
    
    html = resp.text
    
    # Save raw HTML for debugging
    debug_file = DATA_DIR / "fbref_raw.html"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Saved raw HTML to {debug_file}")
    
    # Use pandas if available for better parsing
    try:
        import pandas as pd
        tables = pd.read_html(html, attrs={'id': 'stats_shooting'})
        if tables:
            df = tables[0]
            print(f"✅ Parsed {len(df)} rows from shooting stats")
            return df.to_dict('records')
    except ImportError:
        print("⚠️ pandas not available, using basic parsing")
    except Exception as e:
        print(f"⚠️ pandas parsing failed: {e}")
    
    return []


def fetch_team_stats_page(team_name: str) -> str:
    """Fetch a team's stats page HTML"""
    team_key = team_name.lower().replace(" ", "-")
    squad_id = TEAM_SQUAD_IDS.get(team_name.lower())
    
    if not squad_id:
        print(f"❌ Team not found: {team_name}")
        return ""
    
    # FBref URL format: /en/squads/{id}/{Team-Name}-Stats
    team_slug = team_name.title().replace(" ", "-")
    url = f"https://fbref.com/en/squads/{squad_id}/2024-2025/{team_slug}-Stats"
    
    headers = {"User-Agent": USER_AGENT}
    
    print(f"📥 Fetching {team_name} stats from {url}")
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return ""


def parse_player_stats_from_html(html: str, team_name: str) -> list:
    """Parse player stats from FBref team page HTML using pandas"""
    if not html:
        return []
    
    try:
        import pandas as pd
        
        # Find all tables
        tables = pd.read_html(html)
        
        players = []
        
        # Look for standard stats table (usually first one with player names)
        for i, df in enumerate(tables):
            # Check if this looks like a player stats table
            cols = [str(c).lower() for c in df.columns.tolist()]
            
            # Look for tables with 'player' and stat columns
            if any('player' in str(c).lower() for c in df.columns):
                print(f"  Found player table #{i} with {len(df)} rows")
                
                # Try to extract key stats
                for _, row in df.iterrows():
                    player_name = None
                    for col in df.columns:
                        if 'player' in str(col).lower():
                            player_name = str(row[col])
                            break
                    
                    if not player_name or player_name == 'nan':
                        continue
                    
                    # Extract stats (column names vary)
                    player_data = {
                        "name": player_name,
                        "team": team_name,
                        "games_played": 0,
                        "shots_total": 0,
                        "shots_on_target": 0,
                        "goals": 0,
                        "assists": 0,
                    }
                    
                    for col in df.columns:
                        col_lower = str(col).lower()
                        val = row[col]
                        
                        # Try to convert to number
                        try:
                            val = float(val) if val and str(val) != 'nan' else 0
                        except (ValueError, TypeError):
                            val = 0
                        
                        if 'mp' in col_lower or 'matches' in col_lower or 'played' in col_lower:
                            player_data["games_played"] = int(val)
                        elif col_lower in ('sh', 'shots') or 'shots' in col_lower and 'target' not in col_lower:
                            player_data["shots_total"] = int(val)
                        elif 'sot' in col_lower or 'target' in col_lower:
                            player_data["shots_on_target"] = int(val)
                        elif col_lower in ('gls', 'goals'):
                            player_data["goals"] = int(val)
                        elif col_lower in ('ast', 'assists'):
                            player_data["assists"] = int(val)
                    
                    if player_data["games_played"] > 0:
                        players.append(player_data)
                
                break  # Use first matching table
        
        return players
        
    except ImportError:
        print("❌ pandas required: pip install pandas lxml")
        return []
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        return []


def calculate_per_game(players: list) -> list:
    """Add per-game stats"""
    for p in players:
        gp = p.get("games_played", 0)
        if gp > 0:
            p["shots_per_game"] = round(p.get("shots_total", 0) / gp, 2)
            p["shots_on_target_per_game"] = round(p.get("shots_on_target", 0) / gp, 2)
            p["goals_per_game"] = round(p.get("goals", 0) / gp, 2)
            p["assists_per_game"] = round(p.get("assists", 0) / gp, 2)
    return players


def save_stats(players: list, team_name: str = "combined"):
    """Save to CSV and update JSON"""
    if not players:
        print("No players to save")
        return
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # CSV
    csv_file = DATA_DIR / f"fbref_{team_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
    fieldnames = list(players[0].keys())
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(players)
    
    print(f"✅ Saved {len(players)} players to {csv_file}")
    
    # Update JSON
    update_player_stats_json(players)


def update_player_stats_json(players: list):
    """Update the main player_stats.json"""
    if STATS_JSON.exists():
        with open(STATS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
    
    for p in players:
        key = p["name"].lower().replace(" ", "_")
        data[key] = {
            "name": p["name"],
            "team": p.get("team", ""),
            "games_played": p.get("games_played", 0),
            "shots_per_game": p.get("shots_per_game", 0),
            "shots_on_target_per_game": p.get("shots_on_target_per_game", 0),
            "goals_per_game": p.get("goals_per_game", 0),
            "assists_per_game": p.get("assists_per_game", 0),
            "updated": datetime.now().isoformat(),
            "source": "fbref"
        }
    
    with open(STATS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Updated {STATS_JSON} ({len(data)} total players)")


def download_team(team_name: str):
    """Download and save stats for one team"""
    html = fetch_team_stats_page(team_name)
    if not html:
        return []
    
    players = parse_player_stats_from_html(html, team_name)
    players = calculate_per_game(players)
    save_stats(players, team_name)
    
    return players


def download_all_pl_teams():
    """Download stats for all PL teams"""
    all_players = []
    
    for team in TEAM_SQUAD_IDS.keys():
        print(f"\n{'='*50}")
        print(f"📥 {team.title()}")
        print(f"{'='*50}")
        
        players = download_team(team)
        all_players.extend(players)
        
        time.sleep(3)  # Be nice to FBref
    
    print(f"\n✅ Total: {len(all_players)} players downloaded")
    return all_players


def download_key_teams():
    """Download just MCI and NEW for the current report"""
    teams = ["manchester city", "newcastle"]
    all_players = []
    
    for team in teams:
        print(f"\n{'='*50}")
        print(f"📥 {team.title()}")
        print(f"{'='*50}")
        
        players = download_team(team)
        all_players.extend(players)
        
        time.sleep(3)
    
    return all_players


def main():
    parser = argparse.ArgumentParser(description="Download soccer stats from FBref")
    parser.add_argument('--team', help='Team name')
    parser.add_argument('--download-pl-stats', action='store_true', help='Download all PL team stats')
    parser.add_argument('--download-key-teams', action='store_true', help='Download MCI + NEW only')
    parser.add_argument('--league-shooting', action='store_true', help='Download PL shooting stats table')
    
    args = parser.parse_args()
    
    if args.league_shooting:
        stats = fetch_league_shooting_stats()
        if stats:
            print(f"Got {len(stats)} player records")
    elif args.download_pl_stats:
        download_all_pl_teams()
    elif args.download_key_teams:
        download_key_teams()
    elif args.team:
        download_team(args.team)
    else:
        print("Usage:")
        print("  --team 'Manchester City'    Download one team")
        print("  --download-key-teams        Download MCI + NEW")
        print("  --download-pl-stats         Download all PL teams")
        print("  --league-shooting           Download PL shooting stats")


if __name__ == '__main__':
    main()
