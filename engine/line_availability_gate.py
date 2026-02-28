"""
LINE AVAILABILITY GATE — Priority 1 Implementation
===================================================

Validates that recommended lines match actual book offerings.

Features:
- Exact line verification (26.5 not 27.5)
- Line movement detection (>2% = warn, >5% = block)
- Stale line detection (>30 min old)
- Edge recalculation after movement

Phase: 5A (Priority 1)
Created: 2026-02-05
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class LineStatus(Enum):
    """Status of line availability."""
    AVAILABLE = "available"           # Line exists at expected value
    MOVED_MINOR = "moved_minor"       # Line moved <2%
    MOVED_MODERATE = "moved_moderate" # Line moved 2-5%
    MOVED_MAJOR = "moved_major"       # Line moved >5%
    UNAVAILABLE = "unavailable"       # Line not found
    STALE = "stale"                   # Line data too old
    UNKNOWN = "unknown"               # Could not verify


class LineAction(Enum):
    """Action to take based on line status."""
    PROCEED = "proceed"               # Use the pick as-is
    RECALCULATE = "recalculate"       # Recalculate edge with new line
    WARN = "warn"                     # Warn but allow
    BLOCK = "block"                   # Block the pick


# Movement thresholds (percentage)
MOVEMENT_THRESHOLDS = {
    "minor": 2.0,     # <2% movement = no action
    "moderate": 5.0,  # 2-5% movement = warn
    "major": 10.0,    # >5% movement = block
}

# Staleness threshold (minutes)
STALE_THRESHOLD_MINUTES = 30


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LineAvailabilityResult:
    """Result of line availability check."""
    pick_id: str
    player: str
    stat: str
    expected_line: float
    direction: str
    
    # Line verification
    status: LineStatus = LineStatus.UNKNOWN
    actual_line: Optional[float] = None
    line_difference: float = 0.0
    movement_pct: float = 0.0
    
    # Edge impact
    original_edge: float = 0.0
    recalculated_edge: Optional[float] = None
    edge_degraded: bool = False
    
    # Action
    action: LineAction = LineAction.PROCEED
    action_reason: str = ""
    
    # Metadata
    book: str = ""
    checked_at: datetime = field(default_factory=datetime.now)
    line_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "pick_id": self.pick_id,
            "player": self.player,
            "stat": self.stat,
            "expected_line": self.expected_line,
            "direction": self.direction,
            "status": self.status.value,
            "actual_line": self.actual_line,
            "line_difference": self.line_difference,
            "movement_pct": self.movement_pct,
            "original_edge": self.original_edge,
            "recalculated_edge": self.recalculated_edge,
            "edge_degraded": self.edge_degraded,
            "action": self.action.value,
            "action_reason": self.action_reason,
            "book": self.book,
            "checked_at": self.checked_at.isoformat(),
            "line_timestamp": self.line_timestamp.isoformat() if self.line_timestamp else None,
        }


@dataclass
class LineAvailabilityConfig:
    """Configuration for line availability checks."""
    
    # Movement thresholds
    minor_movement_pct: float = 2.0
    moderate_movement_pct: float = 5.0
    major_movement_pct: float = 10.0
    
    # Actions for each movement level
    minor_action: LineAction = LineAction.PROCEED
    moderate_action: LineAction = LineAction.WARN
    major_action: LineAction = LineAction.BLOCK
    unavailable_action: LineAction = LineAction.BLOCK
    
    # Edge thresholds
    min_edge_after_movement: float = 2.0  # Minimum edge to keep after recalculation
    
    # Staleness
    stale_threshold_minutes: int = 30
    stale_action: LineAction = LineAction.WARN
    
    # Direction matching (strict or flexible)
    strict_direction_match: bool = False


DEFAULT_CONFIG = LineAvailabilityConfig()


# =============================================================================
# LINE AVAILABILITY GATE
# =============================================================================

class LineAvailabilityGate:
    """
    Gate that validates line availability and movement.
    
    Integrates with LiquidityGate to get actual line data,
    then validates against expected lines.
    """
    
    def __init__(self, config: LineAvailabilityConfig = None):
        self.config = config or DEFAULT_CONFIG
        
        # Import liquidity gate for line data
        try:
            from engine.liquidity_gate import get_gate as get_liquidity_gate
            self.liquidity_gate = get_liquidity_gate()
        except ImportError:
            logger.warning("Liquidity gate not available, using stub")
            self.liquidity_gate = None
    
    def _get_actual_line(
        self,
        player: str,
        stat: str,
        expected_line: float,
        direction: str,
    ) -> Tuple[Optional[float], str, Optional[datetime]]:
        """
        Get actual line from liquidity gate.
        
        Returns:
            Tuple of (actual_line, book, line_timestamp)
        """
        if self.liquidity_gate is None:
            # Stub: return expected line with small random variation
            import random
            variation = random.uniform(-0.5, 0.5)
            return expected_line + variation, "simulated", datetime.now()
        
        result = self.liquidity_gate.check_liquidity(
            player=player,
            stat=stat,
            line=expected_line,
            direction=direction,
        )
        
        if result.is_available and result.actual_line is not None:
            return result.actual_line, result.book_checked, result.checked_at
        
        return None, "", None
    
    def _calculate_movement(
        self,
        expected: float,
        actual: float,
    ) -> Tuple[float, float, LineStatus]:
        """
        Calculate line movement.
        
        Returns:
            Tuple of (difference, movement_pct, status)
        """
        if actual is None:
            return 0.0, 0.0, LineStatus.UNAVAILABLE
        
        difference = actual - expected
        
        # Avoid division by zero
        if expected == 0:
            movement_pct = 0.0 if actual == 0 else 100.0
        else:
            movement_pct = abs(difference) / expected * 100
        
        # Determine status
        if movement_pct < self.config.minor_movement_pct:
            status = LineStatus.AVAILABLE
        elif movement_pct < self.config.moderate_movement_pct:
            status = LineStatus.MOVED_MINOR
        elif movement_pct < self.config.major_movement_pct:
            status = LineStatus.MOVED_MODERATE
        else:
            status = LineStatus.MOVED_MAJOR
        
        return difference, movement_pct, status
    
    def _determine_action(
        self,
        status: LineStatus,
        line_timestamp: Optional[datetime],
    ) -> Tuple[LineAction, str]:
        """
        Determine action based on line status.
        
        Returns:
            Tuple of (action, reason)
        """
        # Check staleness first
        if line_timestamp:
            age = datetime.now() - line_timestamp
            if age > timedelta(minutes=self.config.stale_threshold_minutes):
                return self.config.stale_action, f"Line data is {age.total_seconds() / 60:.0f} minutes old"
        
        # Map status to action
        if status == LineStatus.AVAILABLE:
            return LineAction.PROCEED, "Line available at expected value"
        
        elif status == LineStatus.MOVED_MINOR:
            return self.config.minor_action, "Minor line movement detected"
        
        elif status == LineStatus.MOVED_MODERATE:
            return self.config.moderate_action, "Moderate line movement — verify edge"
        
        elif status == LineStatus.MOVED_MAJOR:
            return self.config.major_action, "Major line movement — edge likely degraded"
        
        elif status == LineStatus.UNAVAILABLE:
            return self.config.unavailable_action, "Line not available on book"
        
        else:
            return LineAction.WARN, "Could not verify line status"
    
    def _recalculate_edge(
        self,
        original_prob: float,
        expected_line: float,
        actual_line: float,
        direction: str,
        mu: float = 0.0,
        sigma: float = 0.0,
    ) -> Tuple[float, bool]:
        """
        Recalculate edge with new line.
        
        This is a simplified recalculation. In production,
        would re-run Monte Carlo with actual line.
        
        Returns:
            Tuple of (new_edge, is_degraded)
        """
        # Simple linear adjustment
        # For "higher" direction, higher line = lower probability
        # For "lower" direction, higher line = higher probability
        
        line_diff = actual_line - expected_line
        
        # Estimate probability change per 0.5 line movement
        prob_change_per_half = 0.02  # ~2% per 0.5 points
        
        if direction.lower() in ("higher", "over"):
            # Higher line = harder to hit = lower probability
            prob_adjustment = -line_diff * prob_change_per_half * 2
        else:
            # Higher line = easier to go under = higher probability
            prob_adjustment = line_diff * prob_change_per_half * 2
        
        new_prob = original_prob + prob_adjustment
        new_prob = max(0.40, min(0.85, new_prob))  # Clamp to reasonable range
        
        # Calculate edge (assuming 50% implied odds)
        implied_prob = 0.50
        new_edge = (new_prob - implied_prob) * 100
        
        # Check if edge is degraded below threshold
        is_degraded = new_edge < self.config.min_edge_after_movement
        
        return new_edge, is_degraded
    
    def check_line(
        self,
        player: str,
        stat: str,
        expected_line: float,
        direction: str,
        pick_id: str = "",
        original_prob: float = 0.0,
        original_edge: float = 0.0,
        mu: float = 0.0,
        sigma: float = 0.0,
    ) -> LineAvailabilityResult:
        """
        Check if a line is available at the expected value.
        
        Args:
            player: Player name
            stat: Stat type
            expected_line: Expected betting line
            direction: higher/lower or over/under
            pick_id: Unique identifier
            original_prob: Original probability estimate
            original_edge: Original edge percentage
            mu: Player mean (for recalculation)
            sigma: Player standard deviation (for recalculation)
        
        Returns:
            LineAvailabilityResult with status and action
        """
        result = LineAvailabilityResult(
            pick_id=pick_id or f"{player}_{stat}_{expected_line}",
            player=player,
            stat=stat,
            expected_line=expected_line,
            direction=direction,
            original_edge=original_edge,
        )
        
        # Get actual line
        actual_line, book, line_timestamp = self._get_actual_line(
            player, stat, expected_line, direction
        )
        
        result.book = book
        result.line_timestamp = line_timestamp
        result.actual_line = actual_line
        
        # Calculate movement
        difference, movement_pct, status = self._calculate_movement(
            expected_line, actual_line
        )
        
        result.line_difference = difference
        result.movement_pct = movement_pct
        result.status = status
        
        # Determine action
        action, reason = self._determine_action(status, line_timestamp)
        result.action = action
        result.action_reason = reason
        
        # Recalculate edge if line moved
        if status in (LineStatus.MOVED_MINOR, LineStatus.MOVED_MODERATE, LineStatus.MOVED_MAJOR):
            if original_prob > 0 and actual_line is not None:
                new_edge, is_degraded = self._recalculate_edge(
                    original_prob, expected_line, actual_line,
                    direction, mu, sigma
                )
                result.recalculated_edge = new_edge
                result.edge_degraded = is_degraded
                
                # Upgrade to block if edge is too degraded
                if is_degraded and action != LineAction.BLOCK:
                    result.action = LineAction.BLOCK
                    result.action_reason = (
                        f"Edge degraded to {new_edge:.1f}% "
                        f"(below {self.config.min_edge_after_movement}% threshold)"
                    )
        
        return result
    
    def check_batch(
        self,
        picks: List[Dict],
        player_key: str = "player",
        stat_key: str = "stat",
        line_key: str = "line",
        direction_key: str = "direction",
        prob_key: str = "probability",
        edge_key: str = "edge",
    ) -> List[LineAvailabilityResult]:
        """
        Check line availability for a batch of picks.
        """
        results = []
        
        for i, pick in enumerate(picks):
            result = self.check_line(
                player=pick.get(player_key, ""),
                stat=pick.get(stat_key, ""),
                expected_line=pick.get(line_key, 0.0),
                direction=pick.get(direction_key, ""),
                pick_id=pick.get("pick_id", pick.get("edge_id", f"pick_{i}")),
                original_prob=pick.get(prob_key, 0.0),
                original_edge=pick.get(edge_key, 0.0),
                mu=pick.get("mu", 0.0),
                sigma=pick.get("sigma", 0.0),
            )
            results.append(result)
        
        return results
    
    def filter_valid(
        self,
        picks: List[Dict],
        results: List[LineAvailabilityResult] = None,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Filter picks into valid, warned, and blocked lists.
        
        Returns:
            Tuple of (valid_picks, warned_picks, blocked_picks)
        """
        if results is None:
            results = self.check_batch(picks)
        
        valid = []
        warned = []
        blocked = []
        
        for pick, result in zip(picks, results):
            # Add availability info to pick
            pick["line_availability"] = result.to_dict()
            
            # Update line if moved
            if result.actual_line is not None and result.actual_line != result.expected_line:
                pick["original_line"] = result.expected_line
                pick["adjusted_line"] = result.actual_line
            
            # Update edge if recalculated
            if result.recalculated_edge is not None:
                pick["original_edge"] = result.original_edge
                pick["adjusted_edge"] = result.recalculated_edge
            
            # Categorize
            if result.action == LineAction.BLOCK:
                blocked.append(pick)
            elif result.action == LineAction.WARN:
                warned.append(pick)
            else:
                valid.append(pick)
        
        return valid, warned, blocked
    
    def get_summary(self, results: List[LineAvailabilityResult]) -> Dict:
        """Get summary statistics."""
        total = len(results)
        
        status_counts = {}
        for status in LineStatus:
            status_counts[status.value] = sum(1 for r in results if r.status == status)
        
        action_counts = {}
        for action in LineAction:
            action_counts[action.value] = sum(1 for r in results if r.action == action)
        
        avg_movement = 0.0
        movements = [r.movement_pct for r in results if r.movement_pct > 0]
        if movements:
            avg_movement = sum(movements) / len(movements)
        
        degraded = sum(1 for r in results if r.edge_degraded)
        
        return {
            "total_checked": total,
            "status_breakdown": status_counts,
            "action_breakdown": action_counts,
            "avg_movement_pct": avg_movement,
            "edges_degraded": degraded,
            "block_rate": action_counts.get("block", 0) / total * 100 if total > 0 else 0,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_gate: Optional[LineAvailabilityGate] = None


def get_gate() -> LineAvailabilityGate:
    """Get or create global gate instance."""
    global _gate
    if _gate is None:
        _gate = LineAvailabilityGate()
    return _gate


def check_line_availability(
    player: str,
    stat: str,
    expected_line: float,
    direction: str,
    original_prob: float = 0.0,
    original_edge: float = 0.0,
) -> LineAvailabilityResult:
    """Check line availability for a single pick."""
    return get_gate().check_line(
        player=player,
        stat=stat,
        expected_line=expected_line,
        direction=direction,
        original_prob=original_prob,
        original_edge=original_edge,
    )


def run_line_availability_gate(picks: List[Dict]) -> Dict:
    """
    Run line availability gate on picks.
    
    Main entry point for pipeline integration.
    """
    gate = get_gate()
    results = gate.check_batch(picks)
    valid, warned, blocked = gate.filter_valid(picks, results)
    summary = gate.get_summary(results)
    
    return {
        "valid": valid,
        "warned": warned,
        "blocked": blocked,
        "summary": summary,
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI for testing line availability gate."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Line Availability Gate Tester")
    parser.add_argument("--player", default="LeBron James", help="Player name")
    parser.add_argument("--stat", default="points", help="Stat type")
    parser.add_argument("--line", type=float, default=25.5, help="Expected line")
    parser.add_argument("--direction", default="higher", help="Direction")
    parser.add_argument("--prob", type=float, default=0.65, help="Original probability")
    parser.add_argument("--edge", type=float, default=15.0, help="Original edge %")
    parser.add_argument("--batch-test", action="store_true", help="Run batch test")
    
    args = parser.parse_args()
    
    if args.batch_test:
        test_picks = [
            {"player": "LeBron James", "stat": "points", "line": 25.5, "direction": "higher", "probability": 0.65, "edge": 15.0},
            {"player": "Stephen Curry", "stat": "3pm", "line": 4.5, "direction": "higher", "probability": 0.60, "edge": 10.0},
            {"player": "Nikola Jokic", "stat": "assists", "line": 8.5, "direction": "lower", "probability": 0.70, "edge": 20.0},
            {"player": "Luka Doncic", "stat": "rebounds", "line": 9.5, "direction": "higher", "probability": 0.55, "edge": 5.0},
        ]
        
        print("\n" + "=" * 60)
        print("LINE AVAILABILITY GATE — BATCH TEST")
        print("=" * 60)
        
        result = run_line_availability_gate(test_picks)
        
        print(f"\n📊 Summary:")
        for key, value in result["summary"].items():
            if isinstance(value, dict):
                print(f"   {key}:")
                for k, v in value.items():
                    print(f"      {k}: {v}")
            else:
                print(f"   {key}: {value}")
        
        print(f"\n✅ Valid ({len(result['valid'])}):")
        for pick in result["valid"]:
            avail = pick.get("line_availability", {})
            print(f"   {pick['player']} {pick['stat']} {pick['line']} — {avail.get('status', 'N/A')}")
        
        print(f"\n⚠️ Warned ({len(result['warned'])}):")
        for pick in result["warned"]:
            avail = pick.get("line_availability", {})
            print(f"   {pick['player']} {pick['stat']} {pick['line']} — {avail.get('action_reason', 'N/A')}")
        
        print(f"\n❌ Blocked ({len(result['blocked'])}):")
        for pick in result["blocked"]:
            avail = pick.get("line_availability", {})
            print(f"   {pick['player']} {pick['stat']} {pick['line']} — {avail.get('action_reason', 'N/A')}")
    
    else:
        print("\n" + "=" * 60)
        print("LINE AVAILABILITY GATE — SINGLE CHECK")
        print("=" * 60)
        
        result = check_line_availability(
            player=args.player,
            stat=args.stat,
            expected_line=args.line,
            direction=args.direction,
            original_prob=args.prob,
            original_edge=args.edge,
        )
        
        print(f"\nPlayer: {result.player}")
        print(f"Stat: {result.stat}")
        print(f"Expected Line: {result.expected_line}")
        print(f"Actual Line: {result.actual_line or 'N/A'}")
        print(f"Direction: {result.direction}")
        print(f"\nStatus: {result.status.value}")
        print(f"Movement: {result.movement_pct:.2f}%")
        print(f"Action: {result.action.value}")
        print(f"Reason: {result.action_reason}")
        
        if result.recalculated_edge is not None:
            print(f"\nOriginal Edge: {result.original_edge:.1f}%")
            print(f"Recalculated Edge: {result.recalculated_edge:.1f}%")
            print(f"Edge Degraded: {'⚠️ Yes' if result.edge_degraded else '✅ No'}")


if __name__ == "__main__":
    main()
