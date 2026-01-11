#!/usr/bin/env python3
"""
Portfolio Builder - January 9, 2026
Bayesian multiplication for 2-pick and 3-pick Power entries
Diversification + correlation penalties
"""

import json
from itertools import combinations
from collections import defaultdict

# Underdog Power Payouts (2025 confirmed)
POWER_PAYOUTS = {
    2: 3.0,   # 2-pick power
    3: 6.0,   # 3-pick power
    4: 10.0,
    5: 20.0
}

def calculate_entry_ev(picks, payout_multiplier):
    """Bayesian probability multiplication: P(A ∩ B ∩ C) = P(A) × P(B) × P(C)"""
    p_all_hit = 1.0
    for pick in picks:
        p_all_hit *= (pick['p_hit'] / 100.0)
    
    roi = (payout_multiplier * p_all_hit) - 1.0
    return p_all_hit, roi

def check_correlation(picks):
    """Correlation penalties for same-game stacking"""
    teams = [p['team'] for p in picks]
    games = []
    
    # Check if picks from same game
    for i, p1 in enumerate(picks):
        for p2 in picks[i+1:]:
            # Same game stacking (both teams in same matchup)
            if (p1['team'] == p2['team']):
                return 0.10  # 10% penalty for same team
    
    return 0.0  # No penalty

def build_portfolio_jan9():
    """Generate optimal 2-pick and 3-pick Power entries"""
    
    print("💼 JANUARY 9, 2026 - PORTFOLIO BUILDER")
    print("=" * 70)
    print("📊 Bayesian multiplication | Correlation penalties | Diversification")
    print("=" * 70)
    
    with open('outputs/jan9_primary_edges.json', 'r') as f:
        data = json.load(f)
    
    primary_edges = data['primary_edges']
    
    print(f"\n🎯 PRIMARY EDGES: {len(primary_edges)} picks (80%+)")
    print("-" * 70)
    
    all_entries = []
    
    # 2-pick Power entries
    print("\n🔬 GENERATING 2-PICK POWER ENTRIES...")
    for combo in combinations(primary_edges, 2):
        picks = list(combo)
        correlation_penalty = check_correlation(picks)
        p_all_hit, roi = calculate_entry_ev(picks, POWER_PAYOUTS[2])
        
        # Apply correlation penalty
        adjusted_roi = roi * (1 - correlation_penalty)
        
        entry = {
            'type': '2-pick Power',
            'legs': 2,
            'picks': [
                f"{p['player']} {p['stat']} {p['line']}+ [{p['p_hit']}%]"
                for p in picks
            ],
            'teams': [p['team'] for p in picks],
            'p_all_hit': round(p_all_hit * 100, 2),
            'roi': round(adjusted_roi * 100, 2),
            'correlation_penalty': round(correlation_penalty * 100, 1),
            'details': picks
        }
        all_entries.append(entry)
    
    # 3-pick Power entries
    print("🔬 GENERATING 3-PICK POWER ENTRIES...")
    for combo in combinations(primary_edges, 3):
        picks = list(combo)
        correlation_penalty = check_correlation(picks)
        p_all_hit, roi = calculate_entry_ev(picks, POWER_PAYOUTS[3])
        
        # Apply correlation penalty
        adjusted_roi = roi * (1 - correlation_penalty)
        
        # Team diversity check (prefer ≥2 different teams)
        teams = set(p['team'] for p in picks)
        if len(teams) < 2:
            continue  # Skip single-team 3-picks
        
        entry = {
            'type': '3-pick Power',
            'legs': 3,
            'picks': [
                f"{p['player']} {p['stat']} {p['line']}+ [{p['p_hit']}%]"
                for p in picks
            ],
            'teams': [p['team'] for p in picks],
            'p_all_hit': round(p_all_hit * 100, 2),
            'roi': round(adjusted_roi * 100, 2),
            'correlation_penalty': round(correlation_penalty * 100, 1),
            'details': picks
        }
        all_entries.append(entry)
    
    # Sort by ROI
    all_entries.sort(key=lambda x: x['roi'], reverse=True)
    
    print(f"\n📈 PORTFOLIO GENERATION COMPLETE")
    print(f"   Total entries generated: {len(all_entries)}")
    print(f"   2-pick entries: {len([e for e in all_entries if e['legs'] == 2])}")
    print(f"   3-pick entries: {len([e for e in all_entries if e['legs'] == 3])}")
    
    # Top 5 entries
    top_5 = all_entries[:5]
    
    print(f"\n🏆 TOP 5 ENTRIES BY ROI:")
    print("=" * 70)
    for i, entry in enumerate(top_5, 1):
        print(f"\n#{i} - {entry['type']} | ROI: {entry['roi']}% | P(Win): {entry['p_all_hit']}%")
        print(f"   Teams: {', '.join(entry['teams'])}")
        for j, pick in enumerate(entry['picks'], 1):
            print(f"   {j}. {pick}")
        if entry['correlation_penalty'] > 0:
            print(f"   ⚠️  Correlation penalty: {entry['correlation_penalty']}%")
    
    # Portfolio breakdown
    print(f"\n📊 PORTFOLIO COMPOSITION:")
    print("-" * 70)
    
    # Player distribution in top 20
    player_count = defaultdict(int)
    for entry in all_entries[:20]:
        for pick in entry['details']:
            player_count[pick['player']] += 1
    
    print("   Top players in portfolio:")
    sorted_players = sorted(player_count.items(), key=lambda x: x[1], reverse=True)[:10]
    for player, count in sorted_players:
        print(f"   - {player:25} ({count} entries)")
    
    # Save complete portfolio
    portfolio = {
        'date': '2026-01-09',
        'total_entries': len(all_entries),
        'top_5_entries': top_5,
        'top_20_entries': all_entries[:20],
        'methodology': {
            'probability_model': 'Bayesian multiplication',
            'correlation_penalties': 'Same-team stacking = 10% penalty',
            'diversification': 'Min 2 teams for 3-picks',
            'payout_table': POWER_PAYOUTS
        }
    }
    
    with open('outputs/jan9_complete_portfolio.json', 'w') as f:
        json.dump(portfolio, f, indent=2)
    
    print(f"\n💾 PORTFOLIO SAVED:")
    print(f"   ✅ outputs/jan9_complete_portfolio.json (top 20 entries)")
    print(f"\n⏭️  NEXT STEP: Create enhanced telegram message")

if __name__ == '__main__':
    build_portfolio_jan9()
