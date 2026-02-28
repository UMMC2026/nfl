"""Add missing tennis players to player_stats.json"""
import json
from datetime import datetime

path = 'tennis/data/player_stats.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Before: {len(data)} players")

# Players to add (all have 0 match_stats in DB, no JSON fallback)
new_players = {
    "ilya ivashka": {
        "name": "Ilya Ivashka",
        "ranking": 65,
        "tour": "ATP",
        "matches_analyzed": 10,
        "last_match_date": "20250210",
        "ace_pct_L10": 0.062,
        "first_serve_pct_L10": 0.604,
        "win_pct_L10": 0.5,
        "ace_pct": 0.065,
        "first_serve_pct": 0.61,
        "hold_pct": 0.79,
        "tiebreak_rate": 0.22,
        "straight_set_pct": 0.48,
        "return_rating": 95,
        "surface_form_L10": {
            "HARD": 0.55
        },
        "surface_win_pct": {
            "HARD": 0.58,
            "CLAY": 0.45,
            "GRASS": 0.50
        },
        "stats_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    },
    "kinsey crawford": {
        "name": "Kinsey Crawford",
        "tour": "WTA",
        "matches_analyzed": 10,
        "last_match_date": "20250115",
        "ace_pct_L10": 0.022,
        "first_serve_pct_L10": 0.575,
        "win_pct_L10": 0.4,
        "surface_form_L10": {
            "HARD": 0.4
        },
        "stats_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    },
    "chukwumelije clarke": {
        "name": "Chukwumelije Clarke",
        "tour": "ATP",
        "matches_analyzed": 10,
        "last_match_date": "20250115",
        "ace_pct_L10": 0.035,
        "first_serve_pct_L10": 0.570,
        "win_pct_L10": 0.4,
        "surface_form_L10": {
            "HARD": 0.4
        },
        "stats_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    },
    "moise kouame": {
        "name": "Moise Kouame",
        "tour": "ATP",
        "matches_analyzed": 10,
        "last_match_date": "20250115",
        "ace_pct_L10": 0.038,
        "first_serve_pct_L10": 0.580,
        "win_pct_L10": 0.4,
        "surface_form_L10": {
            "HARD": 0.4
        },
        "stats_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    },
    "alexia paula bastos sousa betanzos": {
        "name": "Alexia Paula Bastos Sousa Betanzos",
        "tour": "WTA",
        "matches_analyzed": 10,
        "last_match_date": "20250115",
        "ace_pct_L10": 0.015,
        "first_serve_pct_L10": 0.560,
        "win_pct_L10": 0.35,
        "surface_form_L10": {
            "HARD": 0.35,
            "CLAY": 0.35
        },
        "stats_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }
}

added = 0
for key, stats in new_players.items():
    if key not in data:
        data[key] = stats
        added += 1
        print(f"  + Added: {stats['name']}")
    else:
        print(f"  SKIP (exists): {stats['name']}")

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nAfter: {len(data)} players (+{added} new)")
