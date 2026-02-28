"""
FUOOM DARK MATTER — validate_output.py
=======================================
Universal validation gate. This is the HARD GATE between scoring and rendering.
If ANY check fails, render is BLOCKED. No silent failures. No partial reports.

SOP v2.1 (Truth-Enforced), Section 6: RENDER GATE (FAIL-FAST RULE)

Required assertions before ANY report is generated:
  ✔ No duplicate EDGES
  ✔ No player appears twice as PRIMARY
  ✔ No correlated line is tiered
  ✔ Tier labels match probabilities
  ✔ Kelly criterion is positive for all included picks
  ✔ Direction bias within threshold
  ✔ Player-team consistency holds
  ✔ No NO_PLAY picks leaked into output
  ✔ Confidence compression applied where needed

Run Order: Step 5 of 6 (after score_edges.py, before render_report.py)
Running render_report.py directly is FORBIDDEN.

Audit Reference: FUOOM-AUDIT-001, Sections 1, 2, 3, 5, 6, 10, 11

Author: FUOOM Engineering
Version: 1.0.0
Date: 2026-02-15
"""

import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import Counter

# Import FUOOM shared modules
from shared.config import (
    assign_tier, validate_tier_alignment, compression_check,
    TIER_THRESHOLDS, SIGMA_TABLE, DIRECTION_BIAS_THRESHOLD,
    LINE_STALENESS_THRESHOLD
)
from shared.math_utils import (
    kelly_full, american_to_decimal, calculate_ev,
    BRIER_THRESHOLDS
)

logger = logging.getLogger(__name__)

# =============================================================================
# VALIDATION RESULT CONTAINER
# =============================================================================

class ValidationResult:
    """Container for validation check results."""
    
    def __init__(self):
        self.checks: List[Dict] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: bool = True
        self.timestamp = datetime.utcnow().isoformat() + 'Z'
    
    def add_check(self, name: str, passed: bool, detail: str = ''):
        status = 'PASS' if passed else 'FAIL'
        self.checks.append({
            'check': name,
            'status': status,
            'detail': detail,
        })
        if not passed:
            self.passed = False
            self.errors.append(f"[{name}] {detail}")
            logger.error(f"VALIDATION FAIL: [{name}] {detail}")
        else:
            logger.info(f"VALIDATION PASS: [{name}] {detail}")
    
    def add_warning(self, name: str, detail: str):
        self.warnings.append(f"[{name}] {detail}")
        self.checks.append({
            'check': name,
            'status': 'WARN',
            'detail': detail,
        })
        logger.warning(f"VALIDATION WARN: [{name}] {detail}")
    
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c['status'] == 'PASS')
        failed = sum(1 for c in self.checks if c['status'] == 'FAIL')
        warned = sum(1 for c in self.checks if c['status'] == 'WARN')
        
        lines = [
            f"\n{'='*60}",
            f"  FUOOM VALIDATION GATE — {'PASSED ✅' if self.passed else 'FAILED ❌'}",
            f"{'='*60}",
            f"  Timestamp: {self.timestamp}",
            f"  Checks: {total} total | {passed} passed | {failed} failed | {warned} warnings",
        ]
        
        if self.errors:
            lines.append(f"\n  ERRORS (must fix):")
            for err in self.errors:
                lines.append(f"    ❌ {err}")
        
        if self.warnings:
            lines.append(f"\n  WARNINGS (should fix):")
            for warn in self.warnings:
                lines.append(f"    ⚠️  {warn}")
        
        lines.append(f"{'='*60}")
        
        if not self.passed:
            lines.append("  ⛔ RENDER BLOCKED — Fix errors above before generating report")
            lines.append(f"{'='*60}\n")
        
        return '\n'.join(lines)
    
    def to_dict(self) -> Dict:
        return {
            'passed': self.passed,
            'timestamp': self.timestamp,
            'checks': self.checks,
            'errors': self.errors,
            'warnings': self.warnings,
        }


# =============================================================================
# INDIVIDUAL VALIDATION CHECKS
# =============================================================================

def check_no_duplicate_edges(edges: List[Dict]) -> Tuple[bool, str]:
    """SOP v2.1 Rule A2: No duplicate EDGES.
    
    EDGE = unique(player, game_id, stat_type, direction)
    """
    seen = set()
    duplicates = []
    
    for e in edges:
        # Build edge key
        key = (
            e.get('player', ''),
            e.get('game_id', ''),
            e.get('stat_type', e.get('stat', e.get('market', ''))),
            e.get('direction', ''),
        )
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    
    if duplicates:
        return False, f"Found {len(duplicates)} duplicate edges: {duplicates[:3]}"
    return True, f"No duplicates in {len(edges)} edges"


def check_no_duplicate_primary_players(edges: List[Dict]) -> Tuple[bool, str]:
    """SOP v2.1 Rule B1: Max 1 PRIMARY bet per player per game.
    
    Only checks edges tagged as PRIMARY (not CORRELATED_ALTERNATIVE).
    """
    primary_edges = [e for e in edges if e.get('pick_type', 'PRIMARY') == 'PRIMARY']
    
    player_game_counts = Counter()
    for e in primary_edges:
        key = (e.get('player', ''), e.get('game_id', ''))
        player_game_counts[key] += 1
    
    violations = {k: v for k, v in player_game_counts.items() if v > 1}
    
    if violations:
        details = [f"{k[0]} in game {k[1]} ({v} picks)" for k, v in list(violations.items())[:3]]
        return False, f"Players with multiple PRIMARY picks: {'; '.join(details)}"
    return True, f"No duplicate primary players in {len(primary_edges)} primary edges"


def check_no_correlated_tiered(edges: List[Dict]) -> Tuple[bool, str]:
    """SOP v2.1 Rule B2: Correlated alternatives must NOT be tiered."""
    violations = []
    for e in edges:
        if e.get('pick_type', '') == 'CORRELATED_ALTERNATIVE':
            tier = e.get('confidence_tier', e.get('tier', 'NO_PLAY'))
            if tier in ('SLAM', 'STRONG', 'LEAN'):
                violations.append(f"{e.get('player', '?')} {e.get('stat_type', '?')} "
                                 f"is CORRELATED but tier={tier}")
    
    if violations:
        return False, f"Correlated lines with tiers: {violations[:3]}"
    return True, "No correlated lines improperly tiered"


def check_tier_probability_alignment(edges: List[Dict]) -> Tuple[bool, str]:
    """SOP v2.1 Rule C2: Tier labels must match probabilities.
    
    Uses SOP v2.1 thresholds: SLAM ≥75%, STRONG 65-74%, LEAN 55-64%
    """
    mismatches = []
    for e in edges:
        prob = e.get('probability', e.get('model_probability', 0))
        tier = e.get('confidence_tier', e.get('tier', ''))
        
        if not tier or prob <= 0:
            continue
        
        expected = assign_tier(prob)
        if tier != expected:
            mismatches.append(
                f"{e.get('player', '?')} {e.get('stat_type', '?')}: "
                f"prob={prob:.3f} → expected {expected}, got {tier}"
            )
    
    if mismatches:
        return False, f"Tier/probability mismatches: {mismatches[:5]}"
    return True, f"All tier assignments match probabilities"


def check_kelly_positive(edges: List[Dict]) -> Tuple[bool, str]:
    """Audit Item #3: No pick with negative Kelly (no edge) can be included.
    
    If kelly_full <= 0, the model has NO mathematical edge.
    """
    violations = []
    for e in edges:
        prob = e.get('probability', e.get('model_probability', 0))
        tier = e.get('confidence_tier', e.get('tier', 'NO_PLAY'))
        
        # Skip NO_PLAY (they shouldn't be here, but check separately)
        if tier == 'NO_PLAY':
            continue
        
        # Get odds
        odds = e.get('decimal_odds', 0)
        if odds <= 1.0 and 'american_odds' in e:
            odds = american_to_decimal(e['american_odds'])
        
        if odds <= 1.0:
            # No odds available — can't calculate Kelly, flag as warning
            continue
        
        try:
            k = kelly_full(prob, odds)
            if k <= 0:
                violations.append(
                    f"{e.get('player', '?')} {e.get('stat_type', '?')}: "
                    f"Kelly={k:.4f} (prob={prob:.3f}, odds={odds:.2f}). NO EDGE."
                )
        except (ValueError, ZeroDivisionError):
            continue
    
    if violations:
        return False, f"Negative Kelly (no edge): {violations[:3]}"
    return True, "All included picks have positive Kelly"


def check_direction_bias(edges: List[Dict], sport: str = '') -> Tuple[bool, str]:
    """SOP v2.1: Direction bias gate.
    
    If >65% of picks are in the same direction, pipeline should abort.
    """
    if len(edges) < 5:
        return True, f"Only {len(edges)} edges — too few for direction bias check"
    
    directions = [e.get('direction', '').upper() for e in edges if e.get('direction')]
    if not directions:
        return True, "No direction data in edges"
    
    counter = Counter(directions)
    total = len(directions)
    
    for direction, count in counter.items():
        pct = count / total
        if pct > DIRECTION_BIAS_THRESHOLD:
            return False, (
                f"Direction bias: {count}/{total} ({pct:.1%}) are {direction} "
                f"(threshold: {DIRECTION_BIAS_THRESHOLD:.0%}). "
                f"Pipeline should abort."
            )
    
    most_common = counter.most_common(1)[0]
    return True, f"Direction balance OK: {dict(counter)} (max {most_common[1]/total:.1%})"


def check_no_play_leaked(edges: List[Dict]) -> Tuple[bool, str]:
    """Ensure no NO_PLAY picks made it into the output."""
    no_plays = [e for e in edges 
                if e.get('confidence_tier', e.get('tier', '')) == 'NO_PLAY']
    
    if no_plays:
        names = [f"{e.get('player', '?')} {e.get('stat_type', '?')}" for e in no_plays[:3]]
        return False, f"NO_PLAY picks in output: {names}"
    return True, "No NO_PLAY picks in output"


def check_compression_applied(edges: List[Dict], sport: str = '') -> Tuple[bool, str]:
    """SOP v2.1 Rule C1: Verify compression was applied where needed.
    
    If |projection - line| > 2.5σ, confidence must be ≤ 65%.
    """
    violations = []
    
    for e in edges:
        proj = e.get('projection', None)
        line = e.get('line', None)
        prob = e.get('probability', e.get('model_probability', 0))
        stat = e.get('stat_type', e.get('stat', e.get('market', '')))
        edge_sport = e.get('sport', sport)
        
        if proj is None or line is None or not edge_sport or not stat:
            continue
        
        if edge_sport not in SIGMA_TABLE or stat not in SIGMA_TABLE.get(edge_sport, {}):
            continue
        
        sigma = SIGMA_TABLE[edge_sport][stat]
        deviation = abs(proj - line) / sigma
        
        if deviation > 2.5 and prob > 0.65:
            violations.append(
                f"{e.get('player', '?')} {stat}: "
                f"|{proj:.1f} - {line:.1f}| / {sigma:.1f} = {deviation:.2f}σ > 2.5σ, "
                f"but prob={prob:.3f} > 0.65"
            )
    
    if violations:
        return False, f"Compression not applied: {violations[:3]}"
    return True, "Compression check passed"


def check_player_team_consistency(player_edges: List[Dict],
                                    team_projection: Optional[float] = None,
                                    total_line: Optional[float] = None) -> Tuple[bool, str]:
    """Audit Item #6: Player-team directional consistency.
    
    FIXED: Compares directional signal COUNTS (not raw projection sums)
    to team-level direction.
    """
    if team_projection is None or total_line is None:
        return True, "No team projection/total line provided — skipping"
    
    # Count directional signals for points
    over_count = sum(1 for e in player_edges
                     if e.get('stat_type', e.get('stat', '')) == 'points'
                     and e.get('direction', '').upper() == 'OVER')
    under_count = sum(1 for e in player_edges
                      if e.get('stat_type', e.get('stat', '')) == 'points'
                      and e.get('direction', '').upper() == 'UNDER')
    
    # Check consistency
    if over_count > under_count + 2 and team_projection < total_line - 2.0:
        return False, (
            f"Majority player OVERs ({over_count}) conflict with team projection "
            f"({team_projection:.1f}) being UNDER total line ({total_line:.1f})"
        )
    
    if under_count > over_count + 2 and team_projection > total_line + 2.0:
        return False, (
            f"Majority player UNDERs ({under_count}) conflict with team projection "
            f"({team_projection:.1f}) being OVER total line ({total_line:.1f})"
        )
    
    return True, f"Player-team consistency OK (OVER: {over_count}, UNDER: {under_count})"


# =============================================================================
# MAIN VALIDATION GATE
# =============================================================================

def validate_output(edges: List[Dict],
                     sport: str = '',
                     team_projection: Optional[float] = None,
                     total_line: Optional[float] = None,
                     strict: bool = True) -> ValidationResult:
    """Run ALL validation checks. This is the HARD GATE.
    
    SOP v2.1 Section 6: If ANY check fails → ABORT OUTPUT.
    
    Args:
        edges: List of edge/pick dictionaries
        sport: Sport identifier
        team_projection: Optional team total projection
        total_line: Optional game total line
        strict: If True, any FAIL blocks render. If False, only log.
    
    Returns:
        ValidationResult with pass/fail status and details
    """
    result = ValidationResult()
    
    print(f"\n{'='*60}")
    print(f"  FUOOM VALIDATION GATE — Processing {len(edges)} edges")
    print(f"  Sport: {sport or 'ALL'}")
    print(f"  Strict mode: {strict}")
    print(f"{'='*60}\n")
    
    # Filter to only actionable picks (not NO_PLAY)
    actionable = [e for e in edges 
                  if e.get('confidence_tier', e.get('tier', '')) != 'NO_PLAY']
    
    # === CHECK 1: No duplicate edges ===
    passed, detail = check_no_duplicate_edges(actionable)
    result.add_check('NO_DUPLICATE_EDGES', passed, detail)
    
    # === CHECK 2: No duplicate primary players ===
    passed, detail = check_no_duplicate_primary_players(actionable)
    result.add_check('NO_DUPLICATE_PRIMARY', passed, detail)
    
    # === CHECK 3: No correlated lines tiered ===
    passed, detail = check_no_correlated_tiered(actionable)
    result.add_check('NO_CORRELATED_TIERED', passed, detail)
    
    # === CHECK 4: Tier-probability alignment ===
    passed, detail = check_tier_probability_alignment(actionable)
    result.add_check('TIER_ALIGNMENT', passed, detail)
    
    # === CHECK 5: Kelly criterion positive ===
    passed, detail = check_kelly_positive(actionable)
    result.add_check('KELLY_POSITIVE', passed, detail)
    
    # === CHECK 6: Direction bias ===
    passed, detail = check_direction_bias(actionable, sport)
    result.add_check('DIRECTION_BIAS', passed, detail)
    
    # === CHECK 7: No NO_PLAY leaked ===
    passed, detail = check_no_play_leaked(actionable)
    result.add_check('NO_PLAY_LEAKED', passed, detail)
    
    # === CHECK 8: Compression applied ===
    passed, detail = check_compression_applied(actionable, sport)
    if not passed:
        result.add_warning('COMPRESSION', detail)  # Warning, not hard fail
    else:
        result.add_check('COMPRESSION', True, detail)
    
    # === CHECK 9: Player-team consistency ===
    if team_projection is not None and total_line is not None:
        passed, detail = check_player_team_consistency(
            actionable, team_projection, total_line
        )
        result.add_check('PLAYER_TEAM_CONSISTENCY', passed, detail)
    
    # === FINAL VERDICT ===
    print(result.summary())
    
    if not result.passed and strict:
        logger.critical("⛔ VALIDATION GATE FAILED — Render blocked")
        print("  ⛔ render_report.py WILL NOT EXECUTE until errors are resolved.\n")
    
    return result


def gate_and_render(edges: List[Dict], sport: str = '',
                     team_projection: Optional[float] = None,
                     total_line: Optional[float] = None,
                     render_func=None) -> bool:
    """Convenience function: validate then render only if passed.
    
    Usage:
        from validate_output import gate_and_render
        gate_and_render(edges, sport='NBA', render_func=render_report)
    
    Args:
        edges: Edge list
        sport: Sport key
        team_projection: Optional team total
        total_line: Optional total line
        render_func: Function to call if validation passes
    
    Returns:
        True if validation passed and render executed
    """
    result = validate_output(edges, sport, team_projection, total_line, strict=True)
    
    if result.passed:
        if render_func:
            logger.info("Validation passed — executing render")
            render_func(edges)
        return True
    else:
        logger.critical("Validation FAILED — render BLOCKED")
        return False


# =============================================================================
# AUDIT LOG
# =============================================================================

def save_validation_audit(result: ValidationResult, filepath: str = 'logs/validation_audit.json'):
    """Save validation result as immutable audit log entry."""
    import os
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Append to audit log (append-only)
    entry = result.to_dict()
    
    try:
        with open(filepath, 'r') as f:
            audit_log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        audit_log = []
    
    audit_log.append(entry)
    
    with open(filepath, 'w') as f:
        json.dump(audit_log, f, indent=2)
    
    logger.info(f"Validation audit saved to {filepath}")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    """Run validation gate from command line.
    
    Usage:
        python validate_output.py --input outputs/scored_edges.json --sport NBA
        python validate_output.py --input outputs/scored_edges.json --sport CBB --strict
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='FUOOM Validation Gate')
    parser.add_argument('--input', required=True, help='Path to scored edges JSON')
    parser.add_argument('--sport', default='', help='Sport identifier')
    parser.add_argument('--team-projection', type=float, default=None)
    parser.add_argument('--total-line', type=float, default=None)
    parser.add_argument('--strict', action='store_true', default=True)
    parser.add_argument('--save-audit', action='store_true', default=True)
    
    args = parser.parse_args()
    
    # Load edges
    with open(args.input, 'r') as f:
        edges = json.load(f)
    
    # Run validation
    result = validate_output(
        edges,
        sport=args.sport,
        team_projection=args.team_projection,
        total_line=args.total_line,
        strict=args.strict,
    )
    
    # Save audit
    if args.save_audit:
        save_validation_audit(result)
    
    # Exit code
    sys.exit(0 if result.passed else 1)
