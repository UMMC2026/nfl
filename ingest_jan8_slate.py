"""
Ingest January 8, 2026 NBA Slate
4 games: IND@CHA, CLE@MIN, MIA@CHI, DAL@UTA
"""

import json
from datetime import datetime

# Tonight's slate - manually entered props
slate = {
    "date": "2026-01-08",
    "games": [
        {"away": "IND", "home": "CHA", "time": "6:00PM CST"},
        {"away": "CLE", "home": "MIN", "time": "7:00PM CST"},
        {"away": "MIA", "home": "CHI", "time": "7:00PM CST"},
        {"away": "DAL", "home": "UTA", "time": "8:00PM CST"}
    ],
    "picks": [
        # IND @ CHA
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "points", "line": 17.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "pra", "line": 29.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "assists", "line": 7.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "points", "line": 20.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "pra", "line": 28.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "assists", "line": 3.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "points", "line": 19.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "assists", "line": 7.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "3pm", "line": 1.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "points", "line": 25.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "rebounds", "line": 7.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "3pm", "line": 1.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "points", "line": 18.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "rebounds", "line": 6.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "3pm", "line": 1.5, "direction": "higher", "game_time": "6:00PM CST", "league": "NBA"},
        
        # CLE @ MIN
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 29.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 5.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "3pm", "line": 3.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Donovan Mitchell", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 29.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Donovan Mitchell", "team": "CLE", "opponent": "MIN", "stat": "3pm", "line": 3.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Evan Mobley", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 17.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Evan Mobley", "team": "CLE", "opponent": "MIN", "stat": "rebounds", "line": 8.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Jarrett Allen", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 12.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Jarrett Allen", "team": "CLE", "opponent": "MIN", "stat": "rebounds", "line": 8.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 17.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "assists", "line": 6.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 20.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 7.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "assists", "line": 5.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "3pm", "line": 1.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Rudy Gobert", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 10.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Rudy Gobert", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 11.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Naz Reid", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 14.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Naz Reid", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 6.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        # MIA @ CHI
        {"player": "Bam Adebayo", "team": "MIA", "opponent": "CHI", "stat": "points", "line": 16.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Bam Adebayo", "team": "MIA", "opponent": "CHI", "stat": "rebounds", "line": 10.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Tyler Herro", "team": "MIA", "opponent": "CHI", "stat": "points", "line": 20.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Tyler Herro", "team": "MIA", "opponent": "CHI", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Norman Powell", "team": "MIA", "opponent": "CHI", "stat": "points", "line": 23.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Norman Powell", "team": "MIA", "opponent": "CHI", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "points", "line": 19.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "rebounds", "line": 10.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "assists", "line": 4.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "points", "line": 16.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        {"player": "Ayo Dosunmu", "team": "CHI", "opponent": "MIA", "stat": "points", "line": 14.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        {"player": "Ayo Dosunmu", "team": "CHI", "opponent": "MIA", "stat": "assists", "line": 4.5, "direction": "higher", "game_time": "7:00PM CST", "league": "NBA"},
        
        # DAL @ UTA
        {"player": "Lauri Markkanen", "team": "UTA", "opponent": "DAL", "stat": "points", "line": 27.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        {"player": "Lauri Markkanen", "team": "UTA", "opponent": "DAL", "stat": "rebounds", "line": 7.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        
        {"player": "Keyonte George", "team": "UTA", "opponent": "DAL", "stat": "points", "line": 26.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        {"player": "Keyonte George", "team": "UTA", "opponent": "DAL", "stat": "assists", "line": 6.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        
        {"player": "Anthony Davis", "team": "DAL", "opponent": "UTA", "stat": "points", "line": 25.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        {"player": "Anthony Davis", "team": "DAL", "opponent": "UTA", "stat": "rebounds", "line": 12.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        
        {"player": "Klay Thompson", "team": "DAL", "opponent": "UTA", "stat": "points", "line": 12.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        {"player": "Klay Thompson", "team": "DAL", "opponent": "UTA", "stat": "3pm", "line": 2.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        
        {"player": "Naji Marshall", "team": "DAL", "opponent": "UTA", "stat": "points", "line": 14.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        {"player": "Naji Marshall", "team": "DAL", "opponent": "UTA", "stat": "rebounds", "line": 5.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
        {"player": "Naji Marshall", "team": "DAL", "opponent": "UTA", "stat": "assists", "line": 3.5, "direction": "higher", "game_time": "8:00PM CST", "league": "NBA"},
    ]
}

# Save for processing
output_path = 'outputs/jan8_slate_raw.json'
with open(output_path, 'w') as f:
    json.dump(slate, f, indent=2)

print(f"✅ Ingested {len(slate['picks'])} picks from {len(slate['games'])} games")
print(f"📁 Saved to: {output_path}")
print("\n📊 Games:")
for game in slate['games']:
    print(f"  • {game['away']} @ {game['home']} - {game['time']}")

print(f"\n🎯 Top players by pick count:")
from collections import Counter
player_counts = Counter([p['player'] for p in slate['picks']])
for player, count in player_counts.most_common(10):
    print(f"  • {player}: {count} props")

print("\n▶️  Next steps:")
print("1. Run: python monte_carlo_enhanced.py  # Enhancement pipeline")
print("2. Run: python structural_validation_pipeline.py  # Structural checks")
print("3. Review outputs/ for results")
