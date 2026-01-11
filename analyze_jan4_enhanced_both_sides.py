#!/usr/bin/env python3
"""
Enhanced Both-Sides Analysis - No scipy dependency
Using simple probability calculations
"""

import json
from datetime import datetime
from pathlib import Path
import numpy as np

# ============================================================================
# ENHANCED PLAYER STAT DATABASE - BOTH SIDES
# ============================================================================

NFL_PLAYER_STATS = {
    # OFFENSIVE STATS
    "Lamar Jackson": {"pass_yds": {"mu": 285, "sigma": 35}, "rush_yds": {"mu": 82, "sigma": 28}},
    "Patrick Mahomes": {"pass_yds": {"mu": 298, "sigma": 42}},
    "Josh Allen": {"pass_yds": {"mu": 312, "sigma": 45}},
    "Jalen Hurts": {"pass_yds": {"mu": 290, "sigma": 38}, "rush_yds": {"mu": 68, "sigma": 25}},
    "Jared Goff": {"pass_yds": {"mu": 308, "sigma": 42}},
    "C.J. Stroud": {"pass_yds": {"mu": 285, "sigma": 35}},
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
    "Christian Watson": {"rec_yds": {"mu": 75, "sigma": 27}},
    "Puka Nacua": {"rec_yds": {"mu": 75, "sigma": 27}},
    "Mike Evans": {"rec_yds": {"mu": 75, "sigma": 27}},
    "Mark Andrews": {"rec_yds": {"mu": 68, "sigma": 25}},
    "Najee Harris": {"rec_yds": {"mu": 45, "sigma": 18}},
    "George Pickens": {"rec_yds": {"mu": 65, "sigma": 22}},
    "Saquon Barkley": {"rush_yds": {"mu": 98, "sigma": 35}},
    "D'Onta Foreman": {"rush_yds": {"mu": 65, "sigma": 24}},
    "Leonard Fournette": {"rush_yds": {"mu": 55, "sigma": 20}},
    "Joe Mixon": {"rush_yds": {"mu": 75, "sigma": 27}},
    "DK Metcalf": {"rec_yds": {"mu": 78, "sigma": 28}},
    
    # DEFENSIVE STATS
    "T.J. Watt": {"sacks": {"mu": 1.2, "sigma": 1.1}},
    "Nick Bosa": {"sacks": {"mu": 1.8, "sigma": 1.2}},
    "Aaron Donald": {"sacks": {"mu": 1.5, "sigma": 1.1}},
    "Von Miller": {"sacks": {"mu": 0.9, "sigma": 0.9}},
    "Brian Burns": {"sacks": {"mu": 0.8, "sigma": 0.8}},
    "Uchenna Nwosu": {"sacks": {"mu": 0.7, "sigma": 0.7}},
    "Za'Darius Smith": {"sacks": {"mu": 0.6, "sigma": 0.6}},
    "Alex Highsmith": {"sacks": {"mu": 0.8, "sigma": 0.8}},
    "Jeremiah Owusu-Koramoah": {"tackles": {"mu": 9.5, "sigma": 2.5}},
    "De'Vondre Campbell": {"tackles": {"mu": 11.2, "sigma": 2.8}},
    "Patrick Queen": {"tackles": {"mu": 11.5, "sigma": 2.9}},
    "Roquan Smith": {"tackles": {"mu": 10.2, "sigma": 2.6}},
    "Lavonte David": {"tackles": {"mu": 11.8, "sigma": 3.0}},
    "Frankie Luvu": {"tackles": {"mu": 10.5, "sigma": 2.7}},
    "Damar Hamlin": {"tackles": {"mu": 9.2, "sigma": 2.4}},
    "L'Jarius Sneed": {"tackles": {"mu": 8.5, "sigma": 2.2}},
    "Fred Warner": {"tackles": {"mu": 10.8, "sigma": 2.7}},
    "Micah Hyde": {"tackles": {"mu": 7.2, "sigma": 1.9}},
    "Denzel Ward": {"tackles": {"mu": 6.5, "sigma": 1.8}},
    "Derek Stingley Jr.": {"tackles": {"mu": 6.2, "sigma": 1.7}},
    "Jalen Carter": {"tackles": {"mu": 7.5, "sigma": 2.0}},
    "James Bradberry": {"tackles": {"mu": 5.2, "sigma": 1.5}},
    "Keisean Nixon": {"tackles": {"mu": 6.0, "sigma": 1.6}},
    "Marcus Mariota": {"tackles": {"mu": 8.2, "sigma": 2.1}},
    "Jamal Adams": {"tackles": {"mu": 8.5, "sigma": 2.2}},
    "Jonah Williams": {"tackles": {"mu": 8.0, "sigma": 2.1}},
    "Dexter Lawrence": {"tackles": {"mu": 7.2, "sigma": 1.9}},
}

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
}

def normal_cdf_approx(x, mu, sigma):
    """Simple normal CDF approximation"""
    z = (x - mu) / sigma if sigma > 0 else 0
    # Using error function approximation
    return 0.5 * (1 + np.tanh(0.7978845608 * (z + 0.044715 * z**3)))

def calculate_hit_probability(line, direction, player, stat, sport="NBA"):
    """Calculate P(hit) using normal approximation"""
    stats_db = NFL_PLAYER_STATS if sport == "NFL" else NBA_PLAYER_STATS
    
    if player not in stats_db or stat not in stats_db[player]:
        return 0.45
    
    data = stats_db[player][stat]
    mu = data["mu"]
    sigma = data["sigma"]
    
    if direction == "higher":
        prob = 1 - normal_cdf_approx(line, mu, sigma)
    else:
        prob = normal_cdf_approx(line, mu, sigma)
    
    return max(0.01, min(0.99, prob))

def run_monte_carlo_simple(game, num_trials=5000):
    """Run MC simulation (simplified for speed)"""
    hits_list = []
    
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
        hits_list.append(game_hits)
    
    hits = np.array(hits_list)
    return {
        "avg_hits": np.mean(hits),
        "std_dev": np.std(hits),
    }

def main():
    with open("picks_jan4_enhanced_both_sides.json") as f:
        slate = json.load(f)
    
    Path("outputs").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/ENHANCED_BOTH_SIDES_{timestamp}.txt"
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("=" * 100 + "\n")
        out.write("ENHANCED ANALYSIS - BOTH SIDES OF THE BALL\n")
        out.write("NFL (Offensive + Defensive) | NBA (Offensive + Defensive)\n")
        out.write("January 4, 2026 | 16 Games | Both Sides Coverage\n")
        out.write("=" * 100 + "\n\n")
        
        # NFL Analysis
        out.write("NFL SLATE - 8 GAMES (BOTH SIDES OF THE BALL)\n")
        out.write("-" * 100 + "\n\n")
        
        nfl_total_props = 0
        nfl_expected_hits = 0.0
        
        for game in slate["nfl_games"]:
            mc_result = run_monte_carlo_simple(game)
            nfl_total_props += len(game["props"])
            nfl_expected_hits += mc_result["avg_hits"]
            
            avg_hit_pct = (mc_result["avg_hits"] / len(game["props"])) * 100 if game["props"] else 0
            out.write(f"{game['matchup']:<20} | Props: {len(game['props']):>2} | Avg Hits: {mc_result['avg_hits']:>5.1f}\n")
            
            # Stat breakdown
            offensive_props = [p for p in game["props"] if p.get("type") == "offensive"]
            defensive_props = [p for p in game["props"] if p.get("type") == "defensive"]
            out.write(f"    Offensive: {len(offensive_props)} | Defensive: {len(defensive_props)}\n\n")
        
        out.write("-" * 100 + "\n")
        out.write(f"NFL TOTALS: {len(slate['nfl_games'])} games | {nfl_total_props} props | ")
        out.write(f"{nfl_expected_hits:.1f} expected hits\n\n")
        
        # NBA Analysis
        out.write("NBA SLATE - 8 GAMES (BOTH SIDES OF THE BALL)\n")
        out.write("-" * 100 + "\n\n")
        
        nba_total_props = 0
        nba_expected_hits = 0.0
        
        for game in slate["nba_games"]:
            mc_result = run_monte_carlo_simple(game)
            nba_total_props += len(game["props"])
            nba_expected_hits += mc_result["avg_hits"]
            
            avg_hit_pct = (mc_result["avg_hits"] / len(game["props"])) * 100 if game["props"] else 0
            out.write(f"{game['matchup']:<20} | Props: {len(game['props']):>2} | Avg Hits: {mc_result['avg_hits']:>5.1f}\n")
            
            # Stat breakdown
            offensive_props = [p for p in game["props"] if p.get("type") == "offensive"]
            defensive_props = [p for p in game["props"] if p.get("type") == "defensive"]
            out.write(f"    Offensive: {len(offensive_props)} | Defensive: {len(defensive_props)}\n\n")
        
        out.write("-" * 100 + "\n")
        out.write(f"NBA TOTALS: {len(slate['nba_games'])} games | {nba_total_props} props | ")
        out.write(f"{nba_expected_hits:.1f} expected hits\n\n")
        
        # Summary
        out.write("=" * 100 + "\n")
        total_games = len(slate["nfl_games"]) + len(slate["nba_games"])
        total_props = nfl_total_props + nba_total_props
        total_hits = nfl_expected_hits + nba_expected_hits
        
        nfl_off = sum(len([p for p in g["props"] if p.get("type") == "offensive"]) for g in slate["nfl_games"])
        nfl_def = sum(len([p for p in g["props"] if p.get("type") == "defensive"]) for g in slate["nfl_games"])
        nba_off = sum(len([p for p in g["props"] if p.get("type") == "offensive"]) for g in slate["nba_games"])
        nba_def = sum(len([p for p in g["props"] if p.get("type") == "defensive"]) for g in slate["nba_games"])
        
        out.write(f"\nGAMES: {total_games} | TOTAL PROPS: {total_props}\n")
        out.write(f"EXPECTED HITS: {total_hits:.1f} ({(total_hits/total_props)*100:.1f}%)\n\n")
        out.write(f"NFL: {nfl_off} OFF + {nfl_def} DEF | NBA: {nba_off} OFF + {nba_def} DEF\n")
        
    print(f"✅ OK Saved: {output_file}")
    print(f"\n📊 Enhanced Both-Sides Analysis:")
    print(f"   NFL: {len(slate['nfl_games'])} games | {nfl_total_props} props ({nfl_off} OFF + {nfl_def} DEF)")
    print(f"       Expected: {nfl_expected_hits:.1f} hits")
    print(f"   NBA: {len(slate['nba_games'])} games | {nba_total_props} props ({nba_off} OFF + {nba_def} DEF)")
    print(f"       Expected: {nba_expected_hits:.1f} hits")
    print(f"   TOTAL: {total_props} props → {total_hits:.1f} expected hits ({(total_hits/total_props)*100:.1f}%)")
    print(f"\n📄 Output: {output_file}")

if __name__ == "__main__":
    main()
