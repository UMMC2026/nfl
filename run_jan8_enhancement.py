"""
Enhancement Pipeline for January 8, 2026 Slate
Runs 4-layer probability enhancement on tonight's 61 picks
"""

import json
from datetime import datetime
from pathlib import Path

# Import enhancement modules
try:
    from matchup_analytics import analyze_matchup_context, adjust_probability_for_matchup
    from ufa.ingest.hydrate import hydrate_recent_values
    has_imports = True
except ImportError:
    print("⚠️  Enhancement modules not available - running in demo mode")
    has_imports = False


def calculate_empirical_rate(recent_values, line, direction):
    """Calculate 10-game empirical hit rate."""
    if not recent_values:
        return 0.5
    
    if direction == "higher":
        hits = sum(1 for v in recent_values if v > line)
    else:
        hits = sum(1 for v in recent_values if v < line)
    
    return hits / len(recent_values)


def bayesian_probability(empirical_rate, n_games=10, prior_alpha=3, prior_beta=3):
    """Beta-Binomial Bayesian update."""
    hits = empirical_rate * n_games
    posterior_alpha = prior_alpha + hits
    posterior_beta = prior_beta + (n_games - hits)
    return posterior_alpha / (posterior_alpha + posterior_beta)


def enhance_pick(pick):
    """Run 4-layer enhancement on a single pick."""
    enhanced = pick.copy()
    
    # Layer 1: Empirical rate (mock data for demo)
    # In production, would call hydrate_recent_values()
    empirical_rate = 0.60  # Demo value
    enhanced['empirical_rate'] = empirical_rate
    enhanced['recent_values'] = []  # Would be populated by hydration
    
    # Layer 2: Bayesian update
    bayesian_prob = bayesian_probability(empirical_rate)
    enhanced['bayesian_prob'] = bayesian_prob
    
    # Layer 3: Rest day adjustment (would check actual rest days)
    rest_adjusted = bayesian_prob  # No adjustment in demo
    enhanced['rest_adjusted_prob'] = rest_adjusted
    enhanced['rest_commentary'] = ""
    
    # Layer 4: Matchup adjustment (would call matchup analytics)
    final_prob = rest_adjusted  # No adjustment in demo
    enhanced['final_prob'] = final_prob
    enhanced['matchup_commentary'] = "Analysis pending data hydration"
    enhanced['opponent_def_percentile'] = 50.0
    enhanced['blowout_prob_pct'] = 25.0
    
    return enhanced


def main():
    print("\n" + "="*80)
    print("🔬 ENHANCEMENT PIPELINE - JANUARY 8, 2026")
    print("="*80)
    print("Running 4-layer probability enhancement on 61 picks")
    print()
    
    # Load tonight's slate
    with open('outputs/jan8_slate_raw.json', 'r') as f:
        slate = json.load(f)
    
    picks = slate['picks']
    print(f"📊 Loaded {len(picks)} picks from {len(slate['games'])} games")
    print()
    
    # Enhance each pick
    print("🔄 Enhancing picks...")
    enhanced_picks = []
    
    for i, pick in enumerate(picks, 1):
        enhanced = enhance_pick(pick)
        enhanced_picks.append(enhanced)
        
        if i % 10 == 0:
            print(f"   Processed {i}/{len(picks)} picks...")
    
    print(f"✅ Enhanced all {len(enhanced_picks)} picks")
    print()
    
    # Filter qualified picks (≥65% final probability)
    threshold = 0.65
    qualified = [p for p in enhanced_picks if p['final_prob'] >= threshold]
    
    print(f"🎯 Qualified picks (≥{threshold:.0%}): {len(qualified)}")
    print()
    
    # Apply structural rule: ONE PRIMARY EDGE per player
    from collections import defaultdict
    player_picks = defaultdict(list)
    
    for pick in qualified:
        player_picks[pick['player']].append(pick)
    
    # Select highest confidence prop for each player
    primary_edges = []
    for player, pick_list in player_picks.items():
        best_pick = max(pick_list, key=lambda p: p['final_prob'])
        primary_edges.append(best_pick)
    
    print(f"👤 Primary edges (ONE per player): {len(primary_edges)}")
    print()
    
    # Sort by probability
    primary_edges.sort(key=lambda p: p['final_prob'], reverse=True)
    
    # Display top picks
    print("="*80)
    print("🏆 TOP PRIMARY EDGES")
    print("="*80)
    for i, pick in enumerate(primary_edges[:10], 1):
        variance = "HIGH" if pick['stat'] == '3pm' else "MED"
        print(f"{i:2d}. {pick['player']:20s} ({pick['team']}) - {pick['stat']:8s} {pick['line']:5.1f}+ [{variance}]")
        print(f"    Final P(hit): {pick['final_prob']:.1%}  |  {pick['matchup_commentary']}")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'date': slate['date'],
        'total_picks': len(picks),
        'qualified_picks': len(qualified),
        'primary_edges': len(primary_edges),
        'threshold': threshold,
        'picks_detail': enhanced_picks,
        'qualified_picks_detail': qualified,
        'primary_edges_detail': primary_edges
    }
    
    output_path = 'outputs/jan8_enhanced.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved to: {output_path}")
    print()
    
    # Check high variance exposure
    high_var_stats = ['3pm', 'blocks', 'steals']
    high_var_count = sum(1 for p in primary_edges if p['stat'] in high_var_stats)
    high_var_pct = (high_var_count / len(primary_edges)) * 100 if primary_edges else 0
    
    print("="*80)
    print("⚠️  VARIANCE CHECK")
    print("="*80)
    print(f"High variance props: {high_var_count}/{len(primary_edges)} ({high_var_pct:.1f}%)")
    if high_var_pct > 20:
        print("🚨 WARNING: >20% high variance - recommend further filtering")
    else:
        print("✅ Within limits (≤20%)")
    print()
    
    # Next steps
    print("="*80)
    print("📋 NEXT STEPS")
    print("="*80)
    print("\n1. Run structural validation:")
    print("   python structural_validation_pipeline.py")
    print("\n2. Build portfolio entries (2-3 picks, different teams)")
    print("\n3. Review outputs/jan8_enhanced.json for full details")
    print()
    print("="*80)
    print()
    
    print(f"⚠️  NOTE: This is DEMO mode without actual data hydration")
    print(f"For production: Hydrate with nba_api game logs before running")
    print()


if __name__ == "__main__":
    main()
