"""
FUOOM DARK MATTER - Output Validation Gate
============================================
HARD GATE: This module MUST pass before any picks reach subscribers.

If ANY check fails: RAISE ERROR, ABORT OUTPUT.
No silent failures. No partial reports.

Version: 1.0.0
Date: February 9, 2026
"""

import json
import sys
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Import math utilities
try:
    from shared.math_utils import (
        Tier,
        probability_to_tier,
        validate_tier_probability_alignment,
        calculate_kelly,
        validate_kelly_edge,
        american_to_decimal,
        compression_check,
    )
except ImportError:
    # Fallback for standalone execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from shared.math_utils import (
        Tier,
        probability_to_tier,
        validate_tier_probability_alignment,
        calculate_kelly,
        validate_kelly_edge,
        american_to_decimal,
        compression_check,
    )


# =============================================================================
# VALIDATION RESULT STRUCTURES
# =============================================================================

@dataclass
class ValidationError:
    """Single validation error."""
    error_type: str
    signal_id: str
    message: str
    severity: str = "CRITICAL"  # CRITICAL, WARNING
    
    def __str__(self):
        return f"[{self.severity}] {self.error_type}: {self.signal_id} - {self.message}"


@dataclass
class ValidationResult:
    """Complete validation result for a batch."""
    passed: bool
    total_signals: int
    valid_signals: int
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __str__(self):
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Validation {status}: {self.valid_signals}/{self.total_signals} valid, "
            f"{len(self.errors)} errors, {len(self.warnings)} warnings"
        )


# =============================================================================
# CORE VALIDATION GATES
# =============================================================================

def validate_tier_alignment(signal: Dict) -> Optional[ValidationError]:
    """
    Gate 1: Tier label must match probability.
    
    SOP Rule C2: Tier-probability mismatch is a violation.
    """
    probability = signal.get('probability', 0)
    tier = signal.get('confidence_tier', signal.get('tier', ''))
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    
    is_valid, message = validate_tier_probability_alignment(tier, probability)
    
    if not is_valid:
        return ValidationError(
            error_type="TIER_PROBABILITY_MISMATCH",
            signal_id=signal_id,
            message=message,
            severity="CRITICAL"
        )
    
    return None


def validate_kelly_edge(signal: Dict) -> Optional[ValidationError]:
    """
    Gate 2: Negative Kelly = NO EDGE = MUST EXCLUDE.
    
    This is the most critical gate. No mathematical edge means no bet.
    """
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    probability = signal.get('probability', 0)
    
    # Get decimal odds
    decimal_odds = signal.get('decimal_odds')
    if not decimal_odds:
        american_odds = signal.get('american_odds', signal.get('odds'))
        if american_odds:
            decimal_odds = american_to_decimal(american_odds)
        else:
            # Assume -110 standard vig if no odds provided
            decimal_odds = 1.909
    
    # Calculate Kelly
    kelly_result = calculate_kelly(probability, decimal_odds)
    
    if not kelly_result.has_edge:
        return ValidationError(
            error_type="NEGATIVE_KELLY",
            signal_id=signal_id,
            message=f"No mathematical edge. Kelly = {kelly_result.kelly_full:.4f}. MUST EXCLUDE.",
            severity="CRITICAL"
        )
    
    return None


def validate_no_duplicate_edges(signals: List[Dict]) -> List[ValidationError]:
    """
    Gate 3: No duplicate edges allowed.
    
    EDGE = unique(player, game_id, stat, direction)
    Multiple lines for same edge = violation.
    """
    errors = []
    seen_edges: Dict[str, str] = {}  # edge_key -> first signal_id
    
    for signal in signals:
        # Build edge key
        player = signal.get('player', signal.get('player_name', ''))
        game_id = signal.get('game_id', signal.get('game', ''))
        stat = signal.get('market', signal.get('stat', signal.get('prop_type', '')))
        direction = signal.get('direction', '')
        
        edge_key = f"{player}|{game_id}|{stat}|{direction}".lower()
        signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
        
        if edge_key in seen_edges:
            errors.append(ValidationError(
                error_type="DUPLICATE_EDGE",
                signal_id=signal_id,
                message=f"Duplicate edge with {seen_edges[edge_key]}. Edge: {edge_key}",
                severity="CRITICAL"
            ))
        else:
            seen_edges[edge_key] = signal_id
    
    return errors


def validate_no_player_double_primary(signals: List[Dict]) -> List[ValidationError]:
    """
    Gate 4: No player appears twice as PRIMARY bet.
    
    SOP Rule B1: Max 1 PRIMARY bet per player per game (unless ALLOW_CORRELATED).
    """
    errors = []
    player_game_primary: Dict[str, str] = {}  # "player|game" -> first signal_id
    
    for signal in signals:
        # Skip non-primary bets
        if signal.get('is_correlated', False):
            continue
        if signal.get('risk_tag') == 'CORRELATED':
            continue
        
        player = signal.get('player', signal.get('player_name', ''))
        game_id = signal.get('game_id', signal.get('game', ''))
        signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
        
        key = f"{player}|{game_id}".lower()
        
        if key in player_game_primary:
            # Check if ALLOW_CORRELATED is set
            if not signal.get('allow_correlated', False):
                errors.append(ValidationError(
                    error_type="PLAYER_DOUBLE_PRIMARY",
                    signal_id=signal_id,
                    message=f"Player already has PRIMARY bet: {player_game_primary[key]}",
                    severity="CRITICAL"
                ))
        else:
            player_game_primary[key] = signal_id
    
    return errors


def validate_no_correlated_tiered(signals: List[Dict]) -> List[ValidationError]:
    """
    Gate 5: Correlated alternatives cannot be tiered.
    
    Correlated bets must be excluded from tier assignments.
    """
    errors = []
    
    for signal in signals:
        is_correlated = (
            signal.get('is_correlated', False) or
            signal.get('risk_tag') == 'CORRELATED' or
            signal.get('is_alternative', False)
        )
        
        if not is_correlated:
            continue
        
        tier = signal.get('confidence_tier', signal.get('tier', ''))
        signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
        
        if tier and tier.upper() not in ['', 'NONE', 'CORRELATED', 'ALTERNATIVE']:
            errors.append(ValidationError(
                error_type="CORRELATED_TIERED",
                signal_id=signal_id,
                message=f"Correlated alternative has tier '{tier}'. Must be excluded from tiers.",
                severity="CRITICAL"
            ))
    
    return errors


def validate_minimum_confidence(signal: Dict) -> Optional[ValidationError]:
    """
    Gate 6: Confidence must meet minimum threshold.
    
    < 55% = NO_PLAY, should not appear in output.
    """
    probability = signal.get('probability', 0)
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    tier = signal.get('confidence_tier', signal.get('tier', ''))
    
    if probability < 0.55 and tier.upper() not in ['NO_PLAY', 'NO PLAY', 'REJECTED', '']:
        return ValidationError(
            error_type="BELOW_MINIMUM_CONFIDENCE",
            signal_id=signal_id,
            message=f"Probability {probability:.1%} < 55% minimum. Must be NO_PLAY or excluded.",
            severity="CRITICAL"
        )
    
    return None


def validate_compression_applied(signal: Dict) -> Optional[ValidationError]:
    """
    Gate 7: Check if compression rule was applied for extreme deviations.
    
    SOP Rule C1: If |projection - line| > 2.5σ, confidence ≤ 65%.
    """
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    probability = signal.get('probability', 0)
    projection = signal.get('projection', signal.get('model_projection'))
    line = signal.get('line')
    sport = signal.get('sport', 'NBA')
    stat = signal.get('market', signal.get('stat', signal.get('prop_type', '')))
    
    # Can't check without projection/line
    if projection is None or line is None:
        return None
    
    try:
        compressed = compression_check(projection, line, sport, stat, probability)
        
        if compressed < probability:
            return ValidationError(
                error_type="COMPRESSION_NOT_APPLIED",
                signal_id=signal_id,
                message=(
                    f"Extreme deviation detected but confidence not compressed. "
                    f"Should be ≤{compressed:.1%}, got {probability:.1%}"
                ),
                severity="WARNING"
            )
    except ValueError:
        # Unknown sport/stat combination - can't validate
        pass
    
    return None


def validate_required_fields(signal: Dict) -> List[ValidationError]:
    """
    Gate 8: All required fields must be present.
    """
    errors = []
    signal_id = signal.get('signal_id', signal.get('id', 'UNKNOWN'))
    
    required_fields = [
        ('player', ['player', 'player_name']),
        ('probability', ['probability', 'prob', 'confidence']),
        ('direction', ['direction', 'pick_direction']),
        ('line', ['line', 'prop_line', 'market_line']),
    ]
    
    for field_name, possible_keys in required_fields:
        found = any(signal.get(key) is not None for key in possible_keys)
        if not found:
            errors.append(ValidationError(
                error_type="MISSING_FIELD",
                signal_id=signal_id,
                message=f"Missing required field: {field_name}",
                severity="CRITICAL"
            ))
    
    return errors


# =============================================================================
# PLAYER-TEAM CONSISTENCY CHECK (Fixed per Audit)
# =============================================================================

def validate_player_team_consistency(
    player_signals: List[Dict],
    team_projection: Optional[float],
    total_line: Optional[float],
    team_direction: Optional[str]
) -> List[ValidationError]:
    """
    Gate 9: Player-level picks must be consistent with team-level direction.
    
    FIXED per audit: Compare directional signal counts, not raw projection sums.
    """
    errors = []
    
    if team_projection is None or total_line is None or team_direction is None:
        return errors  # Can't validate without team data
    
    # Count directional signals for points
    over_count = sum(
        1 for s in player_signals
        if s.get('market', s.get('stat', '')).lower() in ['points', 'pts']
        and s.get('direction', '').lower() in ['over', 'higher']
    )
    
    under_count = sum(
        1 for s in player_signals
        if s.get('market', s.get('stat', '')).lower() in ['points', 'pts']
        and s.get('direction', '').lower() in ['under', 'lower']
    )
    
    # If majority of player picks are OVER but team total is UNDER
    if over_count > under_count + 2 and team_direction.lower() in ['under', 'lower']:
        errors.append(ValidationError(
            error_type="PLAYER_TEAM_INCONSISTENCY",
            signal_id="TEAM_CHECK",
            message=(
                f"Majority player OVERs ({over_count}) conflict with team UNDER. "
                f"UNDERs: {under_count}"
            ),
            severity="WARNING"
        ))
    
    # If team projection exceeds total line but direction is UNDER
    if team_projection > total_line + 2.0 and team_direction.lower() in ['under', 'lower']:
        errors.append(ValidationError(
            error_type="PROJECTION_DIRECTION_CONFLICT",
            signal_id="TEAM_CHECK",
            message=(
                f"Projection {team_projection:.1f} > line {total_line:.1f} + 2, "
                f"but direction is {team_direction}"
            ),
            severity="WARNING"
        ))
    
    return errors


# =============================================================================
# MASTER VALIDATION FUNCTION
# =============================================================================

def validate_output(
    signals: List[Dict],
    team_data: Optional[Dict] = None,
    strict_mode: bool = True
) -> ValidationResult:
    """
    Master validation gate for all signals.
    
    HARD GATE: If any CRITICAL error exists, validation fails.
    
    Args:
        signals: List of signal dictionaries
        team_data: Optional team-level data for consistency checks
        strict_mode: If True, any error fails. If False, only critical errors fail.
        
    Returns:
        ValidationResult with pass/fail status and all errors
    """
    all_errors: List[ValidationError] = []
    all_warnings: List[ValidationError] = []
    valid_count = 0
    
    # Batch validations (across all signals)
    duplicate_errors = validate_no_duplicate_edges(signals)
    all_errors.extend([e for e in duplicate_errors if e.severity == "CRITICAL"])
    all_warnings.extend([e for e in duplicate_errors if e.severity == "WARNING"])
    
    double_primary_errors = validate_no_player_double_primary(signals)
    all_errors.extend([e for e in double_primary_errors if e.severity == "CRITICAL"])
    all_warnings.extend([e for e in double_primary_errors if e.severity == "WARNING"])
    
    correlated_errors = validate_no_correlated_tiered(signals)
    all_errors.extend([e for e in correlated_errors if e.severity == "CRITICAL"])
    all_warnings.extend([e for e in correlated_errors if e.severity == "WARNING"])
    
    # Per-signal validations
    for signal in signals:
        signal_valid = True
        
        # Required fields
        field_errors = validate_required_fields(signal)
        if field_errors:
            all_errors.extend(field_errors)
            signal_valid = False
            continue  # Skip other checks if missing required fields
        
        # Tier alignment
        tier_error = validate_tier_alignment(signal)
        if tier_error:
            if tier_error.severity == "CRITICAL":
                all_errors.append(tier_error)
                signal_valid = False
            else:
                all_warnings.append(tier_error)
        
        # Kelly edge
        kelly_error = validate_kelly_edge(signal)
        if kelly_error:
            all_errors.append(kelly_error)
            signal_valid = False
        
        # Minimum confidence
        conf_error = validate_minimum_confidence(signal)
        if conf_error:
            all_errors.append(conf_error)
            signal_valid = False
        
        # Compression (warning only)
        comp_error = validate_compression_applied(signal)
        if comp_error:
            all_warnings.append(comp_error)
        
        if signal_valid:
            valid_count += 1
    
    # Team consistency (if team data provided)
    if team_data:
        team_errors = validate_player_team_consistency(
            player_signals=signals,
            team_projection=team_data.get('projection'),
            total_line=team_data.get('total_line'),
            team_direction=team_data.get('direction')
        )
        all_warnings.extend(team_errors)
    
    # Determine pass/fail
    if strict_mode:
        passed = len(all_errors) == 0
    else:
        # In non-strict mode, only critical errors fail
        passed = not any(e.severity == "CRITICAL" for e in all_errors)
    
    return ValidationResult(
        passed=passed,
        total_signals=len(signals),
        valid_signals=valid_count,
        errors=all_errors,
        warnings=all_warnings
    )


# =============================================================================
# CLI INTERFACE
# =============================================================================

def validate_file(filepath: str, strict: bool = True) -> ValidationResult:
    """
    Validate a JSON file of signals.
    
    Args:
        filepath: Path to JSON file
        strict: Strict mode flag
        
    Returns:
        ValidationResult
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, list):
        signals = data
    elif isinstance(data, dict):
        signals = data.get('picks', data.get('signals', data.get('edges', [])))
    else:
        raise ValueError(f"Unexpected data format in {filepath}")
    
    return validate_output(signals, strict_mode=strict)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="FUOOM Validation Gate - Blocks bad picks before output"
    )
    parser.add_argument('file', help='JSON file to validate')
    parser.add_argument('--lenient', action='store_true', 
                        help='Only fail on critical errors')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    
    args = parser.parse_args()
    
    try:
        result = validate_file(args.file, strict=not args.lenient)
    except Exception as e:
        print(f"ERROR: Failed to validate file: {e}", file=sys.stderr)
        sys.exit(2)
    
    if args.json:
        output = {
            'passed': result.passed,
            'total_signals': result.total_signals,
            'valid_signals': result.valid_signals,
            'errors': [str(e) for e in result.errors],
            'warnings': [str(w) for w in result.warnings],
            'timestamp': result.timestamp
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"FUOOM VALIDATION GATE")
        print(f"{'='*60}")
        print(f"File: {args.file}")
        print(f"Timestamp: {result.timestamp}")
        print(f"{'='*60}")
        print(f"\nResult: {result}")
        
        if result.errors:
            print(f"\n{'─'*60}")
            print("CRITICAL ERRORS (must fix):")
            print(f"{'─'*60}")
            for error in result.errors:
                print(f"  ✗ {error}")
        
        if result.warnings:
            print(f"\n{'─'*60}")
            print("WARNINGS (should fix):")
            print(f"{'─'*60}")
            for warning in result.warnings:
                print(f"  ⚠ {warning}")
        
        print(f"\n{'='*60}")
        if result.passed:
            print("✓ VALIDATION PASSED - Output may proceed")
        else:
            print("✗ VALIDATION FAILED - Output blocked")
        print(f"{'='*60}\n")
    
    # Exit with appropriate code
    sys.exit(0 if result.passed else 1)


if __name__ == '__main__':
    main()
