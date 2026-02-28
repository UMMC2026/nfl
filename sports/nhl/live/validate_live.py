"""
LIVE VALIDATION — NHL v2.0 Intermission Engine
===============================================

Final validation layer for live betting decisions.
Enforces the global constraint:

  assert live_bets_per_game <= 1

VALIDATION GATES:
- V1: Maximum one live bet per game
- V2: Minimum edge threshold (3% for live)
- V3: Line movement check (reject adverse movement)
- V4: Clock synchronization validation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .ingest_live import LiveGameSnapshot, IntermissionWindow
from .intermission_model import LiveAdjustment, AdjustmentType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# VALIDATION RESULT
# ─────────────────────────────────────────────────────────

@dataclass
class LiveValidationResult:
    """Result of live bet validation."""
    adjustment: LiveAdjustment
    
    # Gates
    gate_v1_single_bet: bool
    gate_v2_min_edge: bool
    gate_v3_line_movement: bool
    gate_v4_clock_sync: bool
    
    # Final verdict
    is_valid: bool
    rejection_reasons: List[str] = field(default_factory=list)
    
    # Metadata
    validated_at: datetime = field(default_factory=datetime.now)
    
    def __repr__(self):
        status = "VALID" if self.is_valid else "INVALID"
        gates = f"V1:{self.gate_v1_single_bet} V2:{self.gate_v2_min_edge} V3:{self.gate_v3_line_movement} V4:{self.gate_v4_clock_sync}"
        reasons = ", ".join(self.rejection_reasons) if self.rejection_reasons else "None"
        return (
            f"LiveValidationResult({status})\n"
            f"  Entity: {self.adjustment.entity}\n"
            f"  Type: {self.adjustment.adjustment_type.value}\n"
            f"  Gates: {gates}\n"
            f"  Rejections: {reasons}"
        )


# ─────────────────────────────────────────────────────────
# GATE V1: SINGLE BET PER GAME
# ─────────────────────────────────────────────────────────

class LiveBetTracker:
    """
    Track live bets to enforce single-bet-per-game rule.
    
    GLOBAL ASSERTION: live_bets_per_game <= 1
    """
    
    def __init__(self):
        # game_id -> set of bet types placed
        self._bets: Dict[str, Set[str]] = {}
        # game_id -> count of bets
        self._bet_counts: Dict[str, int] = {}
    
    def check_can_bet(self, game_id: str) -> Tuple[bool, str]:
        """
        Check if a live bet can be placed for this game.
        
        Returns:
            (allowed, reason)
        """
        count = self._bet_counts.get(game_id, 0)
        if count >= 1:
            return False, f"REJECTED V1: Already {count} live bet(s) for game {game_id}"
        return True, "PASSED V1: No prior live bets"
    
    def record_bet(self, game_id: str, bet_type: str):
        """Record a live bet was placed."""
        if game_id not in self._bets:
            self._bets[game_id] = set()
            self._bet_counts[game_id] = 0
        
        self._bets[game_id].add(bet_type)
        self._bet_counts[game_id] += 1
        
        logger.info(f"Live bet recorded: {game_id} / {bet_type} (total: {self._bet_counts[game_id]})")
    
    def get_bet_count(self, game_id: str) -> int:
        """Get number of live bets for a game."""
        return self._bet_counts.get(game_id, 0)
    
    def reset_game(self, game_id: str):
        """Reset tracking for a game (e.g., at game end)."""
        if game_id in self._bets:
            del self._bets[game_id]
        if game_id in self._bet_counts:
            del self._bet_counts[game_id]
    
    def get_all_stats(self) -> Dict[str, int]:
        """Get bet counts for all games."""
        return dict(self._bet_counts)


# Singleton tracker
_live_bet_tracker = LiveBetTracker()


def get_live_bet_tracker() -> LiveBetTracker:
    """Get the singleton live bet tracker."""
    return _live_bet_tracker


# ─────────────────────────────────────────────────────────
# GATE V2: MINIMUM EDGE
# ─────────────────────────────────────────────────────────

# Higher threshold for live bets due to timing uncertainty
LIVE_MIN_EDGE = 0.03  # 3% minimum edge


def validate_min_edge(adjustment: LiveAdjustment) -> Tuple[bool, str]:
    """
    Gate V2: Check minimum edge threshold for live bets.
    
    Live bets require higher edge (3%) than pregame (2%) due to:
    - Timing uncertainty
    - Line staleness
    - Execution risk
    """
    if not adjustment.is_actionable:
        return False, f"REJECTED V2: Adjustment not actionable ({adjustment.rejection_reason})"
    
    # Edge is the probability vs implied (simplified: prob > 50% means edge)
    # For more accuracy, would compare to market odds
    edge = adjustment.adjusted_probability - 0.50
    
    if edge < LIVE_MIN_EDGE:
        return False, f"REJECTED V2: Edge {edge:.1%} < {LIVE_MIN_EDGE:.1%} minimum"
    
    return True, f"PASSED V2: Edge {edge:.1%} meets threshold"


# ─────────────────────────────────────────────────────────
# GATE V3: LINE MOVEMENT
# ─────────────────────────────────────────────────────────

# Maximum adverse line movement allowed (e.g., line moved 0.5 against us)
MAX_ADVERSE_MOVEMENT = 0.5


def validate_line_movement(
    adjustment: LiveAdjustment,
    current_line: float,
) -> Tuple[bool, str]:
    """
    Gate V3: Check for adverse line movement.
    
    If line moved against our direction, reject.
    """
    original_line = adjustment.line
    direction = adjustment.direction.upper()
    
    # Calculate movement
    movement = current_line - original_line
    
    # Adverse movement check
    if direction == "OVER" and movement > 0:
        # Line went up (harder to hit OVER)
        if movement > MAX_ADVERSE_MOVEMENT:
            return False, f"REJECTED V3: Line moved up {movement:.1f} (adverse for OVER)"
    elif direction == "UNDER" and movement < 0:
        # Line went down (harder to hit UNDER)
        if abs(movement) > MAX_ADVERSE_MOVEMENT:
            return False, f"REJECTED V3: Line moved down {abs(movement):.1f} (adverse for UNDER)"
    
    return True, f"PASSED V3: Line movement {movement:+.1f} acceptable"


# ─────────────────────────────────────────────────────────
# GATE V4: CLOCK SYNCHRONIZATION
# ─────────────────────────────────────────────────────────

# Maximum acceptable data age for live decisions
MAX_DATA_AGE_SECONDS = 60  # 1 minute max staleness


def validate_clock_sync(
    snapshot: LiveGameSnapshot,
    decision_time: datetime = None,
) -> Tuple[bool, str]:
    """
    Gate V4: Validate data freshness.
    
    Reject if data is too stale for live decisions.
    """
    if decision_time is None:
        decision_time = datetime.now()
    
    # Check explicit staleness flag
    if snapshot.is_stale:
        return False, f"REJECTED V4: Data flagged as stale ({snapshot.data_age_seconds:.0f}s)"
    
    # Check data age
    data_age = (decision_time - snapshot.timestamp).total_seconds()
    
    if data_age > MAX_DATA_AGE_SECONDS:
        return False, f"REJECTED V4: Data age {data_age:.0f}s exceeds {MAX_DATA_AGE_SECONDS}s max"
    
    return True, f"PASSED V4: Data age {data_age:.0f}s within threshold"


# ─────────────────────────────────────────────────────────
# UNIFIED VALIDATION
# ─────────────────────────────────────────────────────────

def validate_live_bet(
    game_id: str,
    snapshot: LiveGameSnapshot,
    adjustment: LiveAdjustment,
    current_line: Optional[float] = None,
    record_if_valid: bool = True,
) -> LiveValidationResult:
    """
    Run full validation on a live bet opportunity.
    
    Args:
        game_id: Game identifier
        snapshot: Live game snapshot
        adjustment: The proposed adjustment
        current_line: Current market line (for movement check)
        record_if_valid: If True, record bet in tracker if valid
    
    Returns:
        LiveValidationResult with all gate outcomes
    """
    rejection_reasons = []
    
    # Gate V1: Single bet per game
    tracker = get_live_bet_tracker()
    v1_pass, v1_reason = tracker.check_can_bet(game_id)
    if not v1_pass:
        rejection_reasons.append(v1_reason)
    
    # Gate V2: Minimum edge
    v2_pass, v2_reason = validate_min_edge(adjustment)
    if not v2_pass:
        rejection_reasons.append(v2_reason)
    
    # Gate V3: Line movement
    if current_line is not None:
        v3_pass, v3_reason = validate_line_movement(adjustment, current_line)
    else:
        v3_pass = True
        v3_reason = "SKIPPED V3: No current line provided"
    if not v3_pass:
        rejection_reasons.append(v3_reason)
    
    # Gate V4: Clock sync
    v4_pass, v4_reason = validate_clock_sync(snapshot)
    if not v4_pass:
        rejection_reasons.append(v4_reason)
    
    # Final verdict
    is_valid = v1_pass and v2_pass and v3_pass and v4_pass
    
    # Record if valid and requested
    if is_valid and record_if_valid:
        tracker.record_bet(game_id, adjustment.adjustment_type.value)
    
    return LiveValidationResult(
        adjustment=adjustment,
        gate_v1_single_bet=v1_pass,
        gate_v2_min_edge=v2_pass,
        gate_v3_line_movement=v3_pass,
        gate_v4_clock_sync=v4_pass,
        is_valid=is_valid,
        rejection_reasons=rejection_reasons,
    )


def validate_all_adjustments(
    game_id: str,
    snapshot: LiveGameSnapshot,
    adjustments: List[LiveAdjustment],
    current_lines: Optional[Dict[str, float]] = None,
) -> List[LiveValidationResult]:
    """
    Validate all adjustments, enforcing single-bet-per-game.
    
    Args:
        game_id: Game identifier
        snapshot: Live game snapshot
        adjustments: List of proposed adjustments
        current_lines: Dict mapping entity names to current lines
    
    Returns:
        List of LiveValidationResult (only first valid bet per game allowed)
    """
    results = []
    
    for adj in adjustments:
        current_line = None
        if current_lines:
            current_line = current_lines.get(adj.entity)
        
        result = validate_live_bet(
            game_id=game_id,
            snapshot=snapshot,
            adjustment=adj,
            current_line=current_line,
            record_if_valid=True,  # Will only record first valid one
        )
        results.append(result)
    
    return results


# ─────────────────────────────────────────────────────────
# ASSERTIONS
# ─────────────────────────────────────────────────────────

def assert_global_constraints():
    """
    Assert all global constraints are satisfied.
    
    GLOBAL ASSERTION: live_bets_per_game <= 1
    
    Raises AssertionError if violated.
    """
    tracker = get_live_bet_tracker()
    stats = tracker.get_all_stats()
    
    for game_id, count in stats.items():
        if count > 1:
            raise AssertionError(
                f"GLOBAL CONSTRAINT VIOLATED: "
                f"live_bets_per_game > 1 for game {game_id} (count={count})"
            )
    
    logger.info("assert_global_constraints: PASSED (live_bets_per_game <= 1)")


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from .ingest_live import GameState
    from .intermission_model import GameTotalModel
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("LIVE VALIDATION — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Mock snapshot
    snapshot = LiveGameSnapshot(
        game_id="2024020815",
        home_team="BOS",
        away_team="DET",
        home_score=3,
        away_score=2,
        period=2,
        period_time_remaining="00:00",
        game_state=GameState.INTERMISSION_2,
        intermission_window=IntermissionWindow.SECOND,
        intermission_time_remaining=1000,
        home_shots=25,
        away_shots=18,
        home_pp_time=120,
        away_pp_time=60,
        home_pims=4,
        away_pims=6,
    )
    
    # Create adjustment
    adjustment = GameTotalModel.adjust(
        snapshot=snapshot,
        original_projection=6.2,
        original_probability=0.58,  # Good edge
        line=6.5,
        direction="OVER",
    )
    
    print(f"\nAdjustment to validate:")
    print(adjustment)
    
    # Validate (first attempt - should pass)
    print("\n" + "-" * 40)
    print("First validation attempt:")
    
    result1 = validate_live_bet(
        game_id="2024020815",
        snapshot=snapshot,
        adjustment=adjustment,
        current_line=6.5,
    )
    print(result1)
    
    # Validate (second attempt - should fail V1)
    print("\n" + "-" * 40)
    print("Second validation attempt (same game):")
    
    result2 = validate_live_bet(
        game_id="2024020815",
        snapshot=snapshot,
        adjustment=adjustment,
        current_line=6.5,
    )
    print(result2)
    
    # Assert global constraints
    print("\n" + "-" * 40)
    print("Global constraint check:")
    
    try:
        assert_global_constraints()
        print("  PASSED: All constraints satisfied")
    except AssertionError as e:
        print(f"  FAILED: {e}")
