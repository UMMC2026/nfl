#!/usr/bin/env python3
"""
Full 4-Layer Enhancement Pipeline for January 8, 2026 Slate
Uses hydrated data → rest day → matchup → qualified picks → primary edges
"""

import json
from pathlib import Path
from datetime import datetime

# NBA Team Ratings (OFF_RTG, DEF_RTG, NET_RTG)
TEAM_RATINGS = {
    "CHA": {"OFF_RTG": 109.2, "DEF_RTG": 116.8, "NET_RTG": -7.6},
    "IND": {"OFF_RTG": 118.5, "DEF_RTG": 113.2, "NET_RTG": 5.3},
    "CLE": {"OFF_RTG": 118.9, "DEF_RTG": 107.8, "NET_RTG": 11.1},
    "MIN": {"OFF_RTG": 114.8, "DEF_RTG": 110.5, "NET_RTG": 4.3},
    "MIA": {"OFF_RTG": 111.7, "DEF_RTG": 111.3, "NET_RTG": 0.4},
    "CHI": {"OFF_RTG": 113.5, "DEF_RTG": 115.2, "NET_RTG": -1.7},
    "DAL": {"OFF_RTG": 119.2, "DEF_RTG": 112.1, "NET_RTG": 7.1},
    "UTA": {"OFF_RTG": 111.8, "DEF_RTG": 119.5, "NET_RTG": -7.7},
}

# Rest day schedules (B2B indicator)
REST_SCHEDULES = {
    "CHA": {"days_rest": 1, "is_b2b": False},
    "IND": {"days_rest": 1, "is_b2b": False},
    "CLE": {"days_rest": 0, "is_b2b": True},
    "MIN": {"days_rest": 1, "is_b2b": False},
    "MIA": {"days_rest": 1, "is_b2b": False},
    "CHI": {"days_rest": 1, "is_b2b": False},
    "DAL": {"days_rest": 0, "is_b2b": True},
    "UTA": {"days_rest": 2, "is_b2b": False},
}

# Blowout probabilities (point spread estimates)
BLOWOUT_PROBS = {
    "IND@CHA": {"favorite": "IND", "spread": -5.5, "blowout_prob": 0.15},
    "CLE@MIN": {"favorite": "CLE", "spread": -3.5, "blowout_prob": 0.10},
    "MIA@CHI": {"favorite": "MIA", "spread": -2.5, "blowout_prob": 0.08},
    "DAL@UTA": {"favorite": "DAL", "spread": -8.5, "blowout_prob": 0.22},
}

def apply_rest_day_adjustment(prob, team):
    """Layer 3: Rest day adjustment"""
    rest_info = REST_SCHEDULES.get(team, {"days_rest": 1, "is_b2b": False})
    
    if rest_info["is_b2b"]:
        # Back-to-back: -10% adjustment
        return prob * 0.90
    elif rest_info["days_rest"] >= 2:
        # Extra rest: +5% adjustment
        return prob * 1.05
    else:
        # Normal rest: no adjustment
        return prob

def apply_matchup_adjustment(prob, player_team, opponent_team, stat_type):
    """Layer 4: Matchup adjustment (opponent defense + blowout)"""
    opp_rating = TEAM_RATINGS.get(opponent_team, {})
    
    # Defensive adjustment
    if "DEF_RTG" in opp_rating:
        league_avg_def = 113.5
        def_delta = opp_rating["DEF_RTG"] - league_avg_def
        
        # Weak defense (high DEF_RTG) → boost prob
        # Strong defense (low DEF_RTG) → reduce prob
        if stat_type in ["points", "pra", "3pm", "assists"]:
            # Offensive stats benefit from weak defense
            if def_delta > 3.0:
                prob *= 1.10
            elif def_delta < -3.0:
                prob *= 0.90
    
    # Blowout adjustment
    for matchup, blowout_info in BLOWOUT_PROBS.items():
        if player_team in matchup:
            if blowout_info["blowout_prob"] > 0.15:
                # High blowout risk → reduce prob for starters
                prob *= 0.95
            break
    
    return prob

def enhance_pick(pick):
    """Apply full 4-layer enhancement"""
    # Layer 1: Empirical rate (from hydration)
    # Layer 2: Bayesian probability (from hydration)
    bayesian_prob = pick.get("bayesian_prob", 0.50)
    
    # Layer 3: Rest day adjustment
    player_team = pick["team"]
    prob_after_rest = apply_rest_day_adjustment(bayesian_prob, player_team)
    
    # Layer 4: Matchup adjustment
    opponent_team = pick.get("opponent", "")
    stat_type = pick["stat"]
    final_prob = apply_matchup_adjustment(prob_after_rest, player_team, opponent_team, stat_type)
    
    # Cap at 90% (no overconfidence)
    final_prob = min(final_prob, 0.90)
    
    pick["prob_rest_adjusted"] = round(prob_after_rest, 3)
    pick["prob_final"] = round(final_prob, 3)
    
    return pick

def classify_pick_tier(prob):
    """Tier classification"""
    if prob >= 0.75:
        return "SLAM"
    elif prob >= 0.65:
        return "STRONG"
    elif prob >= 0.55:
        return "LEAN"
    else:
        return "AVOID"

def classify_variance(stat):
    """Variance classification"""
    if stat in ["3pm", "blocks", "steals"]:
        return "HIGH"
    elif stat in ["points", "rebounds", "assists", "pra"]:
        return "MED"
    else:
        return "LOW"

def select_primary_edges(picks):
    """ONE player = ONE edge"""
    player_picks = {}
    
    for pick in picks:
        player = pick["player"]
        if player not in player_picks:
            player_picks[player] = []
        player_picks[player].append(pick)
    
    primary_edges = []
    for player, player_prop_list in player_picks.items():
        # Select highest probability
        best_pick = max(player_prop_list, key=lambda p: p["prob_final"])
        best_pick["is_primary_edge"] = True
        primary_edges.append(best_pick)
    
    return primary_edges

def main():
    print("\n" + "="*80)
    print("🚀 FULL ENHANCEMENT PIPELINE - JANUARY 8, 2026")
    print("="*80)
    
    # Load hydrated picks
    hydrated_file = Path("outputs/jan8_hydrated.json")
    if not hydrated_file.exists():
        print("❌ ERROR: jan8_hydrated.json not found. Run hydrate_jan8_data.py first.")
        return
    
    with open(hydrated_file, "r") as f:
        data = json.load(f)
    
    picks = data["picks"]
    print(f"📥 Loaded {len(picks)} hydrated picks")
    
    # Layer 3 & 4: Rest day + Matchup adjustments
    print("\n🔧 Applying rest day + matchup adjustments...")
    enhanced_picks = [enhance_pick(pick) for pick in picks]
    
    # Filter qualified picks (≥65%)
    qualified_picks = [p for p in enhanced_picks if p["prob_final"] >= 0.65]
    print(f"✅ Qualified picks (≥65%): {len(qualified_picks)}")
    
    # Add tier and variance classifications
    for pick in qualified_picks:
        pick["tier"] = classify_pick_tier(pick["prob_final"])
        pick["variance"] = classify_variance(pick["stat"])
    
    # Select primary edges
    primary_edges = select_primary_edges(qualified_picks)
    print(f"🎯 Primary edges (ONE per player): {len(primary_edges)}")
    
    # Variance analysis
    high_variance_count = sum(1 for p in primary_edges if p["variance"] == "HIGH")
    variance_pct = high_variance_count / len(primary_edges) * 100 if primary_edges else 0
    print(f"📊 High variance props: {high_variance_count}/{len(primary_edges)} ({variance_pct:.1f}%)")
    
    if variance_pct > 20:
        print("⚠️  WARNING: High variance >20% limit")
    
    # Tier breakdown
    tier_counts = {}
    for pick in primary_edges:
        tier = pick["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print("\n📊 Tier Distribution:")
    for tier in ["SLAM", "STRONG", "LEAN"]:
        count = tier_counts.get(tier, 0)
        print(f"   {tier}: {count}")
    
    # Save results
    output = {
        "date": "2026-01-08",
        "all_enhanced": enhanced_picks,
        "qualified_picks": qualified_picks,
        "primary_edges": primary_edges,
        "stats": {
            "total_picks": len(picks),
            "qualified_count": len(qualified_picks),
            "primary_edges_count": len(primary_edges),
            "high_variance_count": high_variance_count,
            "high_variance_pct": round(variance_pct, 1),
            "tier_breakdown": tier_counts
        }
    }
    
    output_file = Path("outputs/jan8_final_enhanced.json")
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved to: {output_file}")
    
    # Display top primary edges
    print("\n" + "="*80)
    print("🎯 TOP PRIMARY EDGES (sorted by probability)")
    print("="*80)
    
    sorted_edges = sorted(primary_edges, key=lambda p: p["prob_final"], reverse=True)
    
    for i, pick in enumerate(sorted_edges[:15], 1):
        player = pick["player"]
        team = pick["team"]
        stat = pick["stat"]
        line = pick["line"]
        direction = pick["direction"]
        prob = pick["prob_final"]
        tier = pick["tier"]
        variance = pick["variance"]
        
        dir_symbol = "+" if direction == "higher" else "-"
        
        print(f"{i:2d}. {player:20s} ({team}) - {stat} {line}{dir_symbol}")
        print(f"    Prob: {prob:.1%} | Tier: {tier} | Variance: {variance}")
    
    print("\n" + "="*80)
    print("✅ ENHANCEMENT COMPLETE")
    print("="*80)
    print("\n▶️  Next: python structural_validation_pipeline.py")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
