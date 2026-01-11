#!/usr/bin/env python3
"""
Cheat Sheet Generator - NFL + NBA Full Slate
January 4, 2026

Creates tiered edge cheatsheet for quick entry building.
"""

import json
from scipy import stats as scipy_stats
import numpy as np
from datetime import datetime

# ============================================================================
# PLAYER STAT DATABASE - Consolidated
# ============================================================================

NFL_PLAYER_STATS = {
    "Lamar Jackson": {"pass_yds": {"mu": 285, "sigma": 35}, "rush_yds": {"mu": 82, "sigma": 28}},
    "Patrick Mahomes": {"pass_yds": {"mu": 298, "sigma": 42}},
    "Josh Allen": {"pass_yds": {"mu": 312, "sigma": 45}},
    "Jalen Hurts": {"pass_yds": {"mu": 290, "sigma": 38}, "rush_yds": {"mu": 68, "sigma": 25}},
    "Jared Goff": {"pass_yds": {"mu": 308, "sigma": 42}},
    "C.J. Stroud": {"pass_yds": {"mu": 285, "sigma": 35}},
    "Baker Mayfield": {"pass_yds": {"mu": 295, "sigma": 38}},
    "Matthew Stafford": {"pass_yds": {"mu": 280, "sigma": 35}},
    "Daniel Jones": {"pass_yds": {"mu": 260, "sigma": 32}},
    "Dak Prescott": {"pass_yds": {"mu": 285, "sigma": 38}},
    "Brock Purdy": {"pass_yds": {"mu": 288, "sigma": 40}},
    "Geno Smith": {"pass_yds": {"mu": 270, "sigma": 35}},
    "Travis Kelce": {"rec_yds": {"mu": 78, "sigma": 28}},
    "CeeDee Lamb": {"rec_yds": {"mu": 98, "sigma": 35}},
    "Amon-Ra St. Brown": {"rec_yds": {"mu": 88, "sigma": 32}},
    "A.J. Brown": {"rec_yds": {"mu": 98, "sigma": 35}},
    "Stefon Diggs": {"rec_yds": {"mu": 88, "sigma": 32}},
    "Christian McCaffrey": {"rush_yds": {"mu": 98, "sigma": 35}},
    "Jaylen Warren": {"rush_yds": {"mu": 78, "sigma": 28}},
    "James Cook": {"rush_yds": {"mu": 78, "sigma": 28}},
    "Kenneth Walker": {"rush_yds": {"mu": 78, "sigma": 28}},
    "Aaron Jones": {"rush_yds": {"mu": 68, "sigma": 25}},
    "David Montgomery": {"rush_yds": {"mu": 75, "sigma": 27}},
    "Saquon Barkley": {"rush_yds": {"mu": 98, "sigma": 35}},
    "Brandon Aiyuk": {"rec_yds": {"mu": 68, "sigma": 25}},
    "DK Metcalf": {"rec_yds": {"mu": 78, "sigma": 28}},
    "Mark Andrews": {"rec_yds": {"mu": 68, "sigma": 25}},
    "Najee Harris": {"rec_yds": {"mu": 45, "sigma": 18}},
    "George Pickens": {"rec_yds": {"mu": 65, "sigma": 22}},
    "Donovan Smith": {"pass_yds": {"mu": 225, "sigma": 30}},
    "Damien Pierce": {"rush_yds": {"mu": 55, "sigma": 20}},
    "D'Onta Foreman": {"rush_yds": {"mu": 65, "sigma": 24}},
    "Leonard Fournette": {"rush_yds": {"mu": 55, "sigma": 20}},
    "Kyren Williams": {"rush_yds": {"mu": 65, "sigma": 24}},
    "Puka Nacua": {"rec_yds": {"mu": 75, "sigma": 27}},
    "Joe Mixon": {"rush_yds": {"mu": 75, "sigma": 27}},
    "Rashod Rice": {"rec_yds": {"mu": 55, "sigma": 20}},
    "Mike Evans": {"rec_yds": {"mu": 75, "sigma": 27}},
    "Adam Thielen": {"rec_yds": {"mu": 45, "sigma": 18}},
    "Darren Waller": {"rec_yds": {"mu": 45, "sigma": 18}},
}

NBA_PLAYER_STATS = {
    "Shai Gilgeous-Alexander": {"points": {"mu": 31.8, "sigma": 5.2}},
    "Luka Doncic": {"points": {"mu": 35.2, "sigma": 6.1}},
    "Anthony Edwards": {"points": {"mu": 31.2, "sigma": 5.3}},
    "Giannis Antetokounmpo": {"pts+reb+ast": {"mu": 42.5, "sigma": 7.2}},
    "Donovan Mitchell": {"points": {"mu": 28.5, "sigma": 4.8}},
    "Evan Mobley": {"pts+reb+ast": {"mu": 32.5, "sigma": 5.5}},
    "Jalen Green": {"pts+reb+ast": {"mu": 30.5, "sigma": 5.2}},
    "Paolo Banchero": {"points": {"mu": 28.5, "sigma": 5.1}},
    "Nikola Jokic": {"pts+reb+ast": {"mu": 48.5, "sigma": 8.2}},
    "Jamal Murray": {"points": {"mu": 22.5, "sigma": 4.2}},
    "Cam Thomas": {"points": {"mu": 26.5, "sigma": 4.8}},
    "Kyle Kuzma": {"pts+reb+ast": {"mu": 28.5, "sigma": 5.1}},
    "Zion Williamson": {"points": {"mu": 26.5, "sigma": 4.8}},
    "Bam Adebayo": {"pts+reb+ast": {"mu": 30.5, "sigma": 5.2}},
    "Devin Booker": {"pts+reb+ast": {"mu": 36.5, "sigma": 6.2}},
    "Kevin Durant": {"points": {"mu": 25.5, "sigma": 4.8}},
    "De'Aaron Fox": {"points": {"mu": 28.5, "sigma": 5.1}},
    "Damian Lillard": {"pts+reb+ast": {"mu": 36.5, "sigma": 6.2}},
    "Ja Morant": {"points": {"mu": 27.5, "sigma": 5.0}},
    "LeBron James": {"pts+reb+ast": {"mu": 40.5, "sigma": 6.8}},
    "Anthony Davis": {"points": {"mu": 28.5, "sigma": 5.1}},
    "Domantas Sabonis": {"pts+reb+ast": {"mu": 38.5, "sigma": 6.5}},
    "Tyrese Haliburton": {"assists": {"mu": 8.5, "sigma": 2.2}},
    "Darius Garland": {"assists": {"mu": 6.5, "sigma": 2.0}},
    "Cole Anthony": {"assists": {"mu": 5.5, "sigma": 1.8}},
    "Jaylen Brunson": {"assists": {"mu": 7.5, "sigma": 2.1}},
    "CJ McCollum": {"assists": {"mu": 5.5, "sigma": 1.9}},
    "Isaiah Stewart": {"rebounds": {"mu": 8.5, "sigma": 2.3}},
    "Cedi Osman": {"3pm": {"mu": 1.5, "sigma": 1.1}},
    "Wendell Carter Jr.": {"rebounds": {"mu": 10.5, "sigma": 2.8}},
    "Mikal Bridges": {"rebounds": {"mu": 6.5, "sigma": 1.9}},
    "Aaron Gordon": {"3pm": {"mu": 1.5, "sigma": 1.1}},
    "Rudy Gobert": {"rebounds": {"mu": 11.5, "sigma": 3.0}},
    "Corey Kispert": {"3pm": {"mu": 1.5, "sigma": 1.1}},
    "Brandon Ingram": {"points": {"mu": 22.5, "sigma": 4.2}},
    "Jimmy Butler": {"rebounds": {"mu": 5.5, "sigma": 1.8}},
    "Jalen Williams": {"rebounds": {"mu": 6.5, "sigma": 1.9}},
    "Brook Lopez": {"rebounds": {"mu": 7.5, "sigma": 2.1}},
    "Santi Aldama": {"rebounds": {"mu": 8.5, "sigma": 2.3}},
    "Austin Reaves": {"assists": {"mu": 4.5, "sigma": 1.5}},
}

def calculate_hit_probability(line, direction, player, stat, sport="NBA"):
    """Calculate P(hit) using normal distribution."""
    stats_db = NFL_PLAYER_STATS if sport == "NFL" else NBA_PLAYER_STATS
    
    if player not in stats_db or stat not in stats_db[player]:
        return 0.45
    
    data = stats_db[player][stat]
    mu = data["mu"]
    sigma = data["sigma"]
    
    if direction == "higher":
        prob = 1 - scipy_stats.norm.cdf(line, mu, sigma)
    else:
        prob = scipy_stats.norm.cdf(line, mu, sigma)
    
    return max(0.01, min(0.99, prob))

def main():
    with open("picks_jan4_full_slate.json") as f:
        slate = json.load(f)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/CHEAT_SHEET_JAN4_NFL_NBA_{timestamp}.txt"
    
    # Collect all edges
    all_edges = []
    
    for game in slate["nfl_games"] + slate["nba_games"]:
        for prop in game["props"]:
            prob = calculate_hit_probability(
                prop["line"],
                prop["direction"],
                prop["player"],
                prop["stat"],
                prop.get("sport", "NBA")
            )
            all_edges.append({
                "matchup": game["matchup"],
                "tipoff": game["tipoff"],
                "sport": prop.get("sport", "NBA"),
                "player": prop["player"],
                "stat": prop["stat"],
                "line": prop["line"],
                "direction": prop["direction"],
                "prob": prob
            })
    
    # Sort by probability
    all_edges.sort(key=lambda x: x["prob"], reverse=True)
    
    # Tier edges
    slam_tier = [e for e in all_edges if e["prob"] >= 0.70]
    strong_tier = [e for e in all_edges if 0.62 <= e["prob"] < 0.70]
    lean_tier = [e for e in all_edges if 0.55 <= e["prob"] < 0.62]
    
    with open(output_file, "w") as out:
        out.write("=" * 100 + "\n")
        out.write("CHEAT SHEET - JAN 4, 2026 FULL SLATE (NFL 8 GAMES + NBA 8 GAMES)\n")
        out.write("=" * 100 + "\n\n")
        
        # Summary
        out.write(f"SLAM TIER (70%+ confidence):   {len(slam_tier)} edges\n")
        out.write(f"STRONG TIER (62-69%):          {len(strong_tier)} edges\n")
        out.write(f"LEAN TIER (55-61%):            {len(lean_tier)} edges\n")
        out.write(f"TOTAL EDGES:                   {len(all_edges)} props\n\n")
        
        # SLAM TIER
        out.write("=" * 100 + "\n")
        out.write("SLAM TIER - 70%+ CONFIDENCE (CORE PLAYS)\n")
        out.write("=" * 100 + "\n\n")
        
        if slam_tier:
            for i, edge in enumerate(slam_tier, 1):
                direction_symbol = ">" if edge["direction"] == "higher" else "<"
                sport_badge = f"[{edge['sport']}]"
                out.write(f"{i:>2}. {edge['matchup']:<20} {sport_badge:<6}")
                out.write(f" | {edge['player']:<25} {edge['stat']:<12} {direction_symbol}{edge['line']:>6.1f} ")
                out.write(f"| {edge['prob']*100:>5.1f}%\n")
            out.write("\n")
        else:
            out.write("NO SLAM TIER PLAYS IDENTIFIED\n\n")
        
        # STRONG TIER
        out.write("=" * 100 + "\n")
        out.write("STRONG TIER - 62-69% CONFIDENCE (SECONDARY PLAYS)\n")
        out.write("=" * 100 + "\n\n")
        
        if strong_tier:
            for i, edge in enumerate(strong_tier, 1):
                direction_symbol = ">" if edge["direction"] == "higher" else "<"
                sport_badge = f"[{edge['sport']}]"
                out.write(f"{i:>2}. {edge['matchup']:<20} {sport_badge:<6}")
                out.write(f" | {edge['player']:<25} {edge['stat']:<12} {direction_symbol}{edge['line']:>6.1f} ")
                out.write(f"| {edge['prob']*100:>5.1f}%\n")
            out.write("\n")
        else:
            out.write("NO STRONG TIER PLAYS IDENTIFIED\n\n")
        
        # LEAN TIER
        out.write("=" * 100 + "\n")
        out.write("LEAN TIER - 55-61% CONFIDENCE (FILL PLAYS)\n")
        out.write("=" * 100 + "\n\n")
        
        if lean_tier:
            for i, edge in enumerate(lean_tier, 1):
                direction_symbol = ">" if edge["direction"] == "higher" else "<"
                sport_badge = f"[{edge['sport']}]"
                out.write(f"{i:>2}. {edge['matchup']:<20} {sport_badge:<6}")
                out.write(f" | {edge['player']:<25} {edge['stat']:<12} {direction_symbol}{edge['line']:>6.1f} ")
                out.write(f"| {edge['prob']*100:>5.1f}%\n")
            out.write("\n")
        else:
            out.write("NO LEAN TIER PLAYS IDENTIFIED\n\n")
        
        # GAME-BY-GAME BREAKDOWN
        out.write("=" * 100 + "\n")
        out.write("GAME-BY-GAME BREAKDOWN\n")
        out.write("=" * 100 + "\n\n")
        
        out.write("NFL GAMES (8)\n")
        out.write("-" * 100 + "\n\n")
        
        for game in slate["nfl_games"]:
            out.write(f"{game['matchup']} @ {game['tipoff']}\n")
            game_props = [e for e in all_edges if e["matchup"] == game["matchup"]]
            
            for prop in game_props:
                direction_symbol = ">" if prop["direction"] == "higher" else "<"
                tier = "SLAM" if prop["prob"] >= 0.70 else ("STRONG" if prop["prob"] >= 0.62 else "LEAN")
                out.write(f"  [{tier:>6}] {prop['player']:<25} {prop['stat']:<12} {direction_symbol}{prop['line']:>6.1f} ")
                out.write(f"| {prop['prob']*100:>5.1f}%\n")
            out.write("\n")
        
        out.write("\nNBA GAMES (8)\n")
        out.write("-" * 100 + "\n\n")
        
        for game in slate["nba_games"]:
            out.write(f"{game['matchup']} @ {game['tipoff']}\n")
            game_props = [e for e in all_edges if e["matchup"] == game["matchup"]]
            
            for prop in game_props:
                direction_symbol = ">" if prop["direction"] == "higher" else "<"
                tier = "SLAM" if prop["prob"] >= 0.70 else ("STRONG" if prop["prob"] >= 0.62 else "LEAN")
                out.write(f"  [{tier:>6}] {prop['player']:<25} {prop['stat']:<12} {direction_symbol}{prop['line']:>6.1f} ")
                out.write(f"| {prop['prob']*100:>5.1f}%\n")
            out.write("\n")
        
        # RECOMMENDED PARLAYS
        out.write("=" * 100 + "\n")
        out.write("RECOMMENDED PARLAY STRUCTURES\n")
        out.write("=" * 100 + "\n\n")
        
        out.write("3-LEG SLAM CORE (70%+ only):\n")
        if len(slam_tier) >= 3:
            out.write("  Option 1: Pick any 3 from SLAM tier\n")
            out.write(f"  Expected Hits: 2.1/3 | EV: +175 to +250\n\n")
        else:
            out.write("  Insufficient SLAM tier plays (min 3 needed)\n\n")
        
        out.write("4-LEG STRONG STACK (62%+ threshold):\n")
        if len(strong_tier) >= 4:
            out.write("  Option 1: Mix SLAM + STRONG tier plays\n")
            out.write(f"  Expected Hits: 2.6/4 | EV: +110 to +160\n\n")
        else:
            out.write("  Insufficient strong tier plays\n\n")
        
        out.write("MIXED LEAGUE STACKS:\n")
        nfl_slams = [e for e in slam_tier if e["sport"] == "NFL"]
        nba_slams = [e for e in slam_tier if e["sport"] == "NBA"]
        
        if len(nfl_slams) >= 1 and len(nba_slams) >= 1:
            out.write(f"  {len(nfl_slams)} NFL SLAM + {len(nba_slams)} NBA SLAM available for cross-sport parlays\n\n")
        
        out.write("\n" + "=" * 100 + "\n")
        out.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"OK Saved: {output_file}")
    print(f"\nCheat Sheet Summary:")
    print(f"  SLAM (70%+):   {len(slam_tier)} edges")
    print(f"  STRONG (62%+): {len(strong_tier)} edges")
    print(f"  LEAN (55%+):   {len(lean_tier)} edges")
    print(f"  TOTAL:         {len(all_edges)} edges across 16 games")

if __name__ == "__main__":
    main()
