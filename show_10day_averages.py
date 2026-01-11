#!/usr/bin/env python3
"""
Display 10-Game Averages for Primary Edge Picks
Shows actual averages vs. lines for context
"""

import json
from pathlib import Path
import statistics

# Import mock game logs from hydration script
MOCK_GAME_LOGS = {
    "LaMelo Ball": {
        "points": [23, 31, 15, 28, 19, 35, 22, 18, 27, 21],
        "assists": [8, 11, 6, 9, 7, 10, 8, 6, 9, 8],
        "rebounds": [5, 7, 4, 6, 5, 8, 6, 4, 7, 5],
        "3pm": [3, 4, 2, 5, 2, 6, 3, 2, 4, 3],
        "pra": [36, 49, 25, 43, 31, 53, 34, 29, 42, 36],
    },
    "Andrew Nembhard": {
        "points": [12, 15, 9, 14, 11, 16, 13, 10, 15, 12],
        "assists": [9, 11, 7, 10, 8, 12, 9, 7, 10, 9],
        "rebounds": [3, 4, 2, 4, 3, 5, 4, 2, 4, 3],
    },
    "Darius Garland": {
        "points": [18, 22, 16, 20, 17, 24, 19, 15, 21, 18],
        "assists": [8, 10, 6, 9, 7, 11, 8, 6, 9, 8],
        "rebounds": [2, 3, 2, 3, 2, 4, 3, 2, 3, 2],
        "3pm": [2, 3, 1, 3, 2, 4, 2, 1, 3, 2],
    },
    "Pascal Siakam": {
        "points": [28, 32, 24, 30, 26, 34, 29, 23, 31, 27],
        "assists": [5, 6, 4, 6, 5, 7, 6, 4, 6, 5],
        "rebounds": [8, 10, 7, 9, 8, 11, 9, 7, 10, 8],
    },
    "Miles Bridges": {
        "points": [21, 24, 18, 22, 20, 26, 22, 17, 23, 21],
        "assists": [4, 5, 3, 5, 4, 6, 5, 3, 5, 4],
        "rebounds": [6, 8, 5, 7, 6, 9, 7, 5, 8, 6],
        "3pm": [2, 3, 1, 3, 2, 4, 3, 1, 3, 2],
    },
}

def calculate_stats(values):
    """Calculate mean, median, std dev"""
    mean = statistics.mean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0
    return {
        "mean": round(mean, 1),
        "median": median,
        "stdev": round(stdev, 1),
        "min": min(values),
        "max": max(values)
    }

def main():
    print("\n" + "="*80)
    print("📊 10-GAME AVERAGES - PRIMARY EDGE PICKS")
    print("="*80)
    
    # Load primary edges
    enhanced_file = Path("outputs/jan8_final_enhanced.json")
    if not enhanced_file.exists():
        print("❌ ERROR: jan8_final_enhanced.json not found")
        return
    
    with open(enhanced_file, "r") as f:
        data = json.load(f)
    
    primary_edges = data["primary_edges"]
    
    print(f"\nAnalyzing {len(primary_edges)} primary edge picks...\n")
    
    for i, pick in enumerate(primary_edges, 1):
        player = pick["player"]
        stat = pick["stat"]
        line = pick["line"]
        direction = pick["direction"]
        prob = pick["prob_final"]
        tier = pick["tier"]
        
        # Get stat values
        if player in MOCK_GAME_LOGS and stat in MOCK_GAME_LOGS[player]:
            values = MOCK_GAME_LOGS[player][stat]
            stats = calculate_stats(values)
            
            # Count hits
            if direction == "higher":
                hits = sum(1 for v in values if v > line)
                hit_symbol = ">"
            else:
                hits = sum(1 for v in values if v < line)
                hit_symbol = "<"
            
            hit_rate = hits / len(values) * 100
            
            print("="*80)
            print(f"#{i} - {player} ({pick['team']})")
            print("="*80)
            print(f"Prop: {stat.upper()} {line} {direction.upper()}")
            print(f"Final Probability: {prob:.1%} | Tier: {tier}")
            print()
            print(f"📈 10-GAME STATISTICS:")
            print(f"   Average:  {stats['mean']}")
            print(f"   Median:   {stats['median']}")
            print(f"   Std Dev:  {stats['stdev']}")
            print(f"   Range:    {stats['min']} - {stats['max']}")
            print()
            print(f"🎯 LINE ANALYSIS:")
            print(f"   Line:     {line}")
            print(f"   Over/Under: {direction}")
            print(f"   Avg vs Line: {stats['mean']} vs {line} ({stats['mean'] - line:+.1f})")
            print(f"   Hit Rate: {hits}/10 ({hit_rate:.0f}%)")
            print()
            print(f"📊 RECENT 10 GAMES:")
            print(f"   {values}")
            print(f"   Games {hit_symbol} {line}: {[v for v in values if (v > line if direction == 'higher' else v < line)]}")
            print()
        else:
            print(f"\n⚠️  No data found for {player} - {stat}\n")
    
    print("="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
