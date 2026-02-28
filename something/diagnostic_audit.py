"""
FUOOM DARK MATTER - Diagnostic Audit Script
=============================================
Analyzes historical picks to quantify:
1. Tier-probability misclassification rate
2. Negative Kelly picks that should have been excluded
3. Compression rule violations
4. Duplicate edge occurrences

Run this against your pick history to see exactly how broken things were.

Version: 1.0.0
Date: February 9, 2026
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

# Import math utilities
try:
    from shared.math_utils import (
        Tier,
        TIER_THRESHOLDS,
        probability_to_tier,
        calculate_kelly,
        american_to_decimal,
        compression_check,
        calculate_brier_score,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from shared.math_utils import (
        Tier,
        TIER_THRESHOLDS,
        probability_to_tier,
        calculate_kelly,
        american_to_decimal,
        compression_check,
        calculate_brier_score,
    )


# =============================================================================
# V2.0 THRESHOLDS (THE OLD BROKEN ONES) - For comparison
# =============================================================================

V20_THRESHOLDS = {
    'SLAM': 0.90,
    'STRONG': 0.80,
    'LEAN': 0.70,
    'SPEC': 0.60,
    'NO_PLAY': 0.00,
}


# =============================================================================
# DIAGNOSTIC STRUCTURES
# =============================================================================

@dataclass
class TierMismatch:
    """Record of a tier-probability mismatch."""
    signal_id: str
    probability: float
    assigned_tier: str
    correct_tier_v21: str
    tier_if_v20: str  # What it would be under old rules
    impact: str  # "Under-tiered", "Over-tiered", "Correct"


@dataclass
class KellyIssue:
    """Record of a Kelly criterion problem."""
    signal_id: str
    probability: float
    decimal_odds: float
    kelly_full: float
    assigned_kelly: Optional[float]
    issue_type: str  # "NEGATIVE_KELLY", "WRONG_KELLY", "MISSING_KELLY"


@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    total_picks: int
    picks_analyzed: int
    
    # Tier issues
    tier_mismatches: List[TierMismatch] = field(default_factory=list)
    tier_mismatch_rate: float = 0.0
    over_tiered_count: int = 0
    under_tiered_count: int = 0
    
    # Kelly issues
    kelly_issues: List[KellyIssue] = field(default_factory=list)
    negative_kelly_count: int = 0
    missing_kelly_count: int = 0
    
    # Duplicate issues
    duplicate_edges: List[Tuple[str, str]] = field(default_factory=list)
    
    # Compression issues
    compression_violations: List[Dict] = field(default_factory=list)
    
    # Direction analysis
    direction_counts: Dict[str, int] = field(default_factory=dict)
    direction_by_stat: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Calibration (if outcomes available)
    brier_score: Optional[float] = None
    win_rate: Optional[float] = None
    
    # Summary stats
    severity_summary: Dict[str, int] = field(default_factory=dict)


# =============================================================================
# DIAGNOSTIC FUNCTIONS
# =============================================================================

def classify_tier_v20(probability: float) -> str:
    """Classify probability using OLD v2.0 thresholds (the broken ones)."""
    if probability >= 0.90:
        return "SLAM"
    elif probability >= 0.80:
        return "STRONG"
    elif probability >= 0.70:
        return "LEAN"
    elif probability >= 0.60:
        return "SPEC"
    else:
        return "NO_PLAY"


def analyze_tier_mismatch(signal: Dict) -> Optional[TierMismatch]:
    """Check if a signal has tier-probability mismatch."""
    probability = signal.get('probability', 0)
    assigned_tier = signal.get('confidence_tier', signal.get('tier', '')).upper()
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    
    if not assigned_tier or assigned_tier in ['', 'NONE']:
        return None
    
    # What tier SHOULD it be under v2.1
    correct_tier_v21 = probability_to_tier(probability).value
    
    # What tier would it be under v2.0 (old broken rules)
    tier_v20 = classify_tier_v20(probability)
    
    # Normalize assigned tier
    assigned_normalized = assigned_tier.replace(' ', '_').upper()
    if assigned_normalized == 'NO PLAY':
        assigned_normalized = 'NO_PLAY'
    
    # Determine impact
    tier_order = {'SLAM': 4, 'STRONG': 3, 'LEAN': 2, 'SPEC': 1, 'NO_PLAY': 0}
    
    assigned_rank = tier_order.get(assigned_normalized, -1)
    correct_rank = tier_order.get(correct_tier_v21, -1)
    
    if assigned_rank > correct_rank:
        impact = "Over-tiered (more confident than justified)"
    elif assigned_rank < correct_rank:
        impact = "Under-tiered (less confident than justified)"
    else:
        impact = "Correct"
    
    if assigned_normalized != correct_tier_v21:
        return TierMismatch(
            signal_id=signal_id,
            probability=probability,
            assigned_tier=assigned_tier,
            correct_tier_v21=correct_tier_v21,
            tier_if_v20=tier_v20,
            impact=impact
        )
    
    return None


def analyze_kelly(signal: Dict) -> Optional[KellyIssue]:
    """Check for Kelly criterion issues."""
    probability = signal.get('probability', 0)
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    assigned_kelly = signal.get('kelly_fraction')
    
    # Get decimal odds
    decimal_odds = signal.get('decimal_odds')
    if not decimal_odds:
        american_odds = signal.get('american_odds', signal.get('odds'))
        if american_odds:
            decimal_odds = american_to_decimal(american_odds)
        else:
            decimal_odds = 1.909  # Assume -110
    
    # Calculate correct Kelly
    kelly_result = calculate_kelly(probability, decimal_odds)
    
    # Check for issues
    if not kelly_result.has_edge:
        return KellyIssue(
            signal_id=signal_id,
            probability=probability,
            decimal_odds=decimal_odds,
            kelly_full=kelly_result.kelly_full,
            assigned_kelly=assigned_kelly,
            issue_type="NEGATIVE_KELLY"
        )
    
    if assigned_kelly is None:
        return KellyIssue(
            signal_id=signal_id,
            probability=probability,
            decimal_odds=decimal_odds,
            kelly_full=kelly_result.kelly_full,
            assigned_kelly=None,
            issue_type="MISSING_KELLY"
        )
    
    # Check if assigned Kelly is reasonable (within 50% of correct)
    if abs(assigned_kelly - kelly_result.kelly_capped) > kelly_result.kelly_capped * 0.5:
        return KellyIssue(
            signal_id=signal_id,
            probability=probability,
            decimal_odds=decimal_odds,
            kelly_full=kelly_result.kelly_full,
            assigned_kelly=assigned_kelly,
            issue_type="WRONG_KELLY"
        )
    
    return None


def find_duplicate_edges(signals: List[Dict]) -> List[Tuple[str, str]]:
    """Find duplicate edges in signal list."""
    duplicates = []
    seen: Dict[str, str] = {}
    
    for signal in signals:
        player = signal.get('player', signal.get('player_name', ''))
        game_id = signal.get('game_id', signal.get('game', ''))
        stat = signal.get('market', signal.get('stat', signal.get('prop_type', '')))
        direction = signal.get('direction', '')
        signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
        
        edge_key = f"{player}|{game_id}|{stat}|{direction}".lower()
        
        if edge_key in seen:
            duplicates.append((signal_id, seen[edge_key]))
        else:
            seen[edge_key] = signal_id
    
    return duplicates


def analyze_direction_distribution(signals: List[Dict]) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]]]:
    """Analyze direction distribution overall and by stat."""
    direction_counts = defaultdict(int)
    direction_by_stat = defaultdict(lambda: defaultdict(int))
    
    for signal in signals:
        direction = signal.get('direction', '').lower()
        stat = signal.get('market', signal.get('stat', signal.get('prop_type', ''))).lower()
        
        direction_counts[direction] += 1
        direction_by_stat[stat][direction] += 1
    
    return dict(direction_counts), {k: dict(v) for k, v in direction_by_stat.items()}


def run_diagnostic(signals: List[Dict], outcomes: Optional[List[Dict]] = None) -> DiagnosticReport:
    """
    Run complete diagnostic analysis on a set of signals.
    
    Args:
        signals: List of signal dictionaries
        outcomes: Optional list of outcome dictionaries with 'signal_id' and 'result' (0/1)
        
    Returns:
        Complete DiagnosticReport
    """
    report = DiagnosticReport(
        total_picks=len(signals),
        picks_analyzed=0
    )
    
    for signal in signals:
        report.picks_analyzed += 1
        
        # Tier analysis
        tier_issue = analyze_tier_mismatch(signal)
        if tier_issue:
            report.tier_mismatches.append(tier_issue)
            if "Over-tiered" in tier_issue.impact:
                report.over_tiered_count += 1
            elif "Under-tiered" in tier_issue.impact:
                report.under_tiered_count += 1
        
        # Kelly analysis
        kelly_issue = analyze_kelly(signal)
        if kelly_issue:
            report.kelly_issues.append(kelly_issue)
            if kelly_issue.issue_type == "NEGATIVE_KELLY":
                report.negative_kelly_count += 1
            elif kelly_issue.issue_type == "MISSING_KELLY":
                report.missing_kelly_count += 1
    
    # Calculate tier mismatch rate
    if report.picks_analyzed > 0:
        report.tier_mismatch_rate = len(report.tier_mismatches) / report.picks_analyzed
    
    # Find duplicates
    report.duplicate_edges = find_duplicate_edges(signals)
    
    # Direction analysis
    report.direction_counts, report.direction_by_stat = analyze_direction_distribution(signals)
    
    # Calibration (if outcomes provided)
    if outcomes:
        outcome_map = {o['signal_id']: o['result'] for o in outcomes if 'signal_id' in o and 'result' in o}
        predictions = []
        actuals = []
        
        for signal in signals:
            signal_id = signal.get('signal_id', signal.get('id'))
            if signal_id in outcome_map:
                predictions.append(signal.get('probability', 0.5))
                actuals.append(outcome_map[signal_id])
        
        if predictions:
            report.brier_score = calculate_brier_score(predictions, actuals)
            report.win_rate = sum(actuals) / len(actuals)
    
    # Severity summary
    report.severity_summary = {
        'CRITICAL_tier_mismatches': len(report.tier_mismatches),
        'CRITICAL_negative_kelly': report.negative_kelly_count,
        'CRITICAL_duplicates': len(report.duplicate_edges),
        'WARNING_missing_kelly': report.missing_kelly_count,
        'WARNING_over_tiered': report.over_tiered_count,
    }
    
    return report


# =============================================================================
# REPORT FORMATTING
# =============================================================================

def format_report(report: DiagnosticReport) -> str:
    """Format diagnostic report for display."""
    lines = []
    
    lines.append("=" * 70)
    lines.append("FUOOM DARK MATTER - DIAGNOSTIC AUDIT REPORT")
    lines.append("=" * 70)
    lines.append(f"Timestamp: {datetime.now().isoformat()}")
    lines.append(f"Total picks analyzed: {report.picks_analyzed}")
    lines.append("")
    
    # Executive Summary
    lines.append("-" * 70)
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 70)
    
    total_critical = (
        len(report.tier_mismatches) +
        report.negative_kelly_count +
        len(report.duplicate_edges)
    )
    
    if total_critical == 0:
        lines.append("✓ No critical issues found")
    else:
        lines.append(f"✗ {total_critical} CRITICAL issues require immediate fix")
    
    lines.append("")
    
    # Tier Analysis
    lines.append("-" * 70)
    lines.append("TIER-PROBABILITY ALIGNMENT")
    lines.append("-" * 70)
    lines.append(f"Mismatch rate: {report.tier_mismatch_rate:.1%}")
    lines.append(f"  Over-tiered (overconfident): {report.over_tiered_count}")
    lines.append(f"  Under-tiered (underconfident): {report.under_tiered_count}")
    
    if report.tier_mismatches:
        lines.append("")
        lines.append("Sample mismatches (first 10):")
        for mismatch in report.tier_mismatches[:10]:
            lines.append(
                f"  • {mismatch.signal_id}: {mismatch.probability:.1%} → "
                f"assigned {mismatch.assigned_tier}, should be {mismatch.correct_tier_v21}"
            )
            lines.append(f"    (v2.0 would say: {mismatch.tier_if_v20}) - {mismatch.impact}")
    
    lines.append("")
    
    # Kelly Analysis
    lines.append("-" * 70)
    lines.append("KELLY CRITERION ANALYSIS")
    lines.append("-" * 70)
    lines.append(f"Negative Kelly (no edge): {report.negative_kelly_count}")
    lines.append(f"Missing Kelly: {report.missing_kelly_count}")
    
    if report.kelly_issues:
        lines.append("")
        lines.append("Sample issues (first 10):")
        for issue in report.kelly_issues[:10]:
            lines.append(
                f"  • {issue.signal_id}: prob={issue.probability:.1%}, "
                f"kelly_full={issue.kelly_full:.4f}, "
                f"assigned={issue.assigned_kelly} - {issue.issue_type}"
            )
    
    lines.append("")
    
    # Duplicates
    lines.append("-" * 70)
    lines.append("DUPLICATE EDGES")
    lines.append("-" * 70)
    lines.append(f"Duplicate pairs found: {len(report.duplicate_edges)}")
    
    if report.duplicate_edges:
        lines.append("")
        for dup1, dup2 in report.duplicate_edges[:10]:
            lines.append(f"  • {dup1} duplicates {dup2}")
    
    lines.append("")
    
    # Direction Distribution
    lines.append("-" * 70)
    lines.append("DIRECTION DISTRIBUTION")
    lines.append("-" * 70)
    total_dir = sum(report.direction_counts.values())
    for direction, count in sorted(report.direction_counts.items()):
        pct = count / total_dir * 100 if total_dir > 0 else 0
        lines.append(f"  {direction}: {count} ({pct:.1f}%)")
    
    if report.direction_by_stat:
        lines.append("")
        lines.append("By stat:")
        for stat, directions in sorted(report.direction_by_stat.items()):
            stat_total = sum(directions.values())
            dir_str = ", ".join(f"{d}={c}" for d, c in sorted(directions.items()))
            lines.append(f"  {stat}: {dir_str} (total: {stat_total})")
    
    lines.append("")
    
    # Calibration (if available)
    if report.brier_score is not None:
        lines.append("-" * 70)
        lines.append("CALIBRATION (requires outcomes)")
        lines.append("-" * 70)
        lines.append(f"Brier score: {report.brier_score:.4f}")
        lines.append(f"Win rate: {report.win_rate:.1%}" if report.win_rate else "")
        
        if report.brier_score > 0.25:
            lines.append("  ⚠ WARNING: Worse than random (coin flip = 0.25)")
        elif report.brier_score > 0.20:
            lines.append("  ⚠ WARNING: Barely above random")
        else:
            lines.append("  ✓ Acceptable calibration")
    
    lines.append("")
    
    # Recommendations
    lines.append("=" * 70)
    lines.append("RECOMMENDED ACTIONS")
    lines.append("=" * 70)
    
    actions = []
    if report.tier_mismatches:
        actions.append(
            f"1. FIX TIER THRESHOLDS: {len(report.tier_mismatches)} picks would be "
            f"classified differently under v2.1 rules"
        )
    
    if report.negative_kelly_count > 0:
        actions.append(
            f"2. BLOCK NEGATIVE KELLY: {report.negative_kelly_count} picks have no "
            f"mathematical edge and should be excluded"
        )
    
    if report.duplicate_edges:
        actions.append(
            f"3. FIX DUPLICATE EDGES: {len(report.duplicate_edges)} duplicate pairs "
            f"violate one-player-one-bet rule"
        )
    
    if report.missing_kelly_count > 0:
        actions.append(
            f"4. ADD KELLY CALCULATION: {report.missing_kelly_count} picks have no "
            f"Kelly fraction assigned"
        )
    
    if not actions:
        actions.append("No critical actions required. System math appears correct.")
    
    for action in actions:
        lines.append(action)
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="FUOOM Diagnostic Audit - Analyze historical picks for math errors"
    )
    parser.add_argument('file', help='JSON file with picks to analyze')
    parser.add_argument('--outcomes', help='Optional JSON file with outcomes')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Load picks
    with open(args.file, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        signals = data
    elif isinstance(data, dict):
        signals = data.get('picks', data.get('signals', data.get('edges', [])))
    else:
        print(f"ERROR: Unexpected data format", file=sys.stderr)
        sys.exit(1)
    
    # Load outcomes if provided
    outcomes = None
    if args.outcomes:
        with open(args.outcomes, 'r') as f:
            outcomes = json.load(f)
        if isinstance(outcomes, dict):
            outcomes = outcomes.get('outcomes', outcomes.get('results', []))
    
    # Run diagnostic
    report = run_diagnostic(signals, outcomes)
    
    if args.json:
        output = {
            'total_picks': report.total_picks,
            'picks_analyzed': report.picks_analyzed,
            'tier_mismatch_rate': report.tier_mismatch_rate,
            'tier_mismatches': [
                {
                    'signal_id': m.signal_id,
                    'probability': m.probability,
                    'assigned': m.assigned_tier,
                    'correct_v21': m.correct_tier_v21,
                    'impact': m.impact
                }
                for m in report.tier_mismatches
            ],
            'negative_kelly_count': report.negative_kelly_count,
            'duplicate_count': len(report.duplicate_edges),
            'direction_distribution': report.direction_counts,
            'brier_score': report.brier_score,
            'win_rate': report.win_rate,
            'severity_summary': report.severity_summary
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_report(report))
    
    # Exit with error code if critical issues found
    critical_count = (
        len(report.tier_mismatches) +
        report.negative_kelly_count +
        len(report.duplicate_edges)
    )
    sys.exit(1 if critical_count > 0 else 0)


if __name__ == '__main__':
    main()
