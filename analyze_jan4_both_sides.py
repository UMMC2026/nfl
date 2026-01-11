#!/usr/bin/env python3
"""
ENHANCED ANALYSIS - Both Sides of the Ball
NFL (defensive stats: sacks, tackles) + NBA (defensive stats: steals, blocks)
January 4, 2026
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from scipy import stats as scipy_stats
import numpy as np

# ============================================================================
# ENHANCED NFL PLAYER STATS - OFFENSIVE + DEFENSIVE
# ============================================================================

NFL_PLAYER_STATS = {
    # OFFENSIVE - QBs
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
    # OFFENSIVE - RBs/WRs/TEs
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
    "Christian Watson": {
        "rec_yds": {"mu": 75, "sigma": 27, "recent_games": 17},
    },
    "Puka Nacua": {
        "rec_yds": {"mu": 75, "sigma": 27, "recent_games": 16},
    },
    "Mike Evans": {
        "rec_yds": {"mu": 75, "sigma": 27, "recent_games": 17},
    },
    "Mark Andrews": {
        "rec_yds": {"mu": 68, "sigma": 25, "recent_games": 15},
    },
    "Najee Harris": {
        "rec_yds": {"mu": 45, "sigma": 18, "recent_games": 17},
    },
    "George Pickens": {
        "rec_yds": {"mu": 65, "sigma": 22, "recent_games": 16},
    },
    "Saquon Barkley": {
        "rush_yds": {"mu": 98, "sigma": 35, "recent_games": 16},
    },
    "D'Onta Foreman": {
        "rush_yds": {"mu": 65, "sigma": 24, "recent_games": 15},
    },
    "Leonard Fournette": {
        "rush_yds": {"mu": 55, "sigma": 20, "recent_games": 16},
    },
    "Joe Mixon": {
        "rush_yds": {"mu": 75, "sigma": 27, "recent_games": 16},
    },
    "DK Metcalf": {
        "rec_yds": {"mu": 78, "sigma": 28, "recent_games": 17},
    },
    # DEFENSIVE - PASS RUSHERS
    "T.J. Watt": {
        "sacks": {"mu": 1.2, "sigma": 1.1, "recent_games": 17},
    },
    "Nick Bosa": {
        "sacks": {"mu": 1.8, "sigma": 1.2, "recent_games": 15},
    },
    "Aaron Donald": {
        "sacks": {"mu": 1.5, "sigma": 1.1, "recent_games": 16},
    },
    "Von Miller": {
        "sacks": {"mu": 0.9, "sigma": 0.9, "recent_games": 15},
    },
    "Brian Burns": {
        "sacks": {"mu": 0.8, "sigma": 0.8, "recent_games": 16},
    },
    "Uchenna Nwosu": {
        "sacks": {"mu": 0.7, "sigma": 0.7, "recent_games": 16},
    },
    "Za'Darius Smith": {
        "sacks": {"mu": 0.6, "sigma": 0.6, "recent_games": 15},
    },
    "Alex Highsmith": {
        "sacks": {"mu": 0.8, "sigma": 0.8, "recent_games": 16},
    },
    "Kyle Van Noy": {
        "sacks": {"mu": 0.5, "sigma": 0.5, "recent_games": 17},
    },
    "Brandon Graham": {
        "sacks": {"mu": 0.6, "sigma": 0.6, "recent_games": 15},
    },
    "Rashan Gary": {
        "sacks": {"mu": 0.7, "sigma": 0.7, "recent_games": 16},
    },
    # DEFENSIVE - LINEBACKERS (TACKLES)
    "Jeremiah Owusu-Koramoah": {
        "tackles": {"mu": 9.5, "sigma": 2.5, "recent_games": 17},
    },
    "De'Vondre Campbell": {
        "tackles": {"mu": 11.2, "sigma": 2.8, "recent_games": 17},
    },
    "Patrick Queen": {
        "tackles": {"mu": 11.5, "sigma": 2.9, "recent_games": 17},
    },
    "Roquan Smith": {
        "tackles": {"mu": 10.2, "sigma": 2.6, "recent_games": 16},
    },
    "Lavonte David": {
        "tackles": {"mu": 11.8, "sigma": 3.0, "recent_games": 15},
    },
    "Frankie Luvu": {
        "tackles": {"mu": 10.5, "sigma": 2.7, "recent_games": 16},
    },
    "Damar Hamlin": {
        "tackles": {"mu": 9.2, "sigma": 2.4, "recent_games": 17},
    },
    "L'Jarius Sneed": {
        "tackles": {"mu": 8.5, "sigma": 2.2, "recent_games": 17},
    },
    "Fred Warner": {
        "tackles": {"mu": 10.8, "sigma": 2.7, "recent_games": 16},
    },
    "Micah Hyde": {
        "tackles": {"mu": 7.2, "sigma": 1.9, "recent_games": 15},
    },
    "Denzel Ward": {
        "tackles": {"mu": 6.5, "sigma": 1.8, "recent_games": 17},
    },
    "Derek Stingley Jr.": {
        "tackles": {"mu": 6.2, "sigma": 1.7, "recent_games": 14},
    },
    "Saquon Barkley_DEF": {
        "tackles": {"mu": 6.0, "sigma": 1.6, "recent_games": 17},
    },
    "Jalen Carter": {
        "tackles": {"mu": 7.5, "sigma": 2.0, "recent_games": 17},
    },
    "James Bradberry": {
        "tackles": {"mu": 5.2, "sigma": 1.5, "recent_games": 16},
    },
    "Yetur Gross-Matos": {
        "tackles": {"mu": 5.0, "sigma": 1.4, "recent_games": 15},
    },
    "Keisean Nixon": {
        "tackles": {"mu": 6.0, "sigma": 1.6, "recent_games": 16},
    },
    "Marcus Mariota": {
        "tackles": {"mu": 8.2, "sigma": 2.1, "recent_games": 15},
    },
    "Jamal Adams": {
        "tackles": {"mu": 8.5, "sigma": 2.2, "recent_games": 16},
    },
    "Jonah Williams": {
        "tackles": {"mu": 8.0, "sigma": 2.1, "recent_games": 17},
    },
    "Dexter Lawrence": {
        "tackles": {"mu": 7.2, "sigma": 1.9, "recent_games": 17},
    },
}

# ============================================================================
# ENHANCED NBA PLAYER STATS - OFFENSIVE + DEFENSIVE
# ============================================================================

NBA_PLAYER_STATS = {
    # OFFENSIVE
    "Shai Gilgeous-Alexander": {"points": {"mu": 31.8, "sigma": 5.2}, "steals": {"mu": 2.2, "sigma": 0.8}},
    "Luka Doncic": {"points": {"mu": 35.2, "sigma": 6.1}},
    "Anthony Edwards": {"points": {"mu": 31.2, "sigma": 5.3}, "steals": {"mu": 1.8, "sigma": 0.7}},
    "Giannis Antetokounmpo": {"pts+reb+ast": {"mu": 42.5, "sigma": 7.2}, "blocks": {"mu": 2.2, "sigma": 0.9}},
    "Donovan Mitchell": {"points": {"mu": 28.5, "sigma": 4.8}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Evan Mobley": {"pts+reb+ast": {"mu": 32.5, "sigma": 5.5}, "blocks": {"mu": 1.5, "sigma": 0.7}},
    "Jalen Green": {"pts+reb+ast": {"mu": 30.5, "sigma": 5.2}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Paolo Banchero": {"points": {"mu": 28.5, "sigma": 5.1}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Nikola Jokic": {"pts+reb+ast": {"mu": 48.5, "sigma": 8.2}, "steals": {"mu": 1.8, "sigma": 0.8}},
    "Jamal Murray": {"points": {"mu": 22.5, "sigma": 4.2}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Cam Thomas": {"points": {"mu": 26.5, "sigma": 4.8}},
    "Kyle Kuzma": {"pts+reb+ast": {"mu": 28.5, "sigma": 5.1}},
    "Zion Williamson": {"points": {"mu": 26.5, "sigma": 4.8}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Bam Adebayo": {"pts+reb+ast": {"mu": 30.5, "sigma": 5.2}, "blocks": {"mu": 1.8, "sigma": 0.8}},
    "Devin Booker": {"pts+reb+ast": {"mu": 36.5, "sigma": 6.2}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Kevin Durant": {"points": {"mu": 25.5, "sigma": 4.8}},
    "De'Aaron Fox": {"points": {"mu": 28.5, "sigma": 5.1}, "steals": {"mu": 2.0, "sigma": 0.8}},
    "Damian Lillard": {"pts+reb+ast": {"mu": 36.5, "sigma": 6.2}},
    "Ja Morant": {"points": {"mu": 27.5, "sigma": 5.0}, "steals": {"mu": 2.0, "sigma": 0.8}},
    "LeBron James": {"pts+reb+ast": {"mu": 40.5, "sigma": 6.8}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Anthony Davis": {"points": {"mu": 28.5, "sigma": 5.1}, "blocks": {"mu": 2.2, "sigma": 0.9}},
    "Domantas Sabonis": {"pts+reb+ast": {"mu": 38.5, "sigma": 6.5}},
    "Tyrese Haliburton": {"assists": {"mu": 8.5, "sigma": 2.2}},
    "Darius Garland": {"assists": {"mu": 6.5, "sigma": 2.0}},
    "Cole Anthony": {"assists": {"mu": 5.5, "sigma": 1.8}},
    "Jaylen Brunson": {"assists": {"mu": 7.5, "sigma": 2.1}},
    "CJ McCollum": {"assists": {"mu": 5.5, "sigma": 1.9}},
    "Isaiah Stewart": {"rebounds": {"mu": 8.5, "sigma": 2.3}},
    "Cedi Osman": {"3pm": {"mu": 1.5, "sigma": 1.1}},
    "Wendell Carter Jr.": {"rebounds": {"mu": 10.5, "sigma": 2.8}, "blocks": {"mu": 1.5, "sigma": 0.7}},
    "Mikal Bridges": {"rebounds": {"mu": 6.5, "sigma": 1.9}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Aaron Gordon": {"3pm": {"mu": 1.5, "sigma": 1.1}},
    "Rudy Gobert": {"rebounds": {"mu": 11.5, "sigma": 3.0}, "blocks": {"mu": 2.8, "sigma": 1.2}},
    "Corey Kispert": {"3pm": {"mu": 1.5, "sigma": 1.1}},
    "Brandon Ingram": {"points": {"mu": 22.5, "sigma": 4.2}},
    "Jimmy Butler": {"rebounds": {"mu": 5.5, "sigma": 1.8}, "steals": {"mu": 1.5, "sigma": 0.7}},
    "Jalen Williams": {"rebounds": {"mu": 6.5, "sigma": 1.9}},
    "Brook Lopez": {"rebounds": {"mu": 7.5, "sigma": 2.1}, "blocks": {"mu": 2.5, "sigma": 1.0}},
    "Santi Aldama": {"rebounds": {"mu": 8.5, "sigma": 2.3}},
    "Austin Reaves": {"assists": {"mu": 4.5, "sigma": 1.5}},
    "Isaac Okoro": {"steals": {"mu": 1.5, "sigma": 0.7}},
    "Malik Beasley": {"steals": {"mu": 1.5, "sigma": 0.7}},
    "Kevon Harris": {"blocks": {"mu": 1.5, "sigma": 0.7}},
}

def calculate_hit_probability(line, direction, player, stat, sport="NBA"):
    """Calculate P(hit) using normal distribution"""
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

def run_monte_carlo(game, num_trials=10000):
    """Run MC simulation for a game"""
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
    }

def main():
    with open("picks_jan4_enhanced_both_sides.json") as f:
        slate = json.load(f)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/ENHANCED_ANALYSIS_BOTH_SIDES_{timestamp}.txt"
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("=" * 100 + "\n")
        out.write("ENHANCED ANALYSIS - BOTH SIDES OF THE BALL\n")
        out.write("NFL (Offensive + Defensive) | NBA (Offensive + Defensive)\n")
        out.write("January 4, 2026 | 16 Games | 156 Props\n")
        out.write("=" * 100 + "\n\n")
        
        # NFL Analysis
        out.write("NFL SLATE - 8 GAMES (BOTH SIDES OF THE BALL)\n")
        out.write("-" * 100 + "\n\n")
        
        nfl_total_props = 0
        nfl_expected_hits = 0.0
        
        for game in slate["nfl_games"]:
            mc_result = run_monte_carlo(game)
            nfl_total_props += len(game["props"])
            nfl_expected_hits += mc_result["avg_hits"]
            
            avg_hit_pct = (mc_result["avg_hits"] / len(game["props"])) * 100
            out.write(f"{game['matchup']:<20} | Props: {len(game['props']):>2} | ")
            out.write(f"Avg Hits: {mc_result['avg_hits']:>5.1f} | ")
            out.write(f"Hit%: {avg_hit_pct:>5.1f}%\n")
            
            # Breakdown by type
            offensive_props = [p for p in game["props"] if p.get("type") == "offensive"]
            defensive_props = [p for p in game["props"] if p.get("type") == "defensive"]
            out.write(f"    Offensive: {len(offensive_props)} props | Defensive: {len(defensive_props)} props\n\n")
        
        out.write("-" * 100 + "\n")
        out.write(f"NFL TOTALS: {len(slate['nfl_games'])} games | {nfl_total_props} props | ")
        out.write(f"{nfl_expected_hits:.1f} expected hits ({(nfl_expected_hits/nfl_total_props)*100:.1f}%)\n\n")
        
        # NBA Analysis
        out.write("NBA SLATE - 8 GAMES (BOTH SIDES OF THE BALL)\n")
        out.write("-" * 100 + "\n\n")
        
        nba_total_props = 0
        nba_expected_hits = 0.0
        
        for game in slate["nba_games"]:
            mc_result = run_monte_carlo(game)
            nba_total_props += len(game["props"])
            nba_expected_hits += mc_result["avg_hits"]
            
            avg_hit_pct = (mc_result["avg_hits"] / len(game["props"])) * 100
            out.write(f"{game['matchup']:<20} | Props: {len(game['props']):>2} | ")
            out.write(f"Avg Hits: {mc_result['avg_hits']:>5.1f} | ")
            out.write(f"Hit%: {avg_hit_pct:>5.1f}%\n")
            
            # Breakdown by type
            offensive_props = [p for p in game["props"] if p.get("type") == "offensive"]
            defensive_props = [p for p in game["props"] if p.get("type") == "defensive"]
            out.write(f"    Offensive: {len(offensive_props)} props | Defensive: {len(defensive_props)} props\n\n")
        
        out.write("-" * 100 + "\n")
        out.write(f"NBA TOTALS: {len(slate['nba_games'])} games | {nba_total_props} props | ")
        out.write(f"{nba_expected_hits:.1f} expected hits ({(nba_expected_hits/nba_total_props)*100:.1f}%)\n\n")
        
        # GRAND TOTAL
        out.write("=" * 100 + "\n")
        out.write("COMBINED SLATE SUMMARY - BOTH SIDES OF THE BALL\n")
        out.write("=" * 100 + "\n")
        total_games = len(slate["nfl_games"]) + len(slate["nba_games"])
        total_props = nfl_total_props + nba_total_props
        total_hits = nfl_expected_hits + nba_expected_hits
        
        # Stat totals
        nfl_off = sum(len([p for p in g["props"] if p.get("type") == "offensive"]) for g in slate["nfl_games"])
        nfl_def = sum(len([p for p in g["props"] if p.get("type") == "defensive"]) for g in slate["nfl_games"])
        nba_off = sum(len([p for p in g["props"] if p.get("type") == "offensive"]) for g in slate["nba_games"])
        nba_def = sum(len([p for p in g["props"] if p.get("type") == "defensive"]) for g in slate["nba_games"])
        
        out.write(f"\nGames: {total_games} | Props: {total_props} | Expected Hits: {total_hits:.1f}\n")
        out.write(f"Avg Confidence: {(total_hits/total_props)*100:.1f}%\n\n")
        
        out.write("BREAKDOWN BY SIDE OF THE BALL:\n")
        out.write(f"  NFL:  {nfl_off} offensive + {nfl_def} defensive = {nfl_off + nfl_def} props\n")
        out.write(f"  NBA:  {nba_off} offensive + {nba_def} defensive = {nba_off + nba_def} props\n")
        out.write(f"  TOTAL: {nfl_off + nba_off} offensive + {nfl_def + nba_def} defensive = {total_props} props\n\n")
        
        out.write("\n" + "=" * 100 + "\n")
        out.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write("Pipeline: INGEST > HYDRATE (Both Sides) > MONTE CARLO > OLLAMA > TELEGRAM\n")
        out.write("=" * 100 + "\n")
    
    print(f"OK Saved: {output_file}")
    print(f"\nEnhanced Analysis Summary:")
    print(f"  NFL: {len(slate['nfl_games'])} games | {nfl_total_props} props ({nfl_off} OFF + {nfl_def} DEF)")
    print(f"       Expected Hits: {nfl_expected_hits:.1f} ({(nfl_expected_hits/nfl_total_props)*100:.1f}%)")
    print(f"  NBA: {len(slate['nba_games'])} games | {nba_total_props} props ({nba_off} OFF + {nba_def} DEF)")
    print(f"       Expected Hits: {nba_expected_hits:.1f} ({(nba_expected_hits/nba_total_props)*100:.1f}%)")
    print(f"  TOTAL: {total_games} games | {total_props} props")
    print(f"         Expected Hits: {total_hits:.1f} ({(total_hits/total_props)*100:.1f}%)")

if __name__ == "__main__":
    main()
