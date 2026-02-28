"""
SUPER BOWL EMERGENCY CALCULATOR
Bypass broken edge collapse - manual μ/σ calculator only

Usage:
    python superbowl_emergency_calculator.py

Paste props in format:
    Patrick Mahomes, pass_yds, 275.5, higher
    Travis Kelce, rec_yds, 65.5, higher
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from scipy.stats import norm
import pandas as pd
from datetime import datetime
import json

# NFL stats projections (FROZEN - from nflverse 2025 season)
PLAYER_PROJECTIONS = {
    # QBs
    "Patrick Mahomes": {
        "pass_yds": {"mu": 283.2, "sigma": 48.7},
        "pass_tds": {"mu": 2.1, "sigma": 1.2},
        "rush_yds": {"mu": 18.3, "sigma": 12.5}
    },
    "Jalen Hurts": {
        "pass_yds": {"mu": 245.8, "sigma": 52.3},
        "pass_tds": {"mu": 1.9, "sigma": 1.1},
        "rush_yds": {"mu": 38.4, "sigma": 22.7}
    },
    
    # Chiefs pass catchers
    "Travis Kelce": {
        "rec_yds": {"mu": 68.3, "sigma": 28.4},
        "receptions": {"mu": 5.8, "sigma": 2.3}
    },
    "DeAndre Hopkins": {
        "rec_yds": {"mu": 52.1, "sigma": 24.6},
        "receptions": {"mu": 4.2, "sigma": 1.9}
    },
    "Xavier Worthy": {
        "rec_yds": {"mu": 45.7, "sigma": 26.8},
        "receptions": {"mu": 3.1, "sigma": 1.7}
    },
    
    # Chiefs RBs
    "Isiah Pacheco": {
        "rush_yds": {"mu": 62.4, "sigma": 32.1},
        "rec_yds": {"mu": 12.3, "sigma": 11.2}
    },
    "Kareem Hunt": {
        "rush_yds": {"mu": 38.6, "sigma": 24.5},
        "rec_yds": {"mu": 18.4, "sigma": 13.7}
    },
    
    # Eagles pass catchers
    "AJ Brown": {
        "rec_yds": {"mu": 78.4, "sigma": 31.2},
        "receptions": {"mu": 6.1, "sigma": 2.4}
    },
    "DeVonta Smith": {
        "rec_yds": {"mu": 65.3, "sigma": 28.7},
        "receptions": {"mu": 5.2, "sigma": 2.1}
    },
    "Dallas Goedert": {
        "rec_yds": {"mu": 48.2, "sigma": 22.6},
        "receptions": {"mu": 4.3, "sigma": 1.8}
    },
    
    # Eagles RBs
    "Saquon Barkley": {
        "rush_yds": {"mu": 94.7, "sigma": 38.4},
        "rec_yds": {"mu": 24.3, "sigma": 16.8},
        "receptions": {"mu": 2.8, "sigma": 1.6}
    },
    "Kenneth Gainwell": {
        "rush_yds": {"mu": 22.4, "sigma": 18.3},
        "rec_yds": {"mu": 15.7, "sigma": 12.4}
    }
}


def calculate_probability(mu, sigma, line, direction):
    """Calculate probability using z-score."""
    if sigma == 0:
        return 50.0
    
    z_score = (line - mu) / sigma
    
    if direction.lower() in ["higher", "over"]:
        prob = 1 - norm.cdf(z_score)
    else:
        prob = norm.cdf(z_score)
    
    return prob * 100


def calculate_edge(prob):
    """Calculate expected value edge."""
    # Assuming -110 vig (1.91 payout)
    ev = (prob / 100 * 1.91) - 1.0
    return ev * 100


def assign_tier(prob):
    """Assign tier based on probability."""
    if prob >= 75:
        return "SLAM"
    elif prob >= 65:
        return "STRONG"
    elif prob >= 57:
        return "LEAN"
    else:
        return "NO_PLAY"


def interactive_calculator():
    """Interactive prop calculator."""
    print("\n" + "="*70)
    print("🚨 SUPER BOWL EMERGENCY CALCULATOR")
    print("="*70)
    print("\nAvailable players:")
    for i, player in enumerate(PLAYER_PROJECTIONS.keys(), 1):
        stats = list(PLAYER_PROJECTIONS[player].keys())
        print(f"  {i:2d}. {player:25s} ({', '.join(stats)})")
    
    print("\n" + "="*70)
    print("PASTE PROPS (one per line, or 'q' to quit):")
    print("Format: Player Name, stat, line, direction")
    print("Example: Patrick Mahomes, pass_yds, 275.5, higher")
    print("="*70 + "\n")
    
    results = []
    
    while True:
        line = input("> ").strip()
        
        if not line or line.lower() == 'q':
            break
        
        try:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) != 4:
                print("❌ Format: Player, stat, line, direction")
                continue
            
            player, stat, line_str, direction = parts
            line_val = float(line_str)
            
            # Find player (case-insensitive, fuzzy match)
            player_match = None
            for p in PLAYER_PROJECTIONS:
                if player.lower() in p.lower() or p.lower() in player.lower():
                    player_match = p
                    break
            
            if not player_match:
                print(f"❌ Player '{player}' not found")
                continue
            
            if stat not in PLAYER_PROJECTIONS[player_match]:
                print(f"❌ Stat '{stat}' not available for {player_match}")
                print(f"   Available: {list(PLAYER_PROJECTIONS[player_match].keys())}")
                continue
            
            proj = PLAYER_PROJECTIONS[player_match][stat]
            mu = proj['mu']
            sigma = proj['sigma']
            
            prob = calculate_probability(mu, sigma, line_val, direction)
            edge = calculate_edge(prob)
            tier = assign_tier(prob)
            
            result = {
                'player': player_match,
                'stat': stat,
                'line': line_val,
                'direction': direction,
                'mu': mu,
                'sigma': sigma,
                'probability': prob,
                'edge': edge,
                'tier': tier
            }
            
            results.append(result)
            
            # Print result
            tier_emoji = {"SLAM": "💎", "STRONG": "🔥", "LEAN": "✅", "NO_PLAY": "❌"}[tier]
            print(f"  {tier_emoji} {player_match:25s} {stat:12s} {line_val:6.1f} {direction:6s}")
            print(f"     μ={mu:6.1f} σ={sigma:5.1f} | Prob={prob:5.1f}% Edge={edge:+5.1f}% | {tier}")
            print()
            
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    if not results:
        print("\n❌ No props analyzed")
        return
    
    # Sort by probability
    results.sort(key=lambda x: x['probability'], reverse=True)
    
    # Print summary
    print("\n" + "="*70)
    print("📊 TOP PICKS (Sorted by Probability)")
    print("="*70 + "\n")
    
    for i, r in enumerate(results, 1):
        tier_emoji = {"SLAM": "💎", "STRONG": "🔥", "LEAN": "✅", "NO_PLAY": "❌"}[r['tier']]
        print(f"{i:2d}. {tier_emoji} {r['player']:20s} {r['stat']:10s} {r['line']:6.1f} {r['direction']:6s}")
        print(f"      {r['probability']:5.1f}% | μ={r['mu']:6.1f} σ={r['sigma']:5.1f} | Edge={r['edge']:+5.1f}%")
        print()
    
    # Tier breakdown
    tiers = {}
    for r in results:
        tiers[r['tier']] = tiers.get(r['tier'], 0) + 1
    
    print("="*70)
    print("TIER BREAKDOWN:")
    for tier in ["SLAM", "STRONG", "LEAN", "NO_PLAY"]:
        count = tiers.get(tier, 0)
        if count > 0:
            print(f"  {tier:10s}: {count:2d} picks")
    print("="*70)
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/superbowl_emergency_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Saved to {output_file}")
    
    # Top 3 parlay suggestion
    top3 = [r for r in results if r['tier'] in ['SLAM', 'STRONG']][:3]
    if len(top3) >= 2:
        print("\n" + "="*70)
        print("🎯 SUGGESTED 3-LEG PARLAY:")
        print("="*70)
        combined_prob = 1.0
        for i, r in enumerate(top3, 1):
            combined_prob *= (r['probability'] / 100)
            print(f"{i}. {r['player']} {r['stat']} {r['direction']} {r['line']}")
            print(f"   {r['probability']:.1f}% | {r['tier']}")
        
        parlay_prob = combined_prob * 100
        print(f"\nCombined probability: {parlay_prob:.1f}%")
        if parlay_prob >= 40:
            print("✅ PLAYABLE parlay")
        else:
            print("❌ Too risky - probabilities too correlated or low")
        print("="*70)


if __name__ == "__main__":
    interactive_calculator()
