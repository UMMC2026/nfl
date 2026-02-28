"""
HYBRID CONFIDENCE SYSTEM
========================
Combines the best of both approaches:
- Demon mode simplicity: if mu > line, you have edge
- Data-driven adjustments: based on 97 historical picks
- Light uncertainty weighting: not Bayesian overkill

This is the PRODUCTION-READY confidence calculator.
"""
import numpy as np
from scipy import stats
from typing import Dict, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import data-driven penalties from analysis
from config.data_driven_penalties import (
    get_data_driven_multiplier,
    should_veto_stat,
    get_sample_size_factor,
    BYPASS_ALL_PENALTIES
)


def calculate_hybrid_confidence(
    mu: float,              # Model's predicted mean
    sigma: float,           # Observed standard deviation
    line: float,            # Betting line
    n_games: int,           # Sample size
    stat: str,              # Stat type (pts, ast, etc.)
    direction: str = "higher",  # "higher" or "lower"
    verbose: bool = False
) -> Dict:
    """
    Calculate confidence using hybrid approach.
    
    STEP 1: Calculate raw probability (demon mode)
    STEP 2: Apply data-driven stat/direction adjustment
    STEP 3: Apply light sample size adjustment
    STEP 4: Determine tier from effective edge
    
    Returns dict with probability, edge, tier, decision.
    """
    result = {
        'mu': mu,
        'sigma': sigma,
        'line': line,
        'n_games': n_games,
        'stat': stat,
        'direction': direction,
    }
    
    # === VETO CHECK ===
    if should_veto_stat(stat):
        result.update({
            'raw_probability': 0,
            'effective_probability': 0,
            'edge': 0,
            'tier': 'VETO',
            'decision': 'VETO',
            'reason': f"Stat '{stat}' has <35% historical win rate"
        })
        return result
    
    # === STEP 1: RAW PROBABILITY (DEMON MODE) ===
    if sigma <= 0:
        sigma = mu * 0.20  # Assume 20% CV if missing
    
    z_score = (line - mu) / sigma
    
    if direction.lower() in ["higher", "over"]:
        raw_prob = 1 - stats.norm.cdf(z_score)
    else:
        raw_prob = stats.norm.cdf(z_score)
    
    result['z_score'] = round(z_score, 2)
    result['raw_probability'] = round(raw_prob * 100, 1)
    
    # === STEP 2: DATA-DRIVEN ADJUSTMENT ===
    if BYPASS_ALL_PENALTIES:
        stat_dir_mult = 1.0
    else:
        stat_dir_mult = get_data_driven_multiplier(stat, direction)
    
    result['stat_direction_multiplier'] = stat_dir_mult
    
    # === STEP 3: SAMPLE SIZE ADJUSTMENT ===
    if BYPASS_ALL_PENALTIES:
        sample_mult = 1.0
    else:
        sample_mult = get_sample_size_factor(n_games)
    
    if sample_mult == 0:
        result.update({
            'effective_probability': 0,
            'edge': 0,
            'tier': 'VETO',
            'decision': 'VETO',
            'reason': f"Insufficient sample size (n={n_games} < 5)"
        })
        return result
    
    result['sample_size_multiplier'] = sample_mult
    
    # === STEP 4: EFFECTIVE PROBABILITY ===
    # Apply adjustments to the EDGE, not the raw probability
    # This preserves the mu > line logic while adjusting confidence
    
    implied_prob = 0.5238  # At -110 odds
    raw_edge = raw_prob - implied_prob
    
    # Adjust edge by multipliers
    effective_edge = raw_edge * stat_dir_mult * sample_mult
    
    # Convert back to probability for display
    effective_prob = implied_prob + effective_edge
    effective_prob = max(0, min(1, effective_prob))  # Clamp 0-100%
    
    result['raw_edge'] = round(raw_edge * 100, 2)
    result['effective_edge'] = round(effective_edge * 100, 2)
    result['effective_probability'] = round(effective_prob * 100, 1)
    
    # === STEP 5: TIER ASSIGNMENT ===
    # Based on effective edge (not raw)
    edge_pct = effective_edge * 100
    
    if edge_pct >= 15:
        tier = 'SLAM'
    elif edge_pct >= 7:
        tier = 'STRONG'
    elif edge_pct >= 2:
        tier = 'LEAN'
    elif edge_pct >= 0:
        tier = 'WATCH'
    else:
        tier = 'NO_PLAY'
    
    result['tier'] = tier
    result['decision'] = tier if tier not in ['NO_PLAY', 'WATCH'] else 'NO_PLAY'
    
    # === VERBOSE OUTPUT ===
    if verbose:
        print(f"\n{'='*50}")
        print(f"HYBRID CONFIDENCE: {stat} {direction} {line}")
        print(f"{'='*50}")
        print(f"Model: μ={mu}, σ={sigma}, n={n_games}")
        print(f"Z-score: {z_score:.2f}")
        print(f"Raw probability: {raw_prob*100:.1f}%")
        print(f"Raw edge: {raw_edge*100:.2f}%")
        print(f"Stat/Dir multiplier: {stat_dir_mult}")
        print(f"Sample size multiplier: {sample_mult}")
        print(f"Effective edge: {effective_edge*100:.2f}%")
        print(f"Effective probability: {effective_prob*100:.1f}%")
        print(f"TIER: {tier}")
    
    return result


def batch_analyze(plays: list, verbose: bool = False) -> Dict:
    """
    Analyze a batch of plays and return summary.
    """
    results = []
    tier_counts = {'SLAM': 0, 'STRONG': 0, 'LEAN': 0, 'WATCH': 0, 'NO_PLAY': 0, 'VETO': 0}
    
    for play in plays:
        r = calculate_hybrid_confidence(
            mu=play.get('mu', play.get('mean', 0)),
            sigma=play.get('sigma', play.get('std', play.get('mu', 0) * 0.2)),
            line=play.get('line', 0),
            n_games=play.get('n_games', play.get('games', 10)),
            stat=play.get('stat', play.get('stat_type', '')),
            direction=play.get('direction', 'higher'),
            verbose=verbose
        )
        r['player'] = play.get('player', play.get('name', ''))
        results.append(r)
        tier_counts[r['tier']] += 1
    
    return {
        'plays': results,
        'tier_counts': tier_counts,
        'total': len(plays),
        'actionable': tier_counts['SLAM'] + tier_counts['STRONG'] + tier_counts['LEAN']
    }


# === TEST ===
if __name__ == "__main__":
    print("=" * 60)
    print("HYBRID CONFIDENCE SYSTEM TEST")
    print("=" * 60)
    
    # Test cases
    test_plays = [
        {'player': 'Joel Embiid', 'mu': 28.4, 'sigma': 6.5, 'line': 27.5, 'n_games': 15, 'stat': 'pts', 'direction': 'higher'},
        {'player': 'Trae Young', 'mu': 11.5, 'sigma': 3.0, 'line': 10.5, 'n_games': 20, 'stat': 'ast', 'direction': 'higher'},
        {'player': 'Steph Curry', 'mu': 4.2, 'sigma': 2.1, 'line': 3.5, 'n_games': 18, 'stat': '3pm', 'direction': 'higher'},
        {'player': 'High Variance', 'mu': 15.0, 'sigma': 8.0, 'line': 14.5, 'n_games': 8, 'stat': 'pts', 'direction': 'higher'},
        {'player': 'Small Sample', 'mu': 20.0, 'sigma': 5.0, 'line': 18.5, 'n_games': 4, 'stat': 'pts', 'direction': 'higher'},
        {'player': 'WR Receptions', 'mu': 5.0, 'sigma': 2.0, 'line': 4.5, 'n_games': 10, 'stat': 'recs', 'direction': 'higher'},
    ]
    
    for play in test_plays:
        r = calculate_hybrid_confidence(
            mu=play['mu'],
            sigma=play['sigma'],
            line=play['line'],
            n_games=play['n_games'],
            stat=play['stat'],
            direction=play['direction'],
            verbose=False
        )
        
        print(f"\n{play['player']} | {play['stat'].upper()} {play['direction']} {play['line']}")
        print(f"  μ={play['mu']}, σ={play['sigma']}, n={play['n_games']}")
        
        if 'reason' in r:
            print(f"  TIER: {r['tier']} - {r['reason']}")
        else:
            print(f"  Raw: {r['raw_probability']}% | Edge: {r['raw_edge']}%")
            print(f"  Adj: {r['effective_probability']}% | Eff Edge: {r['effective_edge']}%")
            print(f"  TIER: {r['tier']}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    summary = batch_analyze(test_plays)
    print(f"Total plays: {summary['total']}")
    print(f"Actionable: {summary['actionable']}")
    print(f"Tiers: {summary['tier_counts']}")
