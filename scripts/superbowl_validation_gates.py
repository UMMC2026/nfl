"""
SUPER BOWL VALIDATION GATES
Extra strict validation for Super Bowl picks
"""

import numpy as np
from scipy.stats import norm


def apply_over_bias_correction(pick):
    """
    Apply correction for historical OVER bias (37.5% win rate)
    
    Args:
        pick: Dict with keys: probability, direction, tier
    
    Returns:
        Modified pick with OVER bias correction applied
    """
    
    if pick['direction'].lower() in ['over', 'higher', 'more']:
        # Historical OVER win rate: 37.5% (3/8 picks)
        # This is 32% below expected 55% break-even
        # Apply confidence haircut
        
        original_prob = pick['probability']
        
        # 15% haircut for all OVERs
        pick['probability'] *= 0.85
        
        # Raise minimum threshold
        if pick['probability'] < 0.68:  # Normally 60% for LEAN
            pick['tier'] = 'NO_PLAY'
            pick['warnings'] = pick.get('warnings', [])
            pick['warnings'].append({
                'type': 'OVER_BIAS',
                'message': f'Historical OVER bias (37.5% win rate) - reduced {original_prob:.1%} → {pick["probability"]:.1%}',
                'action': 'BLOCKED'
            })
        else:
            # Still playable but flagged
            pick['warnings'] = pick.get('warnings', [])
            pick['warnings'].append({
                'type': 'OVER_BIAS',
                'message': f'CAUTION: Historical OVER bias - probability adjusted down',
                'action': 'REDUCED_CONFIDENCE'
            })
    
    return pick


def superbowl_validation_gates(pick):
    """
    Super Bowl specific validation gates (stricter than regular season)
    
    Args:
        pick: Dict with keys: player, stat, line, direction, mu, sigma, 
              probability, edge, games_in_sample, playoff_games
    
    Returns:
        Dict with 'passed' (bool) and 'gates' (list of gate results)
    """
    
    gates = []
    
    # Extract pick details
    mu = pick.get('mu', 0)
    sigma = pick.get('sigma', 0)
    line = pick.get('line', 0)
    probability = pick.get('probability', 0)
    direction = pick.get('direction', '').lower()
    
    # Gate 1: NULL mu/sigma check (critical!)
    if mu == 0 or sigma == 0 or mu is None or sigma is None:
        gates.append({
            'name': 'STATS_AVAILABLE',
            'status': 'FAIL',
            'severity': 'CRITICAL',
            'message': 'Missing mu/sigma - system did not calculate statistics',
            'recommendation': 'BLOCK - No valid projection data'
        })
        
        return {
            'passed': False,
            'gates': gates,
            'final_decision': 'NO_PLAY',
            'reason': 'CRITICAL: Missing statistical projections'
        }
    
    # Gate 2: Minimum edge requirement (higher for SB)
    edge = abs(mu - line)
    edge_pct = (edge / line * 100) if line > 0 else 0
    
    MIN_EDGE_SB = 7.5  # Normally 5%, but SB requires 7.5%
    
    if edge_pct < MIN_EDGE_SB:
        gates.append({
            'name': 'MINIMUM_EDGE',
            'status': 'FAIL',
            'severity': 'HIGH',
            'message': f'Edge {edge_pct:.1f}% < {MIN_EDGE_SB}% required for Super Bowl',
            'recommendation': 'BLOCK - Insufficient edge'
        })
    else:
        gates.append({
            'name': 'MINIMUM_EDGE',
            'status': 'PASS',
            'value': f'{edge_pct:.1f}%'
        })
    
    # Gate 3: Direction vs Projection check
    if direction in ['over', 'higher', 'more']:
        if mu < line:
            gates.append({
                'name': 'PROJECTION_ALIGNMENT',
                'status': 'FAIL',
                'severity': 'CRITICAL',
                'message': f'Betting OVER {line} but projecting UNDER (μ={mu:.1f})',
                'recommendation': 'BLOCK - Contradictory projection'
            })
        else:
            gates.append({
                'name': 'PROJECTION_ALIGNMENT',
                'status': 'PASS',
                'value': f'μ={mu:.1f} > line={line}'
            })
    else:  # under
        if mu > line:
            gates.append({
                'name': 'PROJECTION_ALIGNMENT',
                'status': 'FAIL',
                'severity': 'CRITICAL',
                'message': f'Betting UNDER {line} but projecting OVER (μ={mu:.1f})',
                'recommendation': 'BLOCK - Contradictory projection'
            })
        else:
            gates.append({
                'name': 'PROJECTION_ALIGNMENT',
                'status': 'PASS',
                'value': f'μ={mu:.1f} < line={line}'
            })
    
    # Gate 4: Variance check (coefficient of variation)
    cv = sigma / mu if mu != 0 else 999
    MAX_CV_SB = 0.25  # Normally 30%, but SB requires tighter (25%)
    
    if cv > MAX_CV_SB:
        gates.append({
            'name': 'VARIANCE_CHECK',
            'status': 'FAIL',
            'severity': 'MEDIUM',
            'message': f'High variance: CV={cv:.2f} > {MAX_CV_SB:.2f}',
            'recommendation': 'CAUTION - High uncertainty'
        })
    else:
        gates.append({
            'name': 'VARIANCE_CHECK',
            'status': 'PASS',
            'value': f'CV={cv:.2f}'
        })
    
    # Gate 5: Sample size check
    games = pick.get('games_in_sample', 0)
    MIN_GAMES_SB = 10
    
    if games < MIN_GAMES_SB:
        gates.append({
            'name': 'SAMPLE_SIZE',
            'status': 'WARNING',
            'severity': 'MEDIUM',
            'message': f'Only {games} games in sample (need {MIN_GAMES_SB}+)',
            'recommendation': 'CAUTION - Small sample'
        })
    else:
        gates.append({
            'name': 'SAMPLE_SIZE',
            'status': 'PASS',
            'value': f'{games} games'
        })
    
    # Gate 6: Playoff experience
    playoff_games = pick.get('playoff_games', 0)
    
    if playoff_games < 3:
        gates.append({
            'name': 'PLAYOFF_EXPERIENCE',
            'status': 'WARNING',
            'severity': 'LOW',
            'message': f'Player has only {playoff_games} playoff games',
            'recommendation': 'CAUTION - Limited playoff data'
        })
    else:
        gates.append({
            'name': 'PLAYOFF_EXPERIENCE',
            'status': 'PASS',
            'value': f'{playoff_games} games'
        })
    
    # Gate 7: OVER bias filter
    if direction in ['over', 'higher', 'more']:
        MIN_PROB_OVER = 0.68  # Normally 60%, but OVERs need 68%
        
        if probability < MIN_PROB_OVER:
            gates.append({
                'name': 'OVER_BIAS_FILTER',
                'status': 'FAIL',
                'severity': 'HIGH',
                'message': f'OVER bet at {probability:.1%} < {MIN_PROB_OVER:.0%} threshold',
                'recommendation': 'BLOCK - Historical OVER bias (37.5% win rate)'
            })
        else:
            gates.append({
                'name': 'OVER_BIAS_FILTER',
                'status': 'PASS',
                'value': f'{probability:.1%} >= {MIN_PROB_OVER:.0%}'
            })
    
    # Gate 8: Z-score sanity check
    z_score = (line - mu) / sigma if sigma > 0 else 0
    
    if abs(z_score) > 3:
        gates.append({
            'name': 'Z_SCORE_CHECK',
            'status': 'WARNING',
            'severity': 'MEDIUM',
            'message': f'Extreme z-score: {z_score:.2f} (line is {abs(z_score):.1f}σ from mean)',
            'recommendation': 'CAUTION - Unusual line'
        })
    else:
        gates.append({
            'name': 'Z_SCORE_CHECK',
            'status': 'PASS',
            'value': f'z={z_score:.2f}'
        })
    
    # Determine overall pass/fail
    failures = [g for g in gates if g['status'] == 'FAIL']
    warnings = [g for g in gates if g['status'] == 'WARNING']
    
    # Final decision
    if len(failures) > 0:
        passed = False
        final_decision = 'NO_PLAY'
        reason = f"{len(failures)} gate failure(s): " + ", ".join([g['name'] for g in failures])
    elif len(warnings) > 2:
        passed = False
        final_decision = 'NO_PLAY'
        reason = f"Too many warnings ({len(warnings)}) - insufficient confidence"
    else:
        passed = True
        final_decision = pick.get('tier', 'LEAN')
        reason = "All critical gates passed"
    
    return {
        'passed': passed,
        'gates': gates,
        'final_decision': final_decision,
        'reason': reason,
        'failures': len(failures),
        'warnings': len(warnings)
    }


def validate_superbowl_pick(pick):
    """
    Complete validation for a Super Bowl pick
    Combines OVER bias correction + validation gates
    
    Args:
        pick: Dict with full pick details
    
    Returns:
        Dict with validation results and final recommendation
    """
    
    # Step 1: Apply OVER bias correction
    pick = apply_over_bias_correction(pick)
    
    # Step 2: Run validation gates
    gate_results = superbowl_validation_gates(pick)
    
    # Step 3: Generate final report
    report = {
        'player': pick.get('player', 'Unknown'),
        'market': pick.get('stat', ''),
        'line': pick.get('line', 0),
        'direction': pick.get('direction', ''),
        'mu': pick.get('mu', 0),
        'sigma': pick.get('sigma', 0),
        'probability_raw': pick.get('probability_raw', pick.get('probability', 0)),
        'probability_adjusted': pick.get('probability', 0),
        'tier_original': pick.get('tier_original', pick.get('tier', '')),
        'tier_final': gate_results['final_decision'],
        'validation_passed': gate_results['passed'],
        'gate_failures': gate_results['failures'],
        'gate_warnings': gate_results['warnings'],
        'gates': gate_results['gates'],
        'warnings': pick.get('warnings', []),
        'reason': gate_results['reason']
    }
    
    return report


# Example usage
if __name__ == "__main__":
    # Test pick
    test_pick = {
        'player': 'Patrick Mahomes',
        'stat': 'Pass Yards',
        'line': 275.5,
        'direction': 'over',
        'mu': 285.3,
        'sigma': 52.1,
        'probability': 0.72,
        'tier': 'STRONG',
        'games_in_sample': 16,
        'playoff_games': 15
    }
    
    print("\n" + "=" * 80)
    print("SUPER BOWL PICK VALIDATION TEST")
    print("=" * 80 + "\n")
    
    result = validate_superbowl_pick(test_pick)
    
    print(f"Pick: {result['player']} {result['market']} {result['direction'].upper()} {result['line']}")
    print(f"Projection: μ={result['mu']:.1f}, σ={result['sigma']:.1f}")
    print(f"Probability: {result['probability_raw']:.1%} → {result['probability_adjusted']:.1%}")
    print(f"Tier: {result['tier_original']} → {result['tier_final']}")
    print(f"\nValidation: {'✅ PASSED' if result['validation_passed'] else '❌ FAILED'}")
    print(f"Reason: {result['reason']}")
    
    print(f"\nGate Results:")
    for gate in result['gates']:
        status_emoji = "✅" if gate['status'] == 'PASS' else ("⚠️" if gate['status'] == 'WARNING' else "❌")
        print(f"  {status_emoji} {gate['name']}: {gate.get('message', gate.get('value', 'OK'))}")
    
    if result['warnings']:
        print(f"\nWarnings:")
        for warning in result['warnings']:
            print(f"  ⚠️ {warning['type']}: {warning['message']}")
    
    print("\n" + "=" * 80 + "\n")
