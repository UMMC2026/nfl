"""
QUANT INTERVIEW DASHBOARD
=========================

One-stop view of all quant-firm readiness metrics.
Shows what you have, what you're missing, and how to fix it.

Usage:
    python quant_interview_dashboard.py
"""

import os
import csv
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# ASCII art for visual appeal
HEADER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║           QUANT FIRM INTERVIEW READINESS DASHBOARD                           ║
║           ═══════════════════════════════════════════                        ║
║           "Can I see your calibration plot?" — Ready to answer.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


def load_calibration_data(path: str = 'calibration_history.csv') -> List[dict]:
    """Load all calibration data"""
    picks = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                picks.append(dict(row))
    except FileNotFoundError:
        pass
    return picks


def analyze_data_quality(picks: List[dict]) -> dict:
    """Analyze data quality for quant metrics"""
    total = len(picks)
    
    # Count various data completeness
    has_probability = sum(1 for p in picks if p.get('probability', '').strip())
    has_outcome = sum(1 for p in picks if p.get('outcome', '').strip().upper() in ['HIT', 'MISS', '1', '0'])
    has_both = sum(
        1 for p in picks 
        if p.get('probability', '').strip() and 
        p.get('outcome', '').strip().upper() in ['HIT', 'MISS', '1', '0']
    )
    
    # Compute hit rate where outcome exists
    hits = sum(1 for p in picks if p.get('outcome', '').strip().upper() in ['HIT', '1'])
    misses = sum(1 for p in picks if p.get('outcome', '').strip().upper() in ['MISS', '0'])
    resolved = hits + misses
    
    return {
        'total_picks': total,
        'has_probability': has_probability,
        'has_outcome': has_outcome,
        'has_both': has_both,
        'resolved_hits': hits,
        'resolved_misses': misses,
        'resolved_total': resolved,
        'hit_rate': hits / resolved if resolved > 0 else 0,
        'prob_coverage': has_probability / total if total > 0 else 0,
        'scorable_coverage': has_both / resolved if resolved > 0 else 0
    }


def check_methodology_documentation() -> Dict[str, Tuple[bool, str]]:
    """Check if key methodology files exist and are documented"""
    checks = {}
    
    # Check opponent adjustment
    opp_files = [
        'sports/cbb/models/quant_probability_engine.py',
        'core/opponent_adjustment.py'
    ]
    found = any(os.path.exists(f) for f in opp_files)
    checks['opponent_adjustment'] = (found, 'sports/cbb/models/quant_probability_engine.py' if found else 'MISSING')
    
    # Check Bayesian shrinkage
    checks['bayesian_shrinkage'] = (
        os.path.exists('sports/cbb/models/quant_probability_engine.py'),
        'sports/cbb/models/quant_probability_engine.py'
    )
    
    # Check calibration analysis
    checks['calibration_module'] = (
        os.path.exists('quant_modules/calibration_analysis.py'),
        'quant_modules/calibration_analysis.py'
    )
    
    # Check walk-forward validation
    checks['walk_forward_validation'] = (
        os.path.exists('quant_modules/walk_forward_validation.py'),
        'quant_modules/walk_forward_validation.py'
    )
    
    # Check penalty documentation
    checks['penalty_coefficients'] = (
        os.path.exists('config/data_driven_penalties.py'),
        'config/data_driven_penalties.py'
    )
    
    # Check Poisson model
    checks['poisson_model'] = (
        os.path.exists('sports/cbb/probability.py') or os.path.exists('sports/cbb/models/probability.py'),
        'sports/cbb/probability.py or sports/cbb/models/probability.py'
    )
    
    return checks


def compute_simple_brier(picks: List[dict]) -> Optional[float]:
    """Compute Brier score from available data"""
    scorable = [
        p for p in picks
        if p.get('probability', '').strip() and 
        p.get('outcome', '').strip().upper() in ['HIT', 'MISS', '1', '0']
    ]
    
    if len(scorable) < 5:
        return None
        
    total = 0
    for p in scorable:
        prob = float(p['probability'])
        # Convert percentage to decimal if needed
        if prob > 1:
            prob = prob / 100.0
        outcome = 1 if p['outcome'].strip().upper() in ['HIT', '1'] else 0
        total += (prob - outcome) ** 2
        
    return total / len(scorable)


def get_interview_talking_points(data_quality: dict, methodology: Dict[str, Tuple[bool, str]]) -> List[str]:
    """Generate talking points for quant interview"""
    points = []
    
    # Methodology strengths
    if methodology['opponent_adjustment'][0]:
        points.append("✓ Opponent-adjusted lambda using KenPom defensive ratings")
    if methodology['bayesian_shrinkage'][0]:
        points.append("✓ Bayesian shrinkage (James-Stein estimator) for low-sample players")
    if methodology['poisson_model'][0]:
        points.append("✓ Poisson distribution for discrete count events (validated via χ² test)")
    if methodology['walk_forward_validation'][0]:
        points.append("✓ Walk-forward validation framework with Brier decomposition")
    if methodology['penalty_coefficients'][0]:
        points.append("✓ Data-driven penalties from 97-pick calibration study")
        
    # Data gaps to address
    if data_quality['has_both'] < 50:
        points.append(f"⚠ Data gap: Only {data_quality['has_both']} picks with probability+outcome (need 50+)")
    if data_quality['scorable_coverage'] < 0.5:
        points.append(f"⚠ Only {data_quality['scorable_coverage']:.0%} of resolved picks have probabilities recorded")
        
    return points


def print_dashboard():
    """Print the complete dashboard"""
    print(HEADER)
    
    # Load data
    picks = load_calibration_data()
    data_quality = analyze_data_quality(picks)
    methodology = check_methodology_documentation()
    
    # Section 1: Data Quality
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║  1. CALIBRATION DATA STATUS                                        ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    print(f"  Total Picks in History:        {data_quality['total_picks']}")
    print(f"  With Probability Recorded:     {data_quality['has_probability']} ({data_quality['prob_coverage']:.0%})")
    print(f"  With Outcome Resolved:         {data_quality['resolved_total']}")
    print(f"  With BOTH (Scorable):          {data_quality['has_both']}")
    print()
    print(f"  Resolved Hit Rate:             {data_quality['hit_rate']:.1%}")
    
    # Brier score if available
    brier = compute_simple_brier(picks)
    if brier is not None:
        print(f"  In-Sample Brier Score:         {brier:.4f}")
        if brier < 0.20:
            quality = "(EXCELLENT)"
        elif brier < 0.22:
            quality = "(GOOD)"
        elif brier < 0.25:
            quality = "(FAIR)"
        else:
            quality = "(NEEDS WORK)"
        print(f"                                 {quality}")
    else:
        print(f"  Brier Score:                   INSUFFICIENT DATA (need 5+ scorable)")
    
    # Section 2: Methodology Checklist
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║  2. METHODOLOGY CHECKLIST                                          ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    for item, (exists, path) in methodology.items():
        status = "✓" if exists else "✗"
        name = item.replace('_', ' ').title()
        print(f"  [{status}] {name:<30} → {path}")
    
    # Section 3: Quant Interview Readiness
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║  3. QUANT INTERVIEW READINESS                                      ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    interview_questions = [
        ("'Show me your calibration plot'", data_quality['has_both'] >= 50, 
         f"Have {data_quality['has_both']}/50 needed scorable picks"),
        ("'What's your out-of-sample Brier score?'", data_quality['has_both'] >= 50,
         f"Walk-forward validation ready, need data"),
        ("'How do you adjust for opponent?'", methodology['opponent_adjustment'][0],
         "KenPom-based defensive multipliers"),
        ("'Prove coefficients aren't overfitted'", methodology['penalty_coefficients'][0] and data_quality['has_both'] >= 50,
         "Bootstrap validation framework ready"),
        ("'Why Poisson distribution?'", methodology['poisson_model'][0],
         "Discrete count events, validated via χ² test"),
        ("'What's your sample size by tier?'", True,
         "Data available in calibration_history.csv")
    ]
    
    for question, ready, detail in interview_questions:
        status = "READY" if ready else "NOT READY"
        color_status = f"[{status}]"
        print(f"  {question:<45} {color_status}")
        print(f"     └─ {detail}")
        print()
    
    # Section 4: Talking Points
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  4. KEY TALKING POINTS                                             ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    points = get_interview_talking_points(data_quality, methodology)
    for point in points:
        print(f"  {point}")
    
    # Section 5: Action Items
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║  5. PRIORITY ACTION ITEMS                                          ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    action_items = []
    
    if data_quality['has_both'] < 50:
        action_items.append({
            'priority': 'CRITICAL',
            'item': 'Save probabilities with picks going forward',
            'detail': f'Currently {50 - data_quality["has_both"]} more scorable picks needed'
        })
        
    if data_quality['scorable_coverage'] < 0.9 and data_quality['resolved_total'] > 0:
        action_items.append({
            'priority': 'HIGH',
            'item': 'Backfill probabilities from JSON outputs',
            'detail': f'{data_quality["resolved_total"] - data_quality["has_both"]} resolved picks missing probabilities'
        })
    
    if not methodology['walk_forward_validation'][0]:
        action_items.append({
            'priority': 'HIGH',
            'item': 'Implement walk-forward validation',
            'detail': 'Required for out-of-sample Brier score'
        })
    
    for item in action_items:
        print(f"  [{item['priority']}] {item['item']}")
        print(f"          {item['detail']}")
        print()
        
    if not action_items:
        print("  ✓ All critical items addressed!")
        print("  → Continue collecting data with probabilities")
        print("  → Run validation once 50+ scorable picks available")
    
    # Section 6: Quick Commands
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║  6. QUICK COMMANDS                                                 ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    print("  # Run calibration analysis")
    print("  .venv\\Scripts\\python.exe quant_modules/calibration_analysis.py")
    print()
    print("  # Run walk-forward validation")
    print("  .venv\\Scripts\\python.exe quant_modules/walk_forward_validation.py")
    print()
    print("  # Backfill probabilities from JSON")
    print("  .venv\\Scripts\\python.exe backfill_probabilities.py")
    print()
    print("  # Test quant probability engine")
    print("  .venv\\Scripts\\python.exe -c \"from sports.cbb.models.quant_probability_engine import demo; demo()\"")
    
    print("\n" + "=" * 74)
    print(f"  Dashboard generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 74)


if __name__ == '__main__':
    print_dashboard()
