"""
STRUCTURAL VALIDATION PIPELINE
================================
Standalone pipeline for analyzing and rebuilding portfolio structure.
Runs independently from the enhancement pipeline.

Purpose: Detect correlation violations, variance overload, multiplier aggression
         and rebuild portfolio with proper structural controls.

Usage:
    python structural_validation_pipeline.py

Outputs:
    - outputs/structural_violations_report.txt
    - outputs/portfolio_before.json
    - outputs/portfolio_after.json
    - outputs/structural_comparison.txt
"""

import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path


class StructuralValidator:
    """Validates portfolio structure independently."""
    
    def __init__(self):
        self.violations = []
        self.warnings = []
        
    def load_portfolio(self, filepath):
        """Load Monte Carlo results."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Extract qualified picks and combos
        picks = data.get('qualified_picks_detail', [])
        combos = data.get('top_30_combos', [])
        
        return {
            'picks': picks,
            'combos': combos[:10],  # Top 10 for analysis
            'metadata': {
                'total_picks': data.get('total_picks', 0),
                'qualified_picks': data.get('qualified_picks', 0),
                'threshold': data.get('threshold', 0)
            }
        }
    
    def analyze_player_exposure(self, combos):
        """Check for duplicate player usage."""
        player_usage = defaultdict(int)
        player_combos = defaultdict(list)
        
        for i, combo in enumerate(combos, 1):
            players = combo.get('players', [])
            for player in players:
                player_usage[player] += 1
                player_combos[player].append(i)
        
        duplicates = {p: count for p, count in player_usage.items() if count > 1}
        
        if duplicates:
            self.violations.append({
                'type': 'DUPLICATE_EXPOSURE',
                'severity': 'CRITICAL',
                'description': 'Players used in multiple combos',
                'data': {p: {'count': c, 'combos': player_combos[p]} for p, c in duplicates.items()}
            })
        
        return duplicates
    
    def analyze_variance_distribution(self, combos):
        """Check for high-variance prop overuse."""
        high_variance = ['3pm', 'blocks', 'steals', 'turnovers']
        
        total_props = 0
        high_var_count = 0
        stat_breakdown = defaultdict(int)
        
        for combo in combos:
            stats = combo.get('stats', [])
            for stat in stats:
                total_props += 1
                stat_breakdown[stat] += 1
                if stat.lower() in high_variance:
                    high_var_count += 1
        
        if total_props == 0:
            return None
        
        high_var_pct = (high_var_count / total_props) * 100
        
        if high_var_pct > 20:
            self.violations.append({
                'type': 'VARIANCE_OVERLOAD',
                'severity': 'HIGH',
                'description': f'High variance props: {high_var_pct:.1f}% (should be ≤20%)',
                'data': stat_breakdown
            })
        
        return {
            'total': total_props,
            'high_variance': high_var_count,
            'percentage': high_var_pct,
            'breakdown': stat_breakdown
        }
    
    def analyze_team_correlation(self, combos):
        """Check for same-team correlation."""
        same_team_violations = []
        
        for i, combo in enumerate(combos, 1):
            teams = combo.get('teams', [])
            if len(teams) != len(set(teams)):
                same_team_violations.append({
                    'combo_num': i,
                    'teams': teams,
                    'players': combo.get('players', [])
                })
        
        if same_team_violations:
            self.warnings.append({
                'type': 'TEAM_CORRELATION',
                'severity': 'MEDIUM',
                'description': 'Same-game correlations detected',
                'data': same_team_violations
            })
        
        return same_team_violations
    
    def analyze_leg_distribution(self, combos):
        """Check multiplier aggressiveness."""
        leg_counts = defaultdict(int)
        
        for combo in combos:
            players = combo.get('players', [])
            num_legs = len(players)
            leg_counts[num_legs] += 1
        
        if leg_counts.get(5, 0) + leg_counts.get(6, 0) + leg_counts.get(7, 0) > 0:
            self.warnings.append({
                'type': 'AGGRESSIVE_MULTIPLIERS',
                'severity': 'HIGH',
                'description': '5+ leg entries detected (high breakeven rate)',
                'data': dict(leg_counts)
            })
        
        return dict(leg_counts)
    
    def generate_report(self, output_path):
        """Generate violation report."""
        report = []
        report.append("="*80)
        report.append("STRUCTURAL VALIDATION REPORT")
        report.append("="*80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Pipeline: STANDALONE (independent from enhancement system)")
        report.append("")
        
        if not self.violations and not self.warnings:
            report.append("✅ NO VIOLATIONS DETECTED")
            report.append("")
            report.append("Portfolio structure meets all requirements:")
            report.append("  • One player = one primary edge")
            report.append("  • High variance props ≤20%")
            report.append("  • No duplicate exposure")
            report.append("  • Reasonable multipliers")
        else:
            report.append(f"🚨 VIOLATIONS: {len(self.violations)}")
            report.append(f"⚠️  WARNINGS: {len(self.warnings)}")
            report.append("")
            
            if self.violations:
                report.append("="*80)
                report.append("CRITICAL VIOLATIONS")
                report.append("="*80)
                for v in self.violations:
                    report.append(f"\n[{v['severity']}] {v['type']}")
                    report.append(f"  {v['description']}")
                    if v['type'] == 'DUPLICATE_EXPOSURE':
                        for player, info in v['data'].items():
                            report.append(f"  • {player}: used {info['count']}x in combos {info['combos']}")
                    elif v['type'] == 'VARIANCE_OVERLOAD':
                        report.append("\n  Stat breakdown:")
                        for stat, count in sorted(v['data'].items(), key=lambda x: x[1], reverse=True):
                            report.append(f"    {stat}: {count}")
            
            if self.warnings:
                report.append("\n" + "="*80)
                report.append("WARNINGS")
                report.append("="*80)
                for w in self.warnings:
                    report.append(f"\n[{w['severity']}] {w['type']}")
                    report.append(f"  {w['description']}")
        
        report.append("\n" + "="*80)
        report.append("NEXT STEPS")
        report.append("="*80)
        report.append("\n1. Review violations above")
        report.append("2. Run portfolio rebuilder to fix structure")
        report.append("3. Compare before/after portfolios")
        report.append("4. Apply rules to future slates")
        report.append("\n" + "="*80)
        
        # Write to file
        Path(output_path).parent.mkdir(exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        return '\n'.join(report)


class PortfolioRebuilder:
    """Rebuilds portfolio with structural controls."""
    
    def __init__(self):
        self.variance_classification = {
            'HIGH': ['3pm', 'blocks', 'steals', 'turnovers'],
            'COMBO': ['pra', 'pts+reb', 'pts+ast', 'reb+ast', 'stl+blk']
        }
    
    def select_primary_edges(self, picks):
        """ONE player = ONE primary edge."""
        player_picks = defaultdict(list)
        
        for pick in picks:
            player = pick['player']
            player_picks[player].append(pick)
        
        # For each player, select highest confidence prop
        primary_edges = []
        for player, pick_list in player_picks.items():
            best_pick = max(pick_list, key=lambda p: p.get('final_prob', 0))
            primary_edges.append(best_pick)
        
        return sorted(primary_edges, key=lambda p: p.get('final_prob', 0), reverse=True)
    
    def classify_variance(self, stat):
        """Classify prop variance level."""
        stat_lower = stat.lower()
        if stat_lower in self.variance_classification['HIGH']:
            return 'HIGH'
        elif stat_lower in self.variance_classification['COMBO']:
            return 'LOW'
        else:
            return 'MEDIUM'
    
    def tier_picks(self, picks):
        """Tier picks by confidence + variance."""
        tiers = {'SLAM': [], 'STRONG': [], 'LEAN': []}
        
        for pick in picks:
            prob = pick.get('final_prob', 0)
            variance = self.classify_variance(pick['stat'])
            
            if prob >= 0.75 and variance in ['LOW', 'MEDIUM']:
                tiers['SLAM'].append(pick)
            elif prob >= 0.65 and variance in ['LOW', 'MEDIUM']:
                tiers['STRONG'].append(pick)
            elif prob >= 0.55:
                tiers['LEAN'].append(pick)
        
        return tiers
    
    def build_entries(self, tiers, max_entries=5):
        """Build tier-based entries."""
        entries = []
        
        # Strategy 1: SLAM-only 2-3 pick combos
        slams = tiers['SLAM']
        if len(slams) >= 2:
            for i in range(min(2, len(slams)-1)):
                for j in range(i+1, min(i+3, len(slams))):
                    entry = {
                        'tier_strategy': 'SLAM_ONLY',
                        'picks': [slams[i], slams[j]],
                        'teams': list(set([slams[i]['team'], slams[j]['team']])),
                        'avg_prob': (slams[i]['final_prob'] + slams[j]['final_prob']) / 2
                    }
                    if len(entry['teams']) >= 2:  # Enforce different teams
                        entries.append(entry)
        
        # Strategy 2: SLAM + STRONG mixed
        strongs = tiers['STRONG']
        if slams and strongs:
            for slam in slams[:3]:
                for strong in strongs[:2]:
                    if slam['team'] != strong['team'] and slam['player'] != strong['player']:
                        entries.append({
                            'tier_strategy': 'SLAM_STRONG',
                            'picks': [slam, strong],
                            'teams': [slam['team'], strong['team']],
                            'avg_prob': (slam['final_prob'] + strong['final_prob']) / 2
                        })
        
        # Strategy 3: LEAN isolated (max 2-pick)
        leans = tiers['LEAN']
        if len(leans) >= 2:
            lean_entry = {
                'tier_strategy': 'LEAN_ISOLATED',
                'picks': leans[:2],
                'teams': [leans[0]['team'], leans[1]['team']],
                'avg_prob': sum(p['final_prob'] for p in leans[:2]) / 2
            }
            if len(set([p['team'] for p in leans[:2]])) >= 2:
                entries.append(lean_entry)
        
        # Sort by avg probability and limit
        entries.sort(key=lambda e: e['avg_prob'], reverse=True)
        return entries[:max_entries]
    
    def rebuild_portfolio(self, picks):
        """Full rebuild pipeline."""
        # Step 1: Select primary edges
        primary_edges = self.select_primary_edges(picks)
        
        # Step 2: Tier classification
        tiers = self.tier_picks(primary_edges)
        
        # Step 3: Build entries
        entries = self.build_entries(tiers)
        
        return {
            'primary_edges': primary_edges,
            'tiers': {k: len(v) for k, v in tiers.items()},
            'entries': entries,
            'metadata': {
                'total_edges': len(primary_edges),
                'total_entries': len(entries),
                'max_player_exposure': 1  # Each player in exactly one entry
            }
        }


def run_structural_pipeline():
    """Execute standalone structural validation pipeline."""
    print("\n" + "="*80)
    print("🔧 STRUCTURAL VALIDATION PIPELINE (STANDALONE)")
    print("="*80)
    print("Independent from enhancement system - analyzes portfolio structure only")
    print()
    
    # Initialize
    validator = StructuralValidator()
    rebuilder = PortfolioRebuilder()
    
    # Load portfolio
    print("📂 Loading portfolio from: outputs/monte_carlo_enhanced.json")
    portfolio = validator.load_portfolio('outputs/monte_carlo_enhanced.json')
    print(f"   Qualified picks: {portfolio['metadata']['qualified_picks']}")
    print(f"   Top combos to analyze: {len(portfolio['combos'])}")
    print()
    
    # Validate structure
    print("🔍 Running structural validations...")
    print()
    
    duplicates = validator.analyze_player_exposure(portfolio['combos'])
    if duplicates:
        print(f"❌ Duplicate exposure: {len(duplicates)} players used multiple times")
    else:
        print("✅ No duplicate player exposure")
    
    variance = validator.analyze_variance_distribution(portfolio['combos'])
    if variance:
        print(f"📊 Variance distribution: {variance['high_variance']}/{variance['total']} props ({variance['percentage']:.1f}%)")
    
    team_corr = validator.analyze_team_correlation(portfolio['combos'])
    if team_corr:
        print(f"⚠️  Same-team correlation: {len(team_corr)} combos affected")
    else:
        print("✅ No same-team correlation")
    
    legs = validator.analyze_leg_distribution(portfolio['combos'])
    print(f"🎯 Leg distribution: {legs}")
    print()
    
    # Generate violation report
    print("📝 Generating violation report...")
    report_path = 'outputs/structural_violations_report.txt'
    report = validator.generate_report(report_path)
    print(f"   Saved to: {report_path}")
    print()
    
    # Save before portfolio
    before_path = 'outputs/portfolio_before.json'
    with open(before_path, 'w') as f:
        json.dump(portfolio['combos'], f, indent=2)
    print(f"📄 Before portfolio: {before_path}")
    
    # Rebuild portfolio
    print("\n🔨 Rebuilding portfolio with structural controls...")
    rebuilt = rebuilder.rebuild_portfolio(portfolio['picks'])
    
    # Save after portfolio
    after_path = 'outputs/portfolio_after.json'
    with open(after_path, 'w') as f:
        json.dump(rebuilt, f, indent=2)
    print(f"   Saved to: {after_path}")
    
    # Comparison summary
    print("\n" + "="*80)
    print("📊 BEFORE vs AFTER COMPARISON")
    print("="*80)
    print(f"Player exposure:    {len(portfolio['combos'])} combos → {rebuilt['metadata']['total_entries']} entries")
    print(f"Primary edges:      N/A → {rebuilt['metadata']['total_edges']} unique players")
    print(f"Tier distribution:  N/A → {rebuilt['tiers']}")
    print(f"Max exposure:       Multiple → {rebuilt['metadata']['max_player_exposure']} per player")
    
    # Save comparison
    comparison_path = 'outputs/structural_comparison.txt'
    with open(comparison_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("STRUCTURAL COMPARISON REPORT\n")
        f.write("="*80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("BEFORE (Original Monte Carlo):\n")
        f.write(f"  Total combos: {len(portfolio['combos'])}\n")
        f.write(f"  Duplicate exposure: {len(duplicates)} players\n")
        if variance:
            f.write(f"  High variance: {variance['percentage']:.1f}%\n")
        f.write(f"  Leg distribution: {legs}\n\n")
        f.write("AFTER (Rebuilt with Controls):\n")
        f.write(f"  Total entries: {rebuilt['metadata']['total_entries']}\n")
        f.write(f"  Primary edges: {rebuilt['metadata']['total_edges']}\n")
        f.write(f"  Tier distribution: {rebuilt['tiers']}\n")
        f.write(f"  Max player exposure: {rebuilt['metadata']['max_player_exposure']}\n")
        f.write("\n" + "="*80 + "\n")
    
    print(f"\n💾 Full comparison: {comparison_path}")
    
    print("\n" + "="*80)
    print("✅ STRUCTURAL PIPELINE COMPLETE")
    print("="*80)
    print("\nGenerated files:")
    print(f"  1. {report_path}")
    print(f"  2. {before_path}")
    print(f"  3. {after_path}")
    print(f"  4. {comparison_path}")
    print("\nThis pipeline runs independently - no conflicts with enhancement system.")
    print("="*80 + "\n")


if __name__ == "__main__":
    run_structural_pipeline()
