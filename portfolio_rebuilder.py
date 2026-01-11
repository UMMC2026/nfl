"""
PORTFOLIO REBUILDER
Reconstructs entries with proper correlation control and risk management.
Implements the "One Player = One Primary Edge" rule.
"""

import json
from pathlib import Path
from collections import defaultdict
from itertools import combinations
import numpy as np

class PortfolioRebuilder:
    """Rebuild portfolio with strict structural rules."""
    
    # Prop variance classification
    HIGH_VARIANCE = ['3pm', 'blocks', 'steals', 'turnovers']
    COMBO_STATS = ['pra', 'pts+reb', 'pts+ast', 'reb+ast', 'stl+blk']
    
    def __init__(self):
        self.qualified_picks = []
        self.player_edges = {}  # One primary edge per player
        
    def classify_prop_variance(self, stat, line):
        """Classify prop by variance level."""
        stat_lower = stat.lower()
        
        if stat_lower in self.HIGH_VARIANCE:
            return "HIGH"
        elif stat_lower in self.COMBO_STATS:
            return "LOW"
        elif stat_lower == 'points' and line < 10:
            return "HIGH"
        else:
            return "MEDIUM"
    
    def select_primary_edges(self, picks):
        """
        ONE PLAYER = ONE PRIMARY EDGE per slate.
        If player has multiple qualified props, pick the highest confidence.
        """
        print("\n" + "="*80)
        print("🎯 SELECTING PRIMARY EDGES (One Per Player)")
        print("="*80)
        
        # Group by player
        player_props = defaultdict(list)
        for pick in picks:
            player = pick['player']
            player_props[player].append(pick)
        
        primary_edges = []
        
        for player, props in player_props.items():
            if len(props) == 1:
                primary_edges.append(props[0])
                print(f"✅ {player}: {props[0]['stat']} {props[0]['line']}+ ({props[0]['final_prob']:.1%})")
            else:
                # Multiple props - pick highest confidence
                best = max(props, key=lambda x: x['final_prob'])
                primary_edges.append(best)
                
                print(f"\n⚠️ {player}: {len(props)} qualified props")
                for p in sorted(props, key=lambda x: x['final_prob'], reverse=True):
                    marker = "✅ SELECTED" if p == best else "❌ SKIPPED"
                    print(f"   {marker}: {p['stat']} {p['line']}+ ({p['final_prob']:.1%})")
        
        print(f"\n📊 Total qualified picks: {len(picks)}")
        print(f"📊 Primary edges selected: {len(primary_edges)}")
        print(f"📊 Edges eliminated: {len(picks) - len(primary_edges)}")
        
        return primary_edges
    
    def tier_classification(self, prob, variance):
        """Classify edge by risk tier."""
        if prob >= 0.75 and variance == "LOW":
            return "SLAM"
        elif prob >= 0.75 and variance == "MEDIUM":
            return "SLAM"
        elif prob >= 0.65 and variance in ["LOW", "MEDIUM"]:
            return "STRONG"
        elif prob >= 0.55:
            return "LEAN"
        else:
            return "FADE"
    
    def build_tier_based_entries(self, primary_edges):
        """
        Build entries respecting tier rules:
        - SLAM tier: Can be used alone or with other SLAMs
        - STRONG tier: Can mix with SLAMs, not with LEANs
        - LEAN tier: Separate entries, never mixed
        """
        print("\n" + "="*80)
        print("🏗️ BUILDING TIER-BASED ENTRIES")
        print("="*80)
        
        # Classify edges
        slams = []
        strongs = []
        leans = []
        
        for edge in primary_edges:
            prob = edge['final_prob']
            variance = self.classify_prop_variance(edge['stat'], edge['line'])
            tier = self.tier_classification(prob, variance)
            
            edge['variance'] = variance
            edge['tier'] = tier
            
            if tier == "SLAM":
                slams.append(edge)
            elif tier == "STRONG":
                strongs.append(edge)
            elif tier == "LEAN":
                leans.append(edge)
        
        print(f"\n🔥 SLAM tier: {len(slams)} edges (≥75% + low/medium variance)")
        print(f"💪 STRONG tier: {len(strongs)} edges (≥65% + low/medium variance)")
        print(f"🎯 LEAN tier: {len(leans)} edges (55-64%)")
        
        # Build entries
        entries = []
        
        # Strategy 1: SLAM-only combos (highest confidence)
        if len(slams) >= 2:
            print("\n📋 Building SLAM-only entries (2-3 picks max)...")
            slam_combos_2 = list(combinations(slams, 2))
            slam_combos_3 = list(combinations(slams, 3))
            
            # Evaluate and pick best
            for combo in slam_combos_2[:5]:  # Top 5 two-pick
                entry = self.evaluate_combo(combo, "SLAM 2-Pick")
                if entry:
                    entries.append(entry)
            
            for combo in slam_combos_3[:5]:  # Top 5 three-pick
                entry = self.evaluate_combo(combo, "SLAM 3-Pick")
                if entry:
                    entries.append(entry)
        
        # Strategy 2: SLAM + STRONG combos
        if len(slams) >= 1 and len(strongs) >= 1:
            print("\n📋 Building SLAM + STRONG entries...")
            # 1 SLAM + 1-2 STRONG
            for slam in slams[:3]:  # Top 3 SLAMs
                for strong in strongs[:3]:  # Top 3 STRONGs
                    if self.check_correlation([slam, strong]):
                        entry = self.evaluate_combo([slam, strong], "Mixed (SLAM+STRONG)")
                        if entry:
                            entries.append(entry)
        
        # Strategy 3: LEAN tier in isolation (max 2-pick)
        if len(leans) >= 2:
            print("\n📋 Building LEAN-only entries (2-pick max)...")
            lean_combos = list(combinations(leans, 2))
            for combo in lean_combos[:3]:  # Max 3 LEAN entries
                if self.check_correlation(combo):
                    entry = self.evaluate_combo(combo, "LEAN 2-Pick")
                    if entry:
                        entries.append(entry)
        
        return entries
    
    def check_correlation(self, picks):
        """Verify picks are statistically independent."""
        teams = [p['team'] for p in picks]
        
        # Rule 1: Max 1 pick per team (avoid same-game correlation)
        if len(teams) != len(set(teams)):
            return False
        
        # Rule 2: Different stat types preferred
        stats = [p['stat'] for p in picks]
        if len(set(stats)) < len(stats) * 0.7:  # At least 70% unique stats
            return False
        
        return True
    
    def evaluate_combo(self, picks, label):
        """Evaluate combo and return structured entry."""
        probs = [p['final_prob'] for p in picks]
        p_all = np.prod(probs)
        
        # Determine payout
        legs = len(picks)
        if legs == 2:
            payout = 3
        elif legs == 3:
            payout = 6
        elif legs == 4:
            payout = 10
        else:
            payout = 20
        
        # Calculate EV
        ev_units = (p_all * (payout - 1)) - (1 - p_all)
        ev_roi = ev_units * 100
        
        # Only accept positive EV
        if ev_roi < 0:
            return None
        
        return {
            'label': label,
            'picks': picks,
            'legs': legs,
            'p_all_hit': p_all,
            'ev_roi_pct': ev_roi,
            'payout': payout,
            'probs': probs
        }
    
    def rank_and_filter(self, entries, max_entries=5):
        """Rank by EV and filter to top N."""
        # Sort by EV
        ranked = sorted(entries, key=lambda x: x['ev_roi_pct'], reverse=True)
        
        print("\n" + "="*80)
        print(f"📊 RANKED ENTRIES (Top {max_entries})")
        print("="*80)
        
        selected = []
        used_players = set()
        
        for entry in ranked:
            # Ensure no player reuse across final portfolio
            players = [p['player'] for p in entry['picks']]
            
            if any(p in used_players for p in players):
                continue  # Skip if player already used
            
            selected.append(entry)
            used_players.update(players)
            
            if len(selected) >= max_entries:
                break
        
        return selected
    
    def display_reconstructed_portfolio(self, entries):
        """Display final portfolio with full context."""
        print("\n" + "="*80)
        print("✅ RECONSTRUCTED PORTFOLIO")
        print("="*80)
        
        print(f"\nTotal entries: {len(entries)}")
        
        total_ev = 0
        for i, entry in enumerate(entries, 1):
            print(f"\n{'='*80}")
            print(f"Entry #{i}: {entry['label']}")
            print(f"{'='*80}")
            print(f"Legs: {entry['legs']} | Payout: {entry['payout']}x")
            print(f"P(All Hit): {entry['p_all_hit']:.1%} | E[ROI]: {entry['ev_roi_pct']:+.1f}%")
            print()
            
            for j, pick in enumerate(entry['picks'], 1):
                print(f"{j}️⃣  {pick['player']} {pick['line']}+ {pick['stat']} ({pick['final_prob']:.1%})")
                print(f"    Team: {pick['team']} | Tier: {pick['tier']} | Variance: {pick['variance']}")
                
                if pick.get('rest_commentary'):
                    print(f"    {pick['rest_commentary']}")
                
                if pick.get('matchup_commentary'):
                    print(f"    {pick['matchup_commentary']}")
                
                print()
            
            total_ev += entry['ev_roi_pct']
        
        print("="*80)
        print(f"📊 PORTFOLIO SUMMARY")
        print("="*80)
        print(f"Total Entries: {len(entries)}")
        print(f"Total Expected ROI: {total_ev:+.1f}%")
        print(f"Avg ROI per Entry: {total_ev/len(entries):+.1f}%")
        print("="*80)

def rebuild_from_enhanced_results():
    """Main rebuild function."""
    print("="*80)
    print(" "*20 + "PORTFOLIO REBUILDER")
    print("="*80)
    
    # Load enhanced results
    filepath = Path("outputs/monte_carlo_enhanced.json")
    with open(filepath) as f:
        data = json.load(f)
    
    picks = data['qualified_picks_detail']
    
    print(f"\n📥 Loaded {len(picks)} qualified picks")
    
    # Initialize rebuilder
    rebuilder = PortfolioRebuilder()
    
    # Step 1: Select primary edges (one per player)
    primary_edges = rebuilder.select_primary_edges(picks)
    
    # Step 2: Build tier-based entries
    entries = rebuilder.build_tier_based_entries(primary_edges)
    
    # Step 3: Rank and filter
    final_entries = rebuilder.rank_and_filter(entries, max_entries=5)
    
    # Step 4: Display
    rebuilder.display_reconstructed_portfolio(final_entries)
    
    # Step 5: Save
    output_file = Path("outputs/portfolio_reconstructed.json")
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': data['timestamp'],
            'original_picks': len(picks),
            'primary_edges': len(primary_edges),
            'final_entries': final_entries
        }, f, indent=2)
    
    print(f"\n✅ Reconstructed portfolio saved to {output_file}")
    
    return final_entries

if __name__ == "__main__":
    rebuild_from_enhanced_results()
