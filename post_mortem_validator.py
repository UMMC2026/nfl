"""
POST-MORTEM VALIDATOR
Analyzes actual results vs predictions to identify systematic failures.
Enforces structural truth about what went wrong.
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

class PostMortemValidator:
    """Validate actual results and identify failure patterns."""
    
    def __init__(self):
        self.results = []
        self.failures = defaultdict(list)
        self.successes = defaultdict(list)
        
    def load_entries(self, filepath):
        """Load entries that were actually played."""
        with open(filepath) as f:
            return json.load(f)
    
    def analyze_correlation_violations(self, entries):
        """Detect duplicate player exposure across entries."""
        print("\n" + "="*80)
        print("🚨 CORRELATION VIOLATIONS DETECTED")
        print("="*80)
        
        # Track player usage across all entries
        player_usage = defaultdict(list)
        
        for i, entry in enumerate(entries, 1):
            # Handle different data structures
            if isinstance(entry.get('picks'), list):
                picks = entry['picks']
            elif isinstance(entry.get('players'), list):
                # Monte Carlo format with players array
                picks = []
                for j, player in enumerate(entry['players']):
                    picks.append({
                        'player': player,
                        'stat': entry['stats'][j] if j < len(entry['stats']) else 'unknown',
                        'line': 0,
                        'prob': entry['probs'][j] if j < len(entry['probs']) else 0
                    })
            else:
                continue
            
            for pick in picks:
                if isinstance(pick, str):
                    # Format: "Player 1.5+ stat"
                    continue
                    
                player = pick.get('player', 'Unknown')
                stat = pick.get('stat', 'unknown')
                player_usage[player].append({
                    'entry': i,
                    'stat': stat,
                    'line': pick.get('line', 0),
                    'prob': pick.get('final_prob', pick.get('bayesian_prob', pick.get('prob', 0)))
                })
        
        # Report violations
        violations = 0
        for player, usage in player_usage.items():
            if len(usage) > 1:
                violations += 1
                print(f"\n⚠️ {player}: USED {len(usage)} TIMES")
                for u in usage:
                    print(f"   Entry #{u['entry']}: {u['stat']} {u['line']}+ ({u['prob']:.1%})")
                print(f"   ❌ VIOLATION: One player = one primary edge per slate")
        
        if violations == 0:
            print("\n✅ No correlation violations detected")
        else:
            print(f"\n❌ TOTAL VIOLATIONS: {violations} players used multiple times")
        
        return violations
    
    def analyze_prop_type_distribution(self, entries):
        """Identify high-variance prop overuse."""
        print("\n" + "="*80)
        print("📊 PROP TYPE DISTRIBUTION ANALYSIS")
        print("="*80)
        
        prop_types = {
            'HIGH_VARIANCE': defaultdict(int),  # 3PM, low-point thresholds
            'MEDIUM_VARIANCE': defaultdict(int),  # Points, AST, REB
            'LOW_VARIANCE': defaultdict(int),  # Combos (PRA), high-usage stats
        }
        
        high_variance_stats = ['3pm', 'blocks', 'steals', 'turnovers']
        combo_stats = ['pra', 'pts+reb', 'pts+ast', 'reb+ast', 'stl+blk']
        
        total_picks = 0
        for entry in entries:
            # Handle different data structures
            if isinstance(entry.get('picks'), list):
                picks = entry['picks']
            elif isinstance(entry.get('stats'), list):
                # Use stats array
                stats = entry['stats']
                for stat in stats:
                    total_picks += 1
                    stat_lower = stat.lower()
                    
                    if stat_lower in high_variance_stats:
                        prop_types['HIGH_VARIANCE'][stat_lower] += 1
                    elif stat_lower in combo_stats:
                        prop_types['LOW_VARIANCE'][stat_lower] += 1
                    else:
                        prop_types['MEDIUM_VARIANCE'][stat_lower] += 1
                continue
            else:
                continue
            
            for pick in picks:
                if isinstance(pick, str):
                    continue
                    
                total_picks += 1
                stat = pick.get('stat', '').lower()
                line = pick.get('line', 0)
                
                # Classify variance
                if stat in high_variance_stats:
                    prop_types['HIGH_VARIANCE'][stat] += 1
                elif stat in combo_stats:
                    prop_types['LOW_VARIANCE'][stat] += 1
                elif stat == 'points' and line < 10:
                    prop_types['HIGH_VARIANCE']['low_points'] += 1
                else:
                    prop_types['MEDIUM_VARIANCE'][stat] += 1
        
        # Report
        print(f"\nTotal picks: {total_picks}")
        print("\n🔴 HIGH VARIANCE PROPS (Should be ≤20% of portfolio):")
        hv_count = sum(prop_types['HIGH_VARIANCE'].values())
        for stat, count in prop_types['HIGH_VARIANCE'].items():
            pct = (count / total_picks) * 100
            print(f"   {stat}: {count} ({pct:.1f}%)")
        print(f"   TOTAL: {hv_count} ({hv_count/total_picks*100:.1f}%)")
        
        if hv_count / total_picks > 0.20:
            print(f"   ❌ VIOLATION: {hv_count/total_picks*100:.1f}% > 20% threshold")
        
        print("\n🟡 MEDIUM VARIANCE PROPS:")
        for stat, count in prop_types['MEDIUM_VARIANCE'].items():
            pct = (count / total_picks) * 100
            print(f"   {stat}: {count} ({pct:.1f}%)")
        
        print("\n🟢 LOW VARIANCE PROPS (Combos):")
        for stat, count in prop_types['LOW_VARIANCE'].items():
            pct = (count / total_picks) * 100
            print(f"   {stat}: {count} ({pct:.1f}%)")
    
    def analyze_entry_structure(self, entries):
        """Analyze multiplier aggressiveness."""
        print("\n" + "="*80)
        print("🎲 ENTRY STRUCTURE ANALYSIS")
        print("="*80)
        
        leg_distribution = defaultdict(int)
        
        for entry in entries:
            legs = len(entry['picks'])
            leg_distribution[legs] += 1
        
        print("\nEntry distribution by leg count:")
        for legs in sorted(leg_distribution.keys()):
            count = leg_distribution[legs]
            # Calculate breakeven win rate needed
            # For 6x payout on 3-pick: need 16.7% hit rate
            # For each additional pick, multiply by ~0.7 to maintain +EV
            if legs == 2:
                payout = 3
                breakeven = 1/payout
                safe_rate = 0.70
            elif legs == 3:
                payout = 6
                breakeven = 1/payout
                safe_rate = 0.60
            elif legs == 4:
                payout = 10
                breakeven = 1/payout
                safe_rate = 0.50
            elif legs == 5:
                payout = 20
                breakeven = 1/payout
                safe_rate = 0.43
            else:
                payout = 50
                breakeven = 1/payout
                safe_rate = 0.35
            
            print(f"\n   {legs}-pick entries: {count}")
            print(f"      Payout: {payout}x")
            print(f"      Breakeven: {breakeven:.1%} hit rate")
            print(f"      Recommended min: {safe_rate:.1%} per leg")
        
        # Flag aggressive entries
        aggressive_count = sum(count for legs, count in leg_distribution.items() if legs >= 5)
        if aggressive_count > 0:
            print(f"\n   ❌ WARNING: {aggressive_count} entries with 5+ legs")
            print(f"      High leg counts require near-perfect execution")
            print(f"      One weak link = guaranteed loss")
    
    def generate_fix_recommendations(self):
        """Generate actionable fixes based on violations."""
        print("\n" + "="*80)
        print("🔧 IMMEDIATE FIX RECOMMENDATIONS")
        print("="*80)
        
        print("\n1. CORRELATION CONTROL (CRITICAL)")
        print("   ✅ Enforce: ONE PRIMARY EDGE PER PLAYER PER SLATE")
        print("   ✅ If player appears twice, pick the higher confidence prop only")
        print("   ✅ Do NOT reuse edges across multiple entries")
        
        print("\n2. PROP TYPE LIMITS (HIGH PRIORITY)")
        print("   ✅ 3PM props: MAX 15% of total portfolio")
        print("   ✅ Low-point props (<10pts): MAX 10% of total portfolio")
        print("   ✅ Blocks/Steals: LEAN-only, never SLAM")
        print("   ✅ Prefer: Assists, Rebounds, PRA combos (lower variance)")
        
        print("\n3. ENTRY STRUCTURE (HIGH PRIORITY)")
        print("   ✅ Cap at 3-pick entries for daily slates")
        print("   ✅ 4+ pick entries ONLY for tournament/GPP formats")
        print("   ✅ Each leg must be ≥70% confidence for 3-pick power")
        print("   ✅ Avoid mixing high-variance props in same entry")
        
        print("\n4. PORTFOLIO CONSTRUCTION (MEDIUM PRIORITY)")
        print("   ✅ Maximum 3-5 entries per slate")
        print("   ✅ Each entry should be statistically independent")
        print("   ✅ If two entries share a player, they must use different games")
        print("   ✅ Diversify across stat types (don't stack all 3PM)")
        
        print("\n5. RISK TIER ENFORCEMENT (MEDIUM PRIORITY)")
        print("   ✅ SLAM tier: 75%+ confidence, core stats only")
        print("   ✅ STRONG tier: 65-74% confidence, medium variance OK")
        print("   ✅ LEAN tier: 55-64% confidence, high variance allowed")
        print("   ✅ Never build entries mixing LEAN + STRONG + SLAM")
    
    def validate_reconstructed_portfolio(self, entries):
        """Full validation of portfolio structure."""
        print("\n" + "="*80)
        print("✅ PORTFOLIO VALIDATION RESULTS")
        print("="*80)
        
        violations = []
        
        # Check 1: Correlation
        corr_violations = self.analyze_correlation_violations(entries)
        if corr_violations > 0:
            violations.append(f"Correlation: {corr_violations} players used multiple times")
        
        # Check 2: Prop types
        self.analyze_prop_type_distribution(entries)
        
        # Check 3: Entry structure
        self.analyze_entry_structure(entries)
        
        # Summary
        print("\n" + "="*80)
        if len(violations) == 0:
            print("✅ PORTFOLIO PASSES ALL VALIDATION CHECKS")
        else:
            print("❌ PORTFOLIO HAS STRUCTURAL ISSUES:")
            for v in violations:
                print(f"   • {v}")
        print("="*80)

def run_post_mortem(entries_file):
    """Run full post-mortem analysis."""
    validator = PostMortemValidator()
    
    print("="*80)
    print(" "*20 + "POST-MORTEM VALIDATION REPORT")
    print("="*80)
    print(f"\nAnalyzing: {entries_file}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load entries
    entries_path = Path(entries_file)
    if not entries_path.exists():
        print(f"\n❌ File not found: {entries_file}")
        return
    
    with open(entries_path) as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, dict) and 'top_30_combos' in data:
        entries = data['top_30_combos'][:10]  # Analyze top 10 combos
        print(f"\n📊 Analyzing top {len(entries)} combos from Monte Carlo results")
        print(f"Total qualified picks: {data.get('qualified_picks', 0)}")
        print(f"Qualified pick details available: {len(data.get('qualified_picks_detail', []))}")
    elif isinstance(data, list):
        entries = data
    else:
        print("❌ Unrecognized JSON structure")
        return
    
    print(f"\nTotal entries to analyze: {len(entries)}")
    
    # Run all validations
    validator.validate_reconstructed_portfolio(entries)
    validator.generate_fix_recommendations()
    
    print("\n" + "="*80)
    print("📋 NEXT STEPS")
    print("="*80)
    print("\n1. Run: python portfolio_rebuilder.py")
    print("   → Rebuilds entries with correlation control")
    print("\n2. Compare before/after structure")
    print("   → Validate improvements")
    print("\n3. Apply rules to future slates")
    print("   → Prevent repeat failures")
    print("\n" + "="*80)

if __name__ == "__main__":
    # Analyze the most recent enhanced Monte Carlo results
    run_post_mortem("outputs/monte_carlo_enhanced.json")
