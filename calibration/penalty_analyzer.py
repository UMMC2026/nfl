"""
PENALTY CALIBRATION ANALYZER
============================
Analyze historical picks to determine which penalties are justified vs harmful.

This answers the core questions:
1. Does high variance actually predict worse performance?
2. Do plays with few games actually underperform?
3. Are points/3PM truly harder to predict?
4. Is 3% edge the right threshold?

Usage:
    python calibration/penalty_analyzer.py
"""
import json
import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_calibration_history() -> List[dict]:
    """Load all historical picks with outcomes."""
    picks = []
    
    # Try calibration_history.csv (root)
    # Schema: pick_id,game_date,player,team,opponent,stat,line,direction,probability,tier,actual_value,outcome,added_utc,league,source
    csv_path = Path(__file__).parent.parent / "calibration_history.csv"
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                outcome = row.get('outcome', '').upper()
                if outcome in ['HIT', 'MISS']:
                    # Parse probability - handle empty, numbers, or "USER" tier marker
                    prob_str = row.get('probability', '')
                    try:
                        probability = float(prob_str) if prob_str and prob_str != 'USER' else 0
                        # If probability looks like a decimal (0-1), convert to percentage
                        if 0 < probability < 1:
                            probability *= 100
                    except:
                        probability = 0
                    
                    # Parse tier - could be in tier column or probability column
                    tier = row.get('tier', '')
                    if not tier or tier == 'USER':
                        tier = row.get('probability', '')  # Sometimes tier is in probability col
                    
                    picks.append({
                        'player': row.get('player', ''),
                        'stat': row.get('stat', '').upper(),
                        'line': float(row.get('line', 0) or 0),
                        'direction': row.get('direction', 'higher').lower(),
                        'probability': probability,
                        'tier': tier,
                        'result': outcome.lower(),
                        'actual': float(row.get('actual_value', 0) or 0) if row.get('actual_value') else None,
                        'date': row.get('game_date', ''),
                        'sport': row.get('league', 'NBA'),
                        'source': row.get('source', 'calibration_history.csv'),
                        'pick_id': row.get('pick_id', '')
                    })
    
    return picks


def calculate_roi(picks: List[dict], odds: int = -110) -> dict:
    """
    Calculate ROI assuming -110 odds (standard).
    
    Win: +$90.91 profit on $100 bet
    Lose: -$100
    """
    if not picks:
        return {'win_rate': 0, 'roi': 0, 'n': 0, 'profit': 0}
    
    wins = sum(1 for p in picks if p['result'] == 'hit')
    losses = len(picks) - wins
    win_rate = wins / len(picks) if picks else 0
    
    # Calculate profit
    # At -110: win pays +90.91, loss costs -100
    payout_ratio = 100 / abs(odds)  # 0.909 at -110
    profit = (wins * payout_ratio * 100) - (losses * 100)
    roi = profit / (len(picks) * 100) * 100  # As percentage
    
    return {
        'win_rate': win_rate,
        'roi': roi,
        'n': len(picks),
        'wins': wins,
        'losses': losses,
        'profit': profit
    }


def analyze_by_stat_type(picks: List[dict]) -> dict:
    """Analyze performance by stat type."""
    by_stat = defaultdict(list)
    for p in picks:
        stat = p['stat'].lower() if p['stat'] else 'unknown'
        by_stat[stat].append(p)
    
    results = {}
    for stat, stat_picks in by_stat.items():
        roi_data = calculate_roi(stat_picks)
        results[stat] = {
            **roi_data,
            'stat': stat,
            'penalty_justified': roi_data['win_rate'] < 0.50  # Below break-even
        }
    
    return results


def analyze_by_probability_bucket(picks: List[dict]) -> dict:
    """Analyze performance by confidence bucket."""
    buckets = {
        '0-40%': (0, 40),
        '40-50%': (40, 50),
        '50-55%': (50, 55),
        '55-60%': (55, 60),
        '60-65%': (60, 65),
        '65-70%': (65, 70),
        '70-80%': (70, 80),
        '80%+': (80, 100)
    }
    
    results = {}
    for bucket_name, (low, high) in buckets.items():
        bucket_picks = [p for p in picks if low <= p['probability'] < high]
        if bucket_picks:
            roi_data = calculate_roi(bucket_picks)
            avg_prob = statistics.mean(p['probability'] for p in bucket_picks)
            results[bucket_name] = {
                **roi_data,
                'avg_probability': avg_prob,
                'calibration_error': abs(avg_prob/100 - roi_data['win_rate']),
                'well_calibrated': abs(avg_prob/100 - roi_data['win_rate']) < 0.10
            }
    
    return results


def analyze_by_tier(picks: List[dict]) -> dict:
    """Analyze performance by tier."""
    by_tier = defaultdict(list)
    for p in picks:
        tier = p['tier'].upper() if p['tier'] else 'UNKNOWN'
        by_tier[tier].append(p)
    
    results = {}
    for tier, tier_picks in by_tier.items():
        results[tier] = calculate_roi(tier_picks)
    
    return results


def analyze_by_edge_bucket(picks: List[dict]) -> dict:
    """
    Analyze performance by edge bucket.
    Edge = probability - 52.38% (implied at -110)
    """
    implied_prob = 52.38  # At -110 odds
    
    buckets = {
        'negative_edge': (-100, 0),
        '0-2%': (0, 2),
        '2-5%': (2, 5),
        '5-10%': (5, 10),
        '10-15%': (10, 15),
        '15%+': (15, 100)
    }
    
    results = {}
    for bucket_name, (low, high) in buckets.items():
        bucket_picks = []
        for p in picks:
            edge = p['probability'] - implied_prob
            if low <= edge < high:
                bucket_picks.append(p)
        
        if bucket_picks:
            roi_data = calculate_roi(bucket_picks)
            avg_edge = statistics.mean(p['probability'] - implied_prob for p in bucket_picks)
            results[bucket_name] = {
                **roi_data,
                'avg_edge': avg_edge,
                'profitable': roi_data['roi'] > 0
            }
    
    return results


def analyze_by_direction(picks: List[dict]) -> dict:
    """Analyze OVER vs UNDER performance."""
    by_dir = defaultdict(list)
    for p in picks:
        direction = p['direction'].lower() if p['direction'] else 'higher'
        by_dir[direction].append(p)
    
    results = {}
    for direction, dir_picks in by_dir.items():
        results[direction] = calculate_roi(dir_picks)
    
    return results


def find_optimal_edge_threshold(picks: List[dict]) -> dict:
    """
    Find the edge threshold that maximizes ROI.
    Test different thresholds and see which performs best.
    """
    implied_prob = 52.38
    
    thresholds_to_test = [0, 1, 2, 3, 4, 5, 7, 10, 12, 15]
    results = []
    
    for threshold in thresholds_to_test:
        # Filter picks that would pass this threshold
        passing_picks = [p for p in picks if (p['probability'] - implied_prob) >= threshold]
        
        if len(passing_picks) >= 5:  # Need minimum sample
            roi_data = calculate_roi(passing_picks)
            results.append({
                'threshold': threshold,
                **roi_data,
                'volume': len(passing_picks) / len(picks) * 100  # % of plays retained
            })
    
    # Find best threshold
    if results:
        best = max(results, key=lambda x: x['roi'])
        return {
            'all_thresholds': results,
            'optimal_threshold': best['threshold'],
            'optimal_roi': best['roi'],
            'optimal_win_rate': best['win_rate'],
            'volume_at_optimal': best['volume']
        }
    
    return {'error': 'Insufficient data'}


def generate_penalty_recommendations(analysis: dict) -> List[str]:
    """Generate actionable recommendations based on analysis."""
    recommendations = []
    
    # Stat-specific penalties
    stat_analysis = analysis.get('by_stat', {})
    for stat, data in stat_analysis.items():
        if data['n'] >= 10:
            if data['win_rate'] >= 0.55:
                recommendations.append(
                    f"✅ REMOVE penalty for '{stat}': {data['win_rate']:.1%} win rate ({data['n']} picks)"
                )
            elif data['win_rate'] < 0.45:
                recommendations.append(
                    f"⚠️ KEEP/INCREASE penalty for '{stat}': {data['win_rate']:.1%} win rate ({data['n']} picks)"
                )
    
    # Edge threshold
    edge_analysis = analysis.get('edge_threshold', {})
    if edge_analysis.get('optimal_threshold') is not None:
        current = 3  # Current threshold
        optimal = edge_analysis['optimal_threshold']
        if optimal < current:
            recommendations.append(
                f"📉 LOWER edge threshold: {current}% → {optimal}% (ROI: {edge_analysis['optimal_roi']:.1f}%)"
            )
        elif optimal > current:
            recommendations.append(
                f"📈 RAISE edge threshold: {current}% → {optimal}% (ROI: {edge_analysis['optimal_roi']:.1f}%)"
            )
    
    # Direction bias
    dir_analysis = analysis.get('by_direction', {})
    higher = dir_analysis.get('higher', {})
    lower = dir_analysis.get('lower', {})
    if higher.get('win_rate', 0) > lower.get('win_rate', 0) + 0.10:
        recommendations.append(
            f"🎯 FAVOR OVERS: {higher.get('win_rate', 0):.1%} vs {lower.get('win_rate', 0):.1%} unders"
        )
    elif lower.get('win_rate', 0) > higher.get('win_rate', 0) + 0.10:
        recommendations.append(
            f"🎯 FAVOR UNDERS: {lower.get('win_rate', 0):.1%} vs {higher.get('win_rate', 0):.1%} overs"
        )
    
    # Calibration
    prob_analysis = analysis.get('by_probability', {})
    for bucket, data in prob_analysis.items():
        if data.get('n', 0) >= 10 and not data.get('well_calibrated', True):
            recommendations.append(
                f"⚙️ CALIBRATION needed for {bucket}: predicted {data['avg_probability']:.0f}%, actual {data['win_rate']:.1%}"
            )
    
    return recommendations


def run_full_analysis():
    """Run complete penalty analysis."""
    print("=" * 70)
    print("PENALTY CALIBRATION ANALYSIS")
    print("=" * 70)
    print()
    
    # Load data
    picks = load_calibration_history()
    
    if not picks:
        print("❌ No historical picks found!")
        print("   Check: calibration_history.csv or calibration/picks.csv")
        return
    
    # Filter to picks with outcomes
    picks_with_results = [p for p in picks if p['result'] in ['hit', 'miss']]
    
    print(f"📊 Loaded {len(picks_with_results)} picks with outcomes")
    print()
    
    # Overall performance
    overall = calculate_roi(picks_with_results)
    print("OVERALL PERFORMANCE:")
    print(f"  Win Rate: {overall['win_rate']:.1%} ({overall['wins']}/{overall['n']})")
    print(f"  ROI: {overall['roi']:.1f}%")
    print(f"  Profit: ${overall['profit']:.0f} (on ${overall['n'] * 100} wagered)")
    print()
    
    # Store all analysis
    analysis = {
        'overall': overall,
        'by_stat': analyze_by_stat_type(picks_with_results),
        'by_probability': analyze_by_probability_bucket(picks_with_results),
        'by_tier': analyze_by_tier(picks_with_results),
        'by_edge': analyze_by_edge_bucket(picks_with_results),
        'by_direction': analyze_by_direction(picks_with_results),
        'edge_threshold': find_optimal_edge_threshold(picks_with_results),
    }
    
    # Print stat analysis
    print("BY STAT TYPE:")
    print("-" * 50)
    for stat, data in sorted(analysis['by_stat'].items(), key=lambda x: -x[1]['win_rate']):
        if data['n'] >= 3:
            penalty_flag = "✅" if data['win_rate'] >= 0.52 else "⚠️" if data['win_rate'] >= 0.45 else "❌"
            print(f"  {penalty_flag} {stat:<15} {data['win_rate']:>6.1%} ({data['n']:>3} picks) ROI: {data['roi']:>6.1f}%")
    print()
    
    # Print probability bucket analysis
    print("BY PROBABILITY BUCKET:")
    print("-" * 50)
    for bucket, data in analysis['by_probability'].items():
        calib_flag = "✅" if data.get('well_calibrated') else "⚠️"
        print(f"  {calib_flag} {bucket:<10} predicted {data['avg_probability']:>4.0f}% → actual {data['win_rate']:>5.1%} (n={data['n']})")
    print()
    
    # Print edge analysis
    print("BY EDGE BUCKET (vs 52.38% implied):")
    print("-" * 50)
    for bucket, data in analysis['by_edge'].items():
        profit_flag = "✅" if data.get('profitable') else "❌"
        print(f"  {profit_flag} {bucket:<15} win: {data['win_rate']:>5.1%}  ROI: {data['roi']:>6.1f}% (n={data['n']})")
    print()
    
    # Print optimal threshold
    edge_opt = analysis['edge_threshold']
    if edge_opt.get('optimal_threshold') is not None:
        print("OPTIMAL EDGE THRESHOLD:")
        print("-" * 50)
        print(f"  Current: 3% (arbitrary)")
        print(f"  Optimal: {edge_opt['optimal_threshold']}%")
        print(f"  At optimal: {edge_opt['optimal_win_rate']:.1%} win rate, {edge_opt['optimal_roi']:.1f}% ROI")
        print(f"  Volume retained: {edge_opt['volume_at_optimal']:.0f}% of plays")
        print()
    
    # Print direction analysis
    print("BY DIRECTION:")
    print("-" * 50)
    for direction, data in analysis['by_direction'].items():
        print(f"  {direction.upper():<10} {data['win_rate']:.1%} ({data['n']} picks) ROI: {data['roi']:.1f}%")
    print()
    
    # Generate recommendations
    print("=" * 70)
    print("RECOMMENDATIONS:")
    print("=" * 70)
    recommendations = generate_penalty_recommendations(analysis)
    for rec in recommendations:
        print(f"  {rec}")
    
    if not recommendations:
        print("  No strong recommendations - data may be insufficient")
    
    print()
    
    # Save analysis to JSON
    output_path = Path(__file__).parent / "penalty_analysis_results.json"
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)
    print(f"📁 Full analysis saved to: {output_path}")
    
    return analysis


if __name__ == "__main__":
    run_full_analysis()
