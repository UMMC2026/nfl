import random
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from engine.edge_stability_engine import EdgeStabilityEngine

def run_chaos_simulation(engine: EdgeStabilityEngine, num_games: int = 50):
    results = {"total_picks": 0, "tiers": {}}
    print(f"--- STARTING CHAOS STRESS TEST: {num_games} GAMES ---")
    for game_id in range(num_games):
        slate_noise = random.uniform(0.8, 1.3)
        for prop in range(10):
            mean = random.uniform(10, 30)
            line = mean * random.uniform(0.85, 1.15)
            sigma = (mean * 0.2) * slate_noise
            min_stab = random.uniform(0.6, 0.95)
            role_ent = random.uniform(0.05, 0.4)
            tail_r = random.uniform(0.1, 0.45)
            ess_score = engine.calculate_ess(mean, line, sigma, min_stab, role_ent, tail_r)
            tier = engine.get_tier(ess_score)
            results["tiers"][tier] = results["tiers"].get(tier, 0) + 1
            results["total_picks"] += 1
    print(f"Stress Test Complete.")
    print(f"Tier Distribution: {results['tiers']}")
    slam_rate = results['tiers'].get('SLAM', 0) / results['total_picks']
    if slam_rate > 0.15:
        print("❌ FAIL: ESS is too lenient. Too many SLAM picks in a chaos environment.")
    else:
        print("✅ PASS: ESS effectively throttled picks during high noise.")

if __name__ == "__main__":
    run_chaos_simulation(EdgeStabilityEngine())
