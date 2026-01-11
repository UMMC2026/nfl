#!/usr/bin/env python3
"""
Player Stats Distribution Simulation for NYK vs PHI
Generates realistic stat distributions for key players
"""

import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

# Player stats profiles (mean, std based on season data)
PLAYERS = {
    # 76ers
    "Tyrese Maxey": {"pts": (28.2, 5.8), "reb": (4.1, 1.9), "ast": (6.2, 2.1), "reb_ast": (10.3, 3.2)},
    "Joel Embiid": {"pts": (27.8, 7.2), "reb": (11.4, 4.1), "ast": (3.8, 1.6), "reb_ast": (15.2, 5.1)},
    "Paul George": {"pts": (14.8, 5.1), "reb": (4.2, 2.0), "ast": (2.1, 1.2), "reb_ast": (6.3, 2.4)},
    
    # Knicks
    "Jalen Brunson": {"pts": (28.9, 6.1), "reb": (3.2, 1.5), "ast": (8.4, 2.3), "reb_ast": (11.6, 3.1)},
    "Karl-Anthony Towns": {"pts": (21.2, 5.5), "reb": (8.1, 3.2), "ast": (2.7, 1.3), "reb_ast": (10.8, 3.9)},
    "OG Anunoby": {"pts": (16.1, 4.2), "reb": (5.2, 2.1), "ast": (1.8, 0.9), "reb_ast": (7.0, 2.4)},
}

# Betting lines (from game report)
LINES = {
    "Tyrese Maxey": {"pts_over": 28.0, "pra_over": 38.5},
    "Joel Embiid": {"pts_over": 25.0, "reb_over": 11.5},
    "Paul George": {"pts_over": 15.0},
    "Jalen Brunson": {"pts_over": 28.5, "pra_under": 40.5},
    "Karl-Anthony Towns": {"pts_under": 21.5},
    "OG Anunoby": {"pts_under": 16.5},
}

def simulate_player_stats(player_name, stats_profile, n_sims=10000, seed=42):
    """Simulate stat distribution for a player"""
    
    np.random.seed(seed + hash(player_name) % 1000)
    
    results = {}
    
    # Simulate each stat type
    for stat_type, (mean, std) in stats_profile.items():
        # Use truncated normal (no negative values)
        samples = np.random.normal(mean, std, n_sims)
        samples = np.maximum(samples, 0)  # Floor at 0
        
        results[stat_type] = {
            "samples": samples,
            "mean": samples.mean(),
            "median": np.median(samples),
            "std": samples.std(),
            "p10": np.percentile(samples, 10),
            "p25": np.percentile(samples, 25),
            "p50": np.percentile(samples, 50),
            "p75": np.percentile(samples, 75),
            "p90": np.percentile(samples, 90),
            "min": samples.min(),
            "max": samples.max(),
        }
    
    return results

def calculate_hit_probability(samples, line, direction="over"):
    """Calculate probability of hitting a line"""
    if direction == "over":
        return (samples > line).mean()
    else:  # under
        return (samples < line).mean()

def generate_report(n_sims=10000):
    """Generate comprehensive stats distribution report"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output = []
    output.append("=" * 100)
    output.append("📊 PLAYER STATS DISTRIBUTION SIMULATION: NYK vs PHI")
    output.append("=" * 100)
    output.append(f"Simulations: {n_sims:,} | Timestamp: {timestamp}\n")
    
    all_data = {}
    
    # Simulate each player
    for player_name, stats_profile in PLAYERS.items():
        output.append(f"\n{'='*100}")
        output.append(f"🏀 {player_name.upper()}")
        output.append(f"{'='*100}\n")
        
        sim_results = simulate_player_stats(player_name, stats_profile, n_sims)
        all_data[player_name] = sim_results
        
        # Display distribution for each stat
        for stat_type, results in sim_results.items():
            output.append(f"\n{stat_type.upper()}")
            output.append("-" * 100)
            
            stat_name = stat_type.replace("_", " ").title()
            output.append(f"Distribution: Mean={results['mean']:.1f}, Median={results['median']:.1f}, Std={results['std']:.1f}")
            output.append(f"Range: {results['min']:.1f} - {results['max']:.1f}")
            output.append(f"Percentiles: P10={results['p10']:.1f}, P25={results['p25']:.1f}, P50={results['p50']:.1f}, P75={results['p75']:.1f}, P90={results['p90']:.1f}")
            
            # Check betting lines
            if player_name in LINES:
                player_lines = LINES[player_name]
                
                # Points lines
                if stat_type == "pts":
                    if f"{stat_type}_over" in player_lines:
                        line = player_lines[f"{stat_type}_over"]
                        hit_prob = calculate_hit_probability(results["samples"], line, "over")
                        output.append(f"Betting Line: O {line:.1f} → Hit Prob: {hit_prob:.1%} {'✅' if hit_prob > 0.60 else '⚠️' if hit_prob > 0.50 else '❌'}")
                
                # Rebounds lines
                if stat_type == "reb":
                    if f"{stat_type}_over" in player_lines:
                        line = player_lines[f"{stat_type}_over"]
                        hit_prob = calculate_hit_probability(results["samples"], line, "over")
                        output.append(f"Betting Line: O {line:.1f} → Hit Prob: {hit_prob:.1%}")
                
                # PRA lines
                if stat_type == "reb_ast":
                    if f"pra_over" in player_lines:
                        line = player_lines["pra_over"]
                        hit_prob = calculate_hit_probability(results["samples"], line, "over")
                        output.append(f"Betting Line: O {line:.1f} (PRA) → Hit Prob: {hit_prob:.1%}")
                    if f"pra_under" in player_lines:
                        line = player_lines["pra_under"]
                        hit_prob = calculate_hit_probability(results["samples"], line, "under")
                        output.append(f"Betting Line: U {line:.1f} (PRA) → Hit Prob: {hit_prob:.1%}")
        
        # Points Under lines
        if player_name in LINES:
            player_lines = LINES[player_name]
            if f"pts_under" in player_lines:
                line = player_lines["pts_under"]
                hit_prob = calculate_hit_probability(sim_results["pts"]["samples"], line, "under")
                output.append(f"\nPoints UNDER Betting Line: U {line:.1f} → Hit Prob: {hit_prob:.1%}")
    
    # Summary comparison table
    output.append(f"\n\n{'='*100}")
    output.append("📋 QUICK REFERENCE: ALL BETTING LINES")
    output.append(f"{'='*100}\n")
    
    output.append(f"{'Player':<20} {'Stat':<15} {'Line':<10} {'Direction':<8} {'P(Hit)':<12} {'Assessment':<15}")
    output.append("-" * 100)
    
    for player_name, player_lines in LINES.items():
        if player_name in all_data:
            player_sims = all_data[player_name]
            
            for line_type, line_value in player_lines.items():
                if line_type == "pts_over":
                    hit_prob = calculate_hit_probability(player_sims["pts"]["samples"], line_value, "over")
                    assessment = "✅ SLAM" if hit_prob > 0.62 else "✅ STRONG" if hit_prob > 0.58 else "👍 LEAN" if hit_prob > 0.52 else "⚠️ AVOID"
                    output.append(f"{player_name:<20} {'Points':<15} {line_value:<10.1f} {'OVER':<8} {hit_prob:<12.1%} {assessment:<15}")
                
                elif line_type == "pts_under":
                    hit_prob = calculate_hit_probability(player_sims["pts"]["samples"], line_value, "under")
                    assessment = "✅ SLAM" if hit_prob > 0.62 else "✅ STRONG" if hit_prob > 0.58 else "👍 LEAN" if hit_prob > 0.52 else "⚠️ AVOID"
                    output.append(f"{player_name:<20} {'Points':<15} {line_value:<10.1f} {'UNDER':<8} {hit_prob:<12.1%} {assessment:<15}")
                
                elif line_type == "reb_over":
                    hit_prob = calculate_hit_probability(player_sims["reb"]["samples"], line_value, "over")
                    output.append(f"{player_name:<20} {'Rebounds':<15} {line_value:<10.1f} {'OVER':<8} {hit_prob:<12.1%}")
                
                elif line_type == "pra_over":
                    hit_prob = calculate_hit_probability(player_sims["reb_ast"]["samples"], line_value, "over")
                    output.append(f"{player_name:<20} {'PRA':<15} {line_value:<10.1f} {'OVER':<8} {hit_prob:<12.1%}")
                
                elif line_type == "pra_under":
                    hit_prob = calculate_hit_probability(player_sims["reb_ast"]["samples"], line_value, "under")
                    output.append(f"{player_name:<20} {'PRA':<15} {line_value:<10.1f} {'UNDER':<8} {hit_prob:<12.1%}")
    
    # Key insights
    output.append(f"\n\n{'='*100}")
    output.append("💡 KEY INSIGHTS")
    output.append(f"{'='*100}\n")
    
    output.append("🔥 Highest Variance (Most Unpredictable):")
    output.append("  • Joel Embiid Points (std=7.2) - Post-up heavy, game-script dependent")
    output.append("  • Karl-Anthony Towns Rebounds (std=3.2) - Matchup-dependent interior battle")
    output.append()
    
    output.append("✅ Most Predictable (Lowest Variance):")
    output.append("  • Jalen Brunson Assists (std=2.3) - Consistent ball handler, low variance")
    output.append("  • Paul George Points (std=5.1) - Role player, defined usage")
    output.append()
    
    output.append("🎯 Recommended Stacks (Correlated Overs):")
    output.append("  • Maxey Points + Brunson Points (pace-dependent, both benefit from fast flow)")
    output.append("  • Embiid Points + Towns Rebounds (inverse - Embiid dominance suppresses KAT)")
    output.append()
    
    output.append("⚖️  Recommended Hedges (Inverse):")
    output.append("  • Maxey Over + KAT Under (wing dominance vs interior struggle)")
    output.append("  • Brunson Over + OG Under (guard play vs wing suppression)")
    
    output.append(f"\n{'='*100}\n")
    
    return "\n".join(output), timestamp

if __name__ == "__main__":
    print("Generating player stats distribution simulation...")
    report, timestamp = generate_report(n_sims=10000)
    print(report)
    
    # Save to file
    output_path = Path("reports/simulations")
    output_path.mkdir(parents=True, exist_ok=True)
    
    filename = output_path / f"STATS_DISTRIBUTION_NYK_PHI_{timestamp}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n📁 Saved to: {filename}")
