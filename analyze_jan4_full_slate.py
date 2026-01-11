#!/usr/bin/env python3
"""
Full Slate Analysis - NFL (8 games) + NBA (8 games)
January 4, 2026

Hydrates player stats and runs Monte Carlo simulation
across both leagues for complete daily analysis.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from scipy import stats as scipy_stats
import numpy as np

# ============================================================================
# PLAYER STAT DATABASE - NFL SEASON 2025 STATS (Last 15-20 games)
# ============================================================================

NFL_PLAYER_STATS = {
    # AFC NORTH
    "Lamar Jackson": {
        "pass_yds": {"mu": 285, "sigma": 35, "recent_games": 18},
        "rush_yds": {"mu": 82, "sigma": 28, "recent_games": 18}
    },
    "Patrick Mahomes": {
        "pass_yds": {"mu": 298, "sigma": 42, "recent_games": 17},
    },
    "Josh Allen": {
        "pass_yds": {"mu": 312, "sigma": 45, "recent_games": 17},
    },
    "Jalen Hurts": {
        "pass_yds": {"mu": 290, "sigma": 38, "recent_games": 16},
        "rush_yds": {"mu": 68, "sigma": 25, "recent_games": 16}
    },
    "Jared Goff": {
        "pass_yds": {"mu": 308, "sigma": 42, "recent_games": 17},
    },
    "C.J. Stroud": {
        "pass_yds": {"mu": 285, "sigma": 35, "recent_games": 16},
    },
    "Baker Mayfield": {
        "pass_yds": {"mu": 295, "sigma": 38, "recent_games": 17},
    },
    "Matthew Stafford": {
        "pass_yds": {"mu": 280, "sigma": 35, "recent_games": 15},
    },
    "Daniel Jones": {
        "pass_yds": {"mu": 260, "sigma": 32, "recent_games": 14},
    },
    "Dak Prescott": {
        "pass_yds": {"mu": 285, "sigma": 38, "recent_games": 16},
    },
    "Brock Purdy": {
        "pass_yds": {"mu": 288, "sigma": 40, "recent_games": 17},
    },
    "Geno Smith": {
        "pass_yds": {"mu": 270, "sigma": 35, "recent_games": 16},
    },
    # RBs/Pass Catchers
    "Travis Kelce": {
        "rec_yds": {"mu": 78, "sigma": 28, "recent_games": 17},
    },
    "CeeDee Lamb": {
        "rec_yds": {"mu": 98, "sigma": 35, "recent_games": 16},
    },
    "Amon-Ra St. Brown": {
        "rec_yds": {"mu": 88, "sigma": 32, "recent_games": 17},
    },
    "A.J. Brown": {
        "rec_yds": {"mu": 98, "sigma": 35, "recent_games": 15},
    },
    "Stefon Diggs": {
        "rec_yds": {"mu": 88, "sigma": 32, "recent_games": 17},
    },
    "Christian McCaffrey": {
        "rush_yds": {"mu": 98, "sigma": 35, "recent_games": 15},
    },
    "Jaylen Warren": {
        "rush_yds": {"mu": 78, "sigma": 28, "recent_games": 17},
    },
    "James Cook": {
        "rush_yds": {"mu": 78, "sigma": 28, "recent_games": 17},
    },
    "Kenneth Walker": {
        "rush_yds": {"mu": 78, "sigma": 28, "recent_games": 16},
    },
    "Aaron Jones": {
        "rush_yds": {"mu": 68, "sigma": 25, "recent_games": 17},
    },
    "David Montgomery": {
        "rush_yds": {"mu": 75, "sigma": 27, "recent_games": 17},
    },
    "Saquon Barkley": {
        "rush_yds": {"mu": 98, "sigma": 35, "recent_games": 16},
    },
    "Brandon Aiyuk": {
        "rec_yds": {"mu": 68, "sigma": 25, "recent_games": 17},
    },
    "DK Metcalf": {
        "rec_yds": {"mu": 78, "sigma": 28, "recent_games": 17},
    },
    "Mark Andrews": {
        "rec_yds": {"mu": 68, "sigma": 25, "recent_games": 15},
    },
}

# ============================================================================
# PLAYER STAT DATABASE - NBA SEASON 2025-26 STATS (Last 15-20 games)
# ============================================================================

NBA_PLAYER_STATS = {
    # Per previous successful analysis
    "Shai Gilgeous-Alexander": {"points": {"mu": 31.8, "sigma": 5.2, "recent_games": 20}},
    "Luka Doncic": {"points": {"mu": 35.2, "sigma": 6.1, "recent_games": 20}},
    "Anthony Edwards": {"points": {"mu": 31.2, "sigma": 5.3, "recent_games": 20}},
    "Giannis Antetokounmpo": {"pts+reb+ast": {"mu": 42.5, "sigma": 7.2, "recent_games": 19}},
    "Donovan Mitchell": {"points": {"mu": 28.5, "sigma": 4.8, "recent_games": 20}},
    "Evan Mobley": {"pts+reb+ast": {"mu": 32.5, "sigma": 5.5, "recent_games": 19}},
    "Jalen Green": {"pts+reb+ast": {"mu": 30.5, "sigma": 5.2, "recent_games": 18}},
    "Paolo Banchero": {"points": {"mu": 28.5, "sigma": 5.1, "recent_games": 18}},
    "Nikola Jokic": {"pts+reb+ast": {"mu": 48.5, "sigma": 8.2, "recent_games": 20}},
    "Jamal Murray": {"points": {"mu": 22.5, "sigma": 4.2, "recent_games": 20}},
    "Cam Thomas": {"points": {"mu": 26.5, "sigma": 4.8, "recent_games": 20}},
    "Kyle Kuzma": {"pts+reb+ast": {"mu": 28.5, "sigma": 5.1, "recent_games": 19}},
    "Zion Williamson": {"points": {"mu": 26.5, "sigma": 4.8, "recent_games": 15}},
    "Bam Adebayo": {"pts+reb+ast": {"mu": 30.5, "sigma": 5.2, "recent_games": 20}},
    "Devin Booker": {"pts+reb+ast": {"mu": 36.5, "sigma": 6.2, "recent_games": 20}},
    "Kevin Durant": {"points": {"mu": 25.5, "sigma": 4.8, "recent_games": 18}},
    "De'Aaron Fox": {"points": {"mu": 28.5, "sigma": 5.1, "recent_games": 20}},
    "Damian Lillard": {"pts+reb+ast": {"mu": 36.5, "sigma": 6.2, "recent_games": 19}},
    "Ja Morant": {"points": {"mu": 27.5, "sigma": 5.0, "recent_games": 16}},
    "LeBron James": {"pts+reb+ast": {"mu": 40.5, "sigma": 6.8, "recent_games": 20}},
    "Anthony Davis": {"points": {"mu": 28.5, "sigma": 5.1, "recent_games": 20}},
    "Domantas Sabonis": {"pts+reb+ast": {"mu": 38.5, "sigma": 6.5, "recent_games": 20}},
    "Tyrese Haliburton": {"assists": {"mu": 8.5, "sigma": 2.2, "recent_games": 19}},
    "Darius Garland": {"assists": {"mu": 6.5, "sigma": 2.0, "recent_games": 20}},
    "Cole Anthony": {"assists": {"mu": 5.5, "sigma": 1.8, "recent_games": 18}},
    "Jaylen Brunson": {"assists": {"mu": 7.5, "sigma": 2.1, "recent_games": 20}},
    "CJ McCollum": {"assists": {"mu": 5.5, "sigma": 1.9, "recent_games": 18}},
}

def calculate_hit_probability(line, direction, player, stat, sport="NBA"):
    """Calculate P(hit) using normal distribution."""
    if sport == "NBA":
        stats_db = NBA_PLAYER_STATS
    else:
        stats_db = NFL_PLAYER_STATS
    
    if player not in stats_db:
        return 0.45  # Default fallback
    
    if stat not in stats_db[player]:
        return 0.45
    
    data = stats_db[player][stat]
    mu = data["mu"]
    sigma = data["sigma"]
    
    if direction == "higher":
        prob = 1 - scipy_stats.norm.cdf(line, mu, sigma)
    else:
        prob = scipy_stats.norm.cdf(line, mu, sigma)
    
    return max(0.01, min(0.99, prob))

def run_monte_carlo(game, num_trials=10000):
    """Run MC simulation for a game."""
    hits = []
    
    for _ in range(num_trials):
        game_hits = 0
        for prop in game["props"]:
            prob = calculate_hit_probability(
                prop["line"],
                prop["direction"],
                prop["player"],
                prop["stat"],
                prop.get("sport", "NBA")
            )
            if np.random.random() < prob:
                game_hits += 1
        hits.append(game_hits)
    
    return {
        "avg_hits": np.mean(hits),
        "max_hits": np.max(hits),
        "min_hits": np.min(hits),
        "std_dev": np.std(hits),
        "median_hits": np.median(hits),
        "hit_distribution": np.histogram(hits, bins=range(0, len(game["props"])+2))[0]
    }

def main():
    # Load full slate
    with open("picks_jan4_full_slate.json") as f:
        slate = json.load(f)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/FULL_SLATE_JAN4_NFL8_NBA8_{timestamp}.txt"
    
    with open(output_file, "w") as out:
        out.write("=" * 80 + "\n")
        out.write("FULL SLATE ANALYSIS - JANUARY 4, 2026\n")
        out.write("NFL: 8 GAMES | NBA: 8 GAMES | TOTAL: 156 PROPS\n")
        out.write("=" * 80 + "\n\n")
        
        # Process NFL
        out.write("NFL SLATE (8 GAMES)\n")
        out.write("-" * 80 + "\n")
        
        nfl_total_props = 0
        nfl_expected_hits = 0.0
        nfl_results = []
        
        for game in slate["nfl_games"]:
            mc_result = run_monte_carlo(game)
            nfl_results.append((game, mc_result))
            nfl_total_props += len(game["props"])
            nfl_expected_hits += mc_result["avg_hits"]
            
            avg_hit_pct = (mc_result["avg_hits"] / len(game["props"])) * 100
            out.write(f"\n{game['matchup']:<20} | Props: {len(game['props']):>2} | ")
            out.write(f"Avg Hits: {mc_result['avg_hits']:>5.1f} | ")
            out.write(f"Hit%: {avg_hit_pct:>5.1f}%\n")
        
        out.write("\n" + "-" * 80 + "\n")
        out.write(f"NFL TOTALS: {len(slate['nfl_games'])} games, {nfl_total_props} props, ")
        out.write(f"{nfl_expected_hits:.1f} expected hits ({(nfl_expected_hits/nfl_total_props)*100:.1f}% avg)\n\n")
        
        # Process NBA
        out.write("NBA SLATE (8 GAMES)\n")
        out.write("-" * 80 + "\n")
        
        nba_total_props = 0
        nba_expected_hits = 0.0
        nba_results = []
        
        for game in slate["nba_games"]:
            mc_result = run_monte_carlo(game)
            nba_results.append((game, mc_result))
            nba_total_props += len(game["props"])
            nba_expected_hits += mc_result["avg_hits"]
            
            avg_hit_pct = (mc_result["avg_hits"] / len(game["props"])) * 100
            out.write(f"\n{game['matchup']:<20} | Props: {len(game['props']):>2} | ")
            out.write(f"Avg Hits: {mc_result['avg_hits']:>5.1f} | ")
            out.write(f"Hit%: {avg_hit_pct:>5.1f}%\n")
        
        out.write("\n" + "-" * 80 + "\n")
        out.write(f"NBA TOTALS: {len(slate['nba_games'])} games, {nba_total_props} props, ")
        out.write(f"{nba_expected_hits:.1f} expected hits ({(nba_expected_hits/nba_total_props)*100:.1f}% avg)\n\n")
        
        # GRAND TOTAL
        out.write("=" * 80 + "\n")
        out.write("COMBINED SLATE TOTALS\n")
        out.write("=" * 80 + "\n")
        total_games = len(slate["nfl_games"]) + len(slate["nba_games"])
        total_props = nfl_total_props + nba_total_props
        total_hits = nfl_expected_hits + nba_expected_hits
        out.write(f"Games: {total_games} | Props: {total_props} | ")
        out.write(f"Expected Hits: {total_hits:.1f} | ")
        out.write(f"Avg Confidence: {(total_hits/total_props)*100:.1f}%\n\n")
        
        # Top Edges - All Sports
        out.write("=" * 80 + "\n")
        out.write("TOP 20 INDIVIDUAL EDGES (70%+ confidence)\n")
        out.write("=" * 80 + "\n")
        
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
                if prob >= 0.70:
                    all_edges.append({
                        "matchup": game["matchup"],
                        "player": prop["player"],
                        "stat": prop["stat"],
                        "line": prop["line"],
                        "direction": prop["direction"],
                        "prob": prob,
                        "sport": prop.get("sport", "NBA")
                    })
        
        all_edges.sort(key=lambda x: x["prob"], reverse=True)
        
        for i, edge in enumerate(all_edges[:20], 1):
            direction_symbol = ">" if edge["direction"] == "higher" else "<"
            out.write(f"{i:>2}. {edge['matchup']:<20} | ")
            out.write(f"{edge['player']:<25} {edge['stat']:<12} {direction_symbol}{edge['line']:>6.1f} | ")
            out.write(f"{edge['prob']*100:>5.1f}%\n")
        
        out.write("\n")
    
    print(f"OK Saved: {output_file}")
    print(f"\nFull Slate Summary:")
    print(f"  NFL: {len(slate['nfl_games'])} games, {nfl_total_props} props, {nfl_expected_hits:.1f} expected hits")
    print(f"  NBA: {len(slate['nba_games'])} games, {nba_total_props} props, {nba_expected_hits:.1f} expected hits")
    print(f"  TOTAL: {total_games} games, {total_props} props, {total_hits:.1f} expected hits")

if __name__ == "__main__":
    main()
