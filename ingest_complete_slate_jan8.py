#!/usr/bin/env python3
"""
Complete Slate Ingestion - January 8, 2026 (Updated List)
All 4 games with full player props
"""

import json
from pathlib import Path
from datetime import datetime

# Complete slate data
SLATE_DATA = {
    "date": "2026-01-08",
    "games": [
        {
            "matchup": "IND@CHA",
            "time": "6:00PM CST",
            "away": "IND",
            "home": "CHA"
        },
        {
            "matchup": "CLE@MIN",
            "time": "7:00PM CST",
            "away": "CLE",
            "home": "MIN"
        },
        {
            "matchup": "MIA@CHI",
            "time": "7:00PM CST",
            "away": "MIA",
            "home": "CHI"
        },
        {
            "matchup": "DAL@UTA",
            "time": "8:00PM CST",
            "away": "DAL",
            "home": "UTA"
        }
    ],
    "picks": [
        # IND @ CHA - 6:00PM CST
        
        # LaMelo Ball (CHA)
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "points", "line": 17.5, "direction": "higher"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "pra", "line": 29.5, "direction": "higher"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "rebounds", "line": 4.5, "direction": "higher"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "assists", "line": 6.5, "direction": "higher"},
        {"player": "LaMelo Ball", "team": "CHA", "opponent": "IND", "stat": "3pm", "line": 2.5, "direction": "higher"},
        
        # Brandon Miller (CHA)
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "points", "line": 20.5, "direction": "higher"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "pra", "line": 28.5, "direction": "higher"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "rebounds", "line": 4.5, "direction": "higher"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "assists", "line": 2.5, "direction": "higher"},
        {"player": "Brandon Miller", "team": "CHA", "opponent": "IND", "stat": "3pm", "line": 2.5, "direction": "higher"},
        
        # Andrew Nembhard (IND)
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "points", "line": 18.5, "direction": "higher"},
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "pra", "line": 28.5, "direction": "higher"},
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "rebounds", "line": 2.5, "direction": "higher"},
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "assists", "line": 7.5, "direction": "higher"},
        {"player": "Andrew Nembhard", "team": "IND", "opponent": "CHA", "stat": "3pm", "line": 1.5, "direction": "higher"},
        
        # Pascal Siakam (IND)
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "points", "line": 25.5, "direction": "higher"},
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "pra", "line": 37.5, "direction": "higher"},
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "rebounds", "line": 6.5, "direction": "higher"},
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "assists", "line": 4.5, "direction": "higher"},
        {"player": "Pascal Siakam", "team": "IND", "opponent": "CHA", "stat": "3pm", "line": 1.5, "direction": "higher"},
        
        # Miles Bridges (CHA)
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "points", "line": 18.5, "direction": "higher"},
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "pra", "line": 28.5, "direction": "higher"},
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "rebounds", "line": 6.5, "direction": "higher"},
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "assists", "line": 3.5, "direction": "higher"},
        {"player": "Miles Bridges", "team": "CHA", "opponent": "IND", "stat": "3pm", "line": 1.5, "direction": "higher"},
        
        # CLE @ MIN - 7:00PM CST
        
        # Anthony Edwards (MIN)
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 30.5, "direction": "higher"},
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "pra", "line": 39.5, "direction": "higher"},
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 5.5, "direction": "higher"},
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "assists", "line": 3.5, "direction": "higher"},
        {"player": "Anthony Edwards", "team": "MIN", "opponent": "CLE", "stat": "3pm", "line": 3.5, "direction": "higher"},
        
        # Donovan Mitchell (CLE)
        {"player": "Donovan Mitchell", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 29.5, "direction": "higher"},
        {"player": "Donovan Mitchell", "team": "CLE", "opponent": "MIN", "stat": "pra", "line": 40.5, "direction": "higher"},
        {"player": "Donovan Mitchell", "team": "CLE", "opponent": "MIN", "stat": "rebounds", "line": 4.5, "direction": "higher"},
        {"player": "Donovan Mitchell", "team": "CLE", "opponent": "MIN", "stat": "assists", "line": 5.5, "direction": "higher"},
        
        # Darius Garland (CLE)
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 18.5, "direction": "higher"},
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "pra", "line": 27.5, "direction": "higher"},
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "rebounds", "line": 2.5, "direction": "higher"},
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "assists", "line": 6.5, "direction": "higher"},
        {"player": "Darius Garland", "team": "CLE", "opponent": "MIN", "stat": "3pm", "line": 2.5, "direction": "higher"},
        
        # Julius Randle (MIN)
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 21.5, "direction": "higher"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "pra", "line": 35.5, "direction": "higher"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 7.5, "direction": "higher"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "assists", "line": 5.5, "direction": "higher"},
        {"player": "Julius Randle", "team": "MIN", "opponent": "CLE", "stat": "3pm", "line": 1.5, "direction": "higher"},
        
        # Evan Mobley (CLE)
        {"player": "Evan Mobley", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 17.5, "direction": "higher"},
        {"player": "Evan Mobley", "team": "CLE", "opponent": "MIN", "stat": "pra", "line": 31.5, "direction": "higher"},
        {"player": "Evan Mobley", "team": "CLE", "opponent": "MIN", "stat": "rebounds", "line": 8.5, "direction": "higher"},
        {"player": "Evan Mobley", "team": "CLE", "opponent": "MIN", "stat": "assists", "line": 4.5, "direction": "higher"},
        
        # Jarrett Allen (CLE)
        {"player": "Jarrett Allen", "team": "CLE", "opponent": "MIN", "stat": "points", "line": 13.5, "direction": "higher"},
        {"player": "Jarrett Allen", "team": "CLE", "opponent": "MIN", "stat": "pra", "line": 24.5, "direction": "higher"},
        {"player": "Jarrett Allen", "team": "CLE", "opponent": "MIN", "stat": "rebounds", "line": 8.5, "direction": "higher"},
        {"player": "Jarrett Allen", "team": "CLE", "opponent": "MIN", "stat": "assists", "line": 2.5, "direction": "higher"},
        
        # Naz Reid (MIN)
        {"player": "Naz Reid", "team": "MIN", "opponent": "CLE", "stat": "points", "line": 14.5, "direction": "higher"},
        {"player": "Naz Reid", "team": "MIN", "opponent": "CLE", "stat": "pra", "line": 23.5, "direction": "higher"},
        {"player": "Naz Reid", "team": "MIN", "opponent": "CLE", "stat": "rebounds", "line": 6.5, "direction": "higher"},
        {"player": "Naz Reid", "team": "MIN", "opponent": "CLE", "stat": "assists", "line": 2.5, "direction": "higher"},
        
        # MIA @ CHI - 7:00PM CST
        
        # Bam Adebayo (MIA)
        {"player": "Bam Adebayo", "team": "MIA", "opponent": "CHI", "stat": "points", "line": 16.5, "direction": "higher"},
        {"player": "Bam Adebayo", "team": "MIA", "opponent": "CHI", "stat": "pra", "line": 29.5, "direction": "higher"},
        {"player": "Bam Adebayo", "team": "MIA", "opponent": "CHI", "stat": "rebounds", "line": 10.5, "direction": "higher"},
        {"player": "Bam Adebayo", "team": "MIA", "opponent": "CHI", "stat": "assists", "line": 2.5, "direction": "higher"},
        
        # Tyler Herro (MIA)
        {"player": "Tyler Herro", "team": "MIA", "opponent": "CHI", "stat": "points", "line": 20.5, "direction": "higher"},
        {"player": "Tyler Herro", "team": "MIA", "opponent": "CHI", "stat": "pra", "line": 28.5, "direction": "higher"},
        {"player": "Tyler Herro", "team": "MIA", "opponent": "CHI", "stat": "rebounds", "line": 4.5, "direction": "higher"},
        {"player": "Tyler Herro", "team": "MIA", "opponent": "CHI", "stat": "assists", "line": 3.5, "direction": "higher"},
        
        # Norman Powell (MIA)
        {"player": "Norman Powell", "team": "MIA", "opponent": "CHI", "stat": "points", "line": 22.5, "direction": "higher"},
        {"player": "Norman Powell", "team": "MIA", "opponent": "CHI", "stat": "pra", "line": 28.5, "direction": "higher"},
        {"player": "Norman Powell", "team": "MIA", "opponent": "CHI", "stat": "rebounds", "line": 3.5, "direction": "higher"},
        {"player": "Norman Powell", "team": "MIA", "opponent": "CHI", "stat": "assists", "line": 2.5, "direction": "higher"},
        
        # Nikola Vucevic (CHI)
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "points", "line": 18.5, "direction": "higher"},
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "pra", "line": 33.5, "direction": "higher"},
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "rebounds", "line": 10.5, "direction": "higher"},
        {"player": "Nikola Vucevic", "team": "CHI", "opponent": "MIA", "stat": "assists", "line": 3.5, "direction": "higher"},
        
        # Coby White (CHI)
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "points", "line": 17.5, "direction": "higher"},
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "pra", "line": 24.5, "direction": "higher"},
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "rebounds", "line": 3.5, "direction": "higher"},
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "assists", "line": 3.5, "direction": "higher"},
        {"player": "Coby White", "team": "CHI", "opponent": "MIA", "stat": "3pm", "line": 2.5, "direction": "higher"},
        
        # DAL @ UTA - 8:00PM CST
        
        # Anthony Davis (DAL)
        {"player": "Anthony Davis", "team": "DAL", "opponent": "UTA", "stat": "points", "line": 25.5, "direction": "higher"},
        {"player": "Anthony Davis", "team": "DAL", "opponent": "UTA", "stat": "pra", "line": 41.5, "direction": "higher"},
        {"player": "Anthony Davis", "team": "DAL", "opponent": "UTA", "stat": "rebounds", "line": 12.5, "direction": "higher"},
        {"player": "Anthony Davis", "team": "DAL", "opponent": "UTA", "stat": "assists", "line": 3.5, "direction": "higher"},
        
        # Cooper Flagg (DAL)
        {"player": "Cooper Flagg", "team": "DAL", "opponent": "UTA", "stat": "points", "line": 20.5, "direction": "higher"},
        {"player": "Cooper Flagg", "team": "DAL", "opponent": "UTA", "stat": "pra", "line": 34.5, "direction": "higher"},
        {"player": "Cooper Flagg", "team": "DAL", "opponent": "UTA", "stat": "rebounds", "line": 6.5, "direction": "higher"},
        {"player": "Cooper Flagg", "team": "DAL", "opponent": "UTA", "stat": "assists", "line": 5.5, "direction": "higher"},
        
        # Klay Thompson (DAL)
        {"player": "Klay Thompson", "team": "DAL", "opponent": "UTA", "stat": "points", "line": 12.5, "direction": "higher"},
        {"player": "Klay Thompson", "team": "DAL", "opponent": "UTA", "stat": "pra", "line": 16.5, "direction": "higher"},
        {"player": "Klay Thompson", "team": "DAL", "opponent": "UTA", "stat": "rebounds", "line": 2.5, "direction": "higher"},
        {"player": "Klay Thompson", "team": "DAL", "opponent": "UTA", "stat": "assists", "line": 1.5, "direction": "higher"},
    ]
}

def main():
    print("\n" + "="*80)
    print("📥 COMPLETE SLATE INGESTION - JANUARY 8, 2026 (UPDATED)")
    print("="*80)
    
    picks = SLATE_DATA["picks"]
    games = SLATE_DATA["games"]
    
    # Count picks per game
    game_counts = {}
    for pick in picks:
        matchup = f"{pick['opponent']}@{pick['team']}" if pick['team'] == picks[0]['team'] else f"{pick['team']}@{pick['opponent']}"
        # Normalize matchup
        for game in games:
            if pick['team'] in game['matchup'] and pick['opponent'] in game['matchup']:
                matchup = game['matchup']
                break
        game_counts[matchup] = game_counts.get(matchup, 0) + 1
    
    # Count unique players
    unique_players = len(set(p['player'] for p in picks))
    
    # Count by stat type
    stat_counts = {}
    for pick in picks:
        stat = pick['stat']
        stat_counts[stat] = stat_counts.get(stat, 0) + 1
    
    print(f"\n📊 SLATE OVERVIEW:")
    print(f"   Total picks: {len(picks)}")
    print(f"   Unique players: {unique_players}")
    print(f"   Games: {len(games)}")
    print()
    
    print("🎮 PICKS BY GAME:")
    for game in games:
        matchup = game['matchup']
        count = game_counts.get(matchup, 0)
        time = game['time']
        print(f"   {matchup} ({time}): {count} props")
    print()
    
    print("📈 PICKS BY STAT TYPE:")
    for stat, count in sorted(stat_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {stat}: {count}")
    
    # Save to file
    output_file = Path("outputs/jan8_complete_slate.json")
    with open(output_file, "w") as f:
        json.dump(SLATE_DATA, f, indent=2)
    
    print(f"\n💾 Saved to: {output_file}")
    
    print("\n" + "="*80)
    print("✅ INGESTION COMPLETE")
    print("="*80)
    print(f"\n▶️  Next: Run full hydration + enhancement + Monte Carlo")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
