"""
SOCCER PLAYER STATS INGESTION — FBref/CSV/JSON

Usage:
    python soccer/scripts/update_stats_from_fbref.py --input <match_log.csv> --player "Bernardo Silva"

- Parses match logs for shots attempted, assists, etc.
- Updates soccer/player_stats.json with true per-game stats
- Can be extended for API or batch mode
"""

import csv
import json
import argparse
from pathlib import Path

STATS_FILE = Path(__file__).parent.parent / "player_stats.json"

# Supported columns: 'Date', 'Opponent', 'Shots', 'Assists', ...
def parse_match_log(csv_path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        shots = []
        assists = []
        games = 0
        for row in reader:
            try:
                shots.append(float(row.get('Shots', 0)))
                assists.append(float(row.get('Assists', 0)))
                games += 1
            except Exception:
                continue
        return {
            'shots_per_game': round(sum(shots)/games, 2) if games else 0,
            'assists_per_game': round(sum(assists)/games, 2) if games else 0,
            'games_played': games
        }

def update_player_stats(player, stats):
    # Load or create player_stats.json
    if STATS_FILE.exists():
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
    # Update
    key = player.lower().replace(' ', '_')
    data[key] = {
        'name': player,
        'shots_per_game': stats['shots_per_game'],
        'assists_per_game': stats['assists_per_game'],
        'games_played': stats['games_played']
    }
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Updated stats for {player}: {stats}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Path to match log CSV')
    parser.add_argument('--player', required=True, help='Player name')
    args = parser.parse_args()
    stats = parse_match_log(args.input)
    update_player_stats(args.player, stats)

if __name__ == '__main__':
    main()
