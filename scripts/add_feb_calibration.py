"""Add Feb 1-3 calibration results."""
import csv
from datetime import datetime

new_picks = [
    # HITS - NBA 3PM Unders
    {"pick_id": "FEB01-01", "game_date": "2026-02-01", "player": "Isaac Okoro", "team": "CLE", "opponent": "", "stat": "3pm", "line": "1.5", "direction": "lower", "probability": "65.0", "tier": "STRONG", "actual_value": "1", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    {"pick_id": "FEB01-02", "game_date": "2026-02-01", "player": "Ayo Dosunmu", "team": "CHI", "opponent": "", "stat": "3pm", "line": "1.5", "direction": "higher", "probability": "62.0", "tier": "STRONG", "actual_value": "2", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    {"pick_id": "FEB01-03", "game_date": "2026-02-01", "player": "Jaylen Brown", "team": "BOS", "opponent": "", "stat": "3pm", "line": "2.5", "direction": "lower", "probability": "64.0", "tier": "STRONG", "actual_value": "2", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    {"pick_id": "FEB01-04", "game_date": "2026-02-01", "player": "Shai Gilgeous-Alexander", "team": "OKC", "opponent": "", "stat": "3pm", "line": "1.5", "direction": "lower", "probability": "68.0", "tier": "STRONG", "actual_value": "1", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    
    # HITS - NHL Binary Stats
    {"pick_id": "FEB01-05", "game_date": "2026-02-01", "player": "Jackson LaCombe", "team": "ANA", "opponent": "", "stat": "points", "line": "0.5", "direction": "higher", "probability": "58.0", "tier": "LEAN", "actual_value": "1", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nhl", "source": "sleeper"},
    {"pick_id": "FEB01-06", "game_date": "2026-02-01", "player": "Jordan Eberle", "team": "SEA", "opponent": "", "stat": "points", "line": "0.5", "direction": "higher", "probability": "60.0", "tier": "LEAN", "actual_value": "1", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nhl", "source": "sleeper"},
    {"pick_id": "FEB01-07", "game_date": "2026-02-01", "player": "Cale Makar", "team": "COL", "opponent": "", "stat": "blocks", "line": "1.5", "direction": "higher", "probability": "59.0", "tier": "LEAN", "actual_value": "2", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nhl", "source": "sleeper"},
    {"pick_id": "FEB01-08", "game_date": "2026-02-01", "player": "William Nylander", "team": "TOR", "opponent": "", "stat": "sog", "line": "2.5", "direction": "higher", "probability": "62.0", "tier": "STRONG", "actual_value": "3", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "nhl", "source": "sleeper"},
    
    # HITS - Tennis Unders
    {"pick_id": "FEB01-09", "game_date": "2026-02-02", "player": "Novak Djokovic", "team": "", "opponent": "", "stat": "games_won", "line": "18.5", "direction": "lower", "probability": "66.0", "tier": "STRONG", "actual_value": "16", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "tennis", "source": "sleeper"},
    {"pick_id": "FEB01-10", "game_date": "2026-02-02", "player": "Carlos Alcaraz", "team": "", "opponent": "", "stat": "aces", "line": "10.5", "direction": "lower", "probability": "64.0", "tier": "STRONG", "actual_value": "8", "outcome": "hit", "added_utc": "2026-02-04T00:00:00Z", "league": "tennis", "source": "sleeper"},
    
    # MISSES - NBA PRA Overs (variance stacking)
    {"pick_id": "FEB02-01", "game_date": "2026-02-02", "player": "Coby White", "team": "CHI", "opponent": "", "stat": "pra", "line": "30.5", "direction": "higher", "probability": "58.0", "tier": "LEAN", "actual_value": "34", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    {"pick_id": "FEB02-03", "game_date": "2026-02-02", "player": "Naji Marshall", "team": "DAL", "opponent": "", "stat": "pra", "line": "27.5", "direction": "higher", "probability": "55.0", "tier": "LEAN", "actual_value": "22", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    {"pick_id": "FEB03-02", "game_date": "2026-02-03", "player": "Duncan Robinson", "team": "MIA", "opponent": "", "stat": "pra", "line": "14.5", "direction": "higher", "probability": "54.0", "tier": "LEAN", "actual_value": "12", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    {"pick_id": "FEB03-03", "game_date": "2026-02-03", "player": "Deni Avdija", "team": "POR", "opponent": "", "stat": "pra", "line": "35.5", "direction": "higher", "probability": "55.0", "tier": "LEAN", "actual_value": "28", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    
    # MISSES - Rookie Variance
    {"pick_id": "FEB02-02", "game_date": "2026-02-02", "player": "Matas Buzelis", "team": "CHI", "opponent": "", "stat": "3pm", "line": "2.5", "direction": "lower", "probability": "60.0", "tier": "LEAN", "actual_value": "5", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    
    # MISSES - Big Man Rebound Under
    {"pick_id": "FEB02-04", "game_date": "2026-02-02", "player": "Jarrett Allen", "team": "CLE", "opponent": "", "stat": "rebounds", "line": "8.5", "direction": "lower", "probability": "57.0", "tier": "LEAN", "actual_value": "17", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "nba", "source": "sleeper"},
    
    # MISSES - CBB Points Over
    {"pick_id": "FEB03-01", "game_date": "2026-02-03", "player": "Johnny Furphy", "team": "IND", "opponent": "", "stat": "points", "line": "11.5", "direction": "lower", "probability": "56.0", "tier": "LEAN", "actual_value": "14", "outcome": "miss", "added_utc": "2026-02-04T00:00:00Z", "league": "cbb", "source": "sleeper"},
]

# Read existing
fieldnames = ['pick_id', 'game_date', 'player', 'team', 'opponent', 'stat', 'line', 'direction', 'probability', 'tier', 'actual_value', 'outcome', 'added_utc', 'league', 'source']
existing = []
try:
    with open('calibration_history.csv', 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.append(row)
except FileNotFoundError:
    pass

# Add new
existing.extend(new_picks)

# Write back
with open('calibration_history.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(existing)

print(f'✅ Added {len(new_picks)} picks to calibration_history.csv')
print(f'   HITS: 10 | MISSES: 7')
print(f'   Sports: NBA, NHL, Tennis, CBB')
