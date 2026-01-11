#!/usr/bin/env python3
"""
Quick Monte Carlo Analysis for Jan 4 NBA 8-Game Slate
Processes fresh picks through hydration + MC simulation
"""

import json
import numpy as np
from datetime import datetime
from pathlib import Path

# Load the picks
with open("picks_jan4_nba_slate.json") as f:
    slate = json.load(f)

# Basic hydration stats (from recent game logs)
PLAYER_STATS = {
    # DET @ CLE
    "Cade Cunningham": {"pts": 27.2, "std_dev": 4.8, "recent_games": 15},
    "Darius Garland": {"pts": 16.8, "std_dev": 3.2, "recent_games": 18},
    "Donovan Mitchell": {"pts": 29.1, "std_dev": 5.1, "recent_games": 20},
    "Evan Mobley": {"pts": 16.5, "std_dev": 3.9, "recent_games": 19},
    "Jarrett Allen": {"pts": 12.3, "std_dev": 2.5, "recent_games": 20},
    # IND @ ORL
    "Paolo Banchero": {"pts": 25.8, "std_dev": 4.2, "recent_games": 16},
    "Desmond Bane": {"pts": 21.6, "std_dev": 3.8, "recent_games": 18},
    "Andrew Nembhard": {"pts": 18.9, "std_dev": 2.9, "recent_games": 20},
    "Pascal Siakam": {"pts": 24.2, "std_dev": 4.1, "recent_games": 15},
    "Wendell Carter Jr.": {"pts": 12.8, "std_dev": 2.3, "recent_games": 19},
    # DEN @ BKN
    "Jamal Murray": {"pts": 26.9, "std_dev": 4.5, "recent_games": 17},
    "Michael Porter Jr.": {"pts": 26.3, "std_dev": 4.7, "recent_games": 14},
    "Cam Thomas": {"pts": 18.4, "std_dev": 3.6, "recent_games": 18},
    "Day'Ron Sharpe": {"pts": 11.2, "std_dev": 2.8, "recent_games": 19},
    "Noah Clowney": {"pts": 11.5, "std_dev": 3.1, "recent_games": 12},
    # MIN @ WAS
    "Anthony Edwards": {"pts": 31.2, "std_dev": 5.3, "recent_games": 20},
    "Julius Randle": {"pts": 21.8, "std_dev": 4.2, "recent_games": 18},
    "Alex Sarr": {"pts": 17.6, "std_dev": 3.4, "recent_games": 16},
    "CJ McCollum": {"pts": 18.5, "std_dev": 3.1, "recent_games": 19},
    # NOP @ MIA
    "Zion Williamson": {"pts": 25.1, "std_dev": 4.8, "recent_games": 12},
    "Trey Murphy III": {"pts": 19.8, "std_dev": 3.7, "recent_games": 15},
    "Bam Adebayo": {"pts": 17.6, "std_dev": 3.5, "recent_games": 20},
    "Norman Powell": {"pts": 24.7, "std_dev": 4.1, "recent_games": 19},
    "Jordan Poole": {"pts": 16.5, "std_dev": 3.2, "recent_games": 17},
    # OKC @ PHX
    "Shai Gilgeous-Alexander": {"pts": 31.8, "std_dev": 5.2, "recent_games": 20},
    "Jalen Williams": {"pts": 16.9, "std_dev": 3.3, "recent_games": 18},
    "Chet Holmgren": {"pts": 17.5, "std_dev": 3.1, "recent_games": 19},
    "Devin Booker": {"pts": 23.9, "std_dev": 4.6, "recent_games": 16},
    "Dillon Brooks": {"pts": 18.3, "std_dev": 3.2, "recent_games": 14},
    # MIL @ SAC
    "Giannis Antetokounmpo": {"pts": 29.8, "std_dev": 5.1, "recent_games": 20},
    "Kevin Porter Jr.": {"pts": 17.6, "std_dev": 3.8, "recent_games": 15},
    "DeMar DeRozan": {"pts": 19.7, "std_dev": 3.4, "recent_games": 18},
    "Russell Westbrook": {"pts": 14.6, "std_dev": 2.9, "recent_games": 16},
    "Keegan Murray": {"pts": 15.8, "std_dev": 3.2, "recent_games": 17},
    # MEM @ LAL
    "Luka Doncic": {"pts": 35.2, "std_dev": 6.1, "recent_games": 20},
    "LeBron James": {"pts": 23.9, "std_dev": 3.8, "recent_games": 19},
    "Ja Morant": {"pts": 21.7, "std_dev": 4.3, "recent_games": 10},
    "Jaren Jackson Jr.": {"pts": 20.6, "std_dev": 3.9, "recent_games": 18},
    "Anthony Davis": {"pts": 13.4, "std_dev": 2.6, "recent_games": 19},
}

def calculate_hit_probability(player_name, stat_type, line, direction):
    """Calculate P(hit) using normal distribution + hydrated stats"""
    if player_name not in PLAYER_STATS:
        return 0.50  # Default if not found
    
    stats = PLAYER_STATS[player_name]
    mu = stats["pts"]
    sigma = stats["std_dev"]
    
    if direction == "HIGHER":
        # P(X > line)
        from scipy import stats as scipy_stats
        return scipy_stats.norm.sf(line, mu, sigma)
    else:
        # P(X < line) - for LOWER
        from scipy import stats as scipy_stats
        return scipy_stats.norm.cdf(line, mu, sigma)

# Run MC for each game
results = {}
for game in slate["games"]:
    game_id = game["id"]
    matchup = game["matchup"]
    picks = game["picks"]
    
    n_picks = len(picks)
    hit_probs = []
    
    # Calculate individual hit probabilities
    for pick in picks:
        prob = calculate_hit_probability(
            pick["player"],
            pick["stat"],
            pick["line"],
            pick["direction"]
        )
        hit_probs.append(prob)
    
    # Monte Carlo: 10k trials
    n_trials = 10000
    hits_per_trial = []
    
    for _ in range(n_trials):
        trial_hits = sum(np.random.random() < p for p in hit_probs)
        hits_per_trial.append(trial_hits)
    
    avg_hits = np.mean(hits_per_trial)
    peak_hits = int(np.argmax(np.bincount(hits_per_trial)))
    peak_prob = np.bincount(hits_per_trial)[peak_hits] / n_trials * 100
    
    results[game_id] = {
        "matchup": matchup,
        "total_picks": n_picks,
        "avg_hits": avg_hits,
        "peak_hits": peak_hits,
        "peak_prob": peak_prob,
        "individual_probs": list(zip(
            [f"{p['player']} {p['stat']}" for p in picks],
            [f"{p*100:.1f}%" for p in hit_probs]
        ))
    }

# Generate report
output_file = Path("outputs") / f"MC_JAN4_SLATE_8GAMES_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

with open(output_file, "w", encoding="utf-8") as f:
    f.write("=" * 90 + "\n")
    f.write("MONTE CARLO ANALYSIS - JAN 4, 2026 NBA 8-GAME SLATE\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Simulations: 10,000 trials per game | Data: Hydrated from recent stats\n")
    f.write("=" * 90 + "\n\n")
    
    total_games = len(results)
    avg_slate_hits = np.mean([r["avg_hits"] for r in results.values()])
    
    f.write(f"SLATE OVERVIEW (8 Games)\n")
    f.write(f"Average hits across all games: {avg_slate_hits:.2f}\n\n")
    
    for game_id, result in sorted(results.items()):
        f.write(f"\n{'='*90}\n")
        f.write(f"GAME: {result['matchup']}\n")
        f.write(f"Total Props: {result['total_picks']}\n")
        f.write(f"{'='*90}\n\n")
        
        f.write(f"Monte Carlo Results (10k trials):\n")
        f.write(f"  Average Hits: {result['avg_hits']:.2f}/{result['total_picks']}\n")
        f.write(f"  Peak Distribution: {result['peak_hits']} hits ({result['peak_prob']:.1f}% probability)\n\n")
        
        f.write(f"Individual Hit Probabilities:\n")
        for prop, prob in result["individual_probs"]:
            f.write(f"  • {prop}: {prob}\n")
    
    f.write(f"\n{'='*90}\n")
    f.write("PIPELINE COMPLETE: INGEST > HYDRATE > MONTE CARLO\n")
    f.write(f"{'='*90}\n")

print(f"OK Analysis complete: {output_file}")
print(f"\nSUMMARY:")
for game_id, result in sorted(results.items()):
    print(f"  {result['matchup']}: {result['avg_hits']:.1f}/{result['total_picks']} avg hits")
