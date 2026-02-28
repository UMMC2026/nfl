"""
FUOOM DARK MATTER - Minutes & Role Access Gate
================================================
Pre-model access control that determines if a prop is physically possible.

This is GATE 1 in the pre-model pipeline.
It answers: "Can this player hit this stat given their opportunity?"

Version: 1.0.0
Date: February 10, 2026
"""

from dataclasses import dataclass
from typing import Tuple, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

class PlayerRole(Enum):
    STAR = "STAR"
    STARTER = "STARTER"
    BENCH = "BENCH"
    FRINGE = "FRINGE"


# Volume stats that require substantial minutes
VOLUME_STATS = {
    "PTS", "POINTS", "SCORING",
    "PRA", "PTS+REB+AST", "POINTS+REBOUNDS+ASSISTS",
    "PTS+REB", "POINTS+REBOUNDS", "PR",
    "PTS+AST", "POINTS+ASSISTS", "PA",
    "FANTASY", "FPTS",
}

# Minimum minutes by stat category
MIN_MINUTES = {
    "volume": 22,
    "rebounds": 18,
    "assists": 20,
    "threes": 15,
    "stocks": 12,  # steals + blocks
    "default": 15,
}

# PPM thresholds for trap detection
PPM_THRESHOLDS = {
    "points_over": 0.40,
    "points_under": 0.20,  # Very low PPM, under might not hit either
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RoleConstraints:
    """Constraints based on player role."""
    slam_eligible: bool
    max_tier: str
    variance_flag: str
    blowout_vulnerable: bool
    parlay_eligible: bool


@dataclass
class MinutesRoleResult:
    """Result from the minutes & role access gate."""
    allowed: bool
    reason: str
    role: str
    expected_minutes: float
    constraints: dict
    checks_performed: List[str]
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "role": self.role,
            "expected_minutes": self.expected_minutes,
            "constraints": self.constraints,
            "checks_performed": self.checks_performed,
        }


# =============================================================================
# ROLE CLASSIFICATION
# =============================================================================

def classify_role(minutes: float) -> PlayerRole:
    """
    Classify player role strictly by minutes.
    
    This is deterministic and based on NBA rotation patterns:
    - Stars: 32+ minutes (primary options)
    - Starters: 26-32 minutes (secondary contributors)
    - Bench: 18-26 minutes (rotation players)
    - Fringe: <18 minutes (garbage time / situational)
    """
    if minutes >= 32:
        return PlayerRole.STAR
    elif minutes >= 26:
        return PlayerRole.STARTER
    elif minutes >= 18:
        return PlayerRole.BENCH
    else:
        return PlayerRole.FRINGE


def get_role_constraints(role: PlayerRole) -> RoleConstraints:
    """
    Get constraints based on player role.
    These propagate downstream to cap confidence and restrict tiers.
    """
    constraints_map = {
        PlayerRole.STAR: RoleConstraints(
            slam_eligible=True,
            max_tier="SLAM",
            variance_flag="LOW",
            blowout_vulnerable=True,   # Stars sit in blowouts
            parlay_eligible=True,
        ),
        PlayerRole.STARTER: RoleConstraints(
            slam_eligible=True,
            max_tier="SLAM",
            variance_flag="NORMAL",
            blowout_vulnerable=True,
            parlay_eligible=True,
        ),
        PlayerRole.BENCH: RoleConstraints(
            slam_eligible=False,
            max_tier="STRONG",
            variance_flag="HIGH",
            blowout_vulnerable=False,  # Bench plays MORE in blowouts
            parlay_eligible=False,     # Too volatile for parlays
        ),
        PlayerRole.FRINGE: RoleConstraints(
            slam_eligible=False,
            max_tier="LEAN",
            variance_flag="EXTREME",
            blowout_vulnerable=False,
            parlay_eligible=False,
        ),
    }
    return constraints_map[role]


# =============================================================================
# ACCESS CHECKS
# =============================================================================

def get_stat_category(stat_type: str) -> str:
    """Categorize stat for minimum minutes lookup."""
    stat_upper = stat_type.upper().replace(" ", "").replace("+", "_")
    
    if stat_upper in VOLUME_STATS or "PTS" in stat_upper or "POINTS" in stat_upper:
        return "volume"
    elif "REB" in stat_upper:
        return "rebounds"
    elif "AST" in stat_upper:
        return "assists"
    elif "3" in stat_upper or "THREE" in stat_upper:
        return "threes"
    elif "STL" in stat_upper or "BLK" in stat_upper or "STOCK" in stat_upper:
        return "stocks"
    else:
        return "default"


def check_minutes_access(
    expected_minutes: float,
    stat_type: str,
    direction: str
) -> Tuple[bool, str]:
    """
    Check if minutes support this prop direction.
    
    Args:
        expected_minutes: Projected or recent average minutes
        stat_type: Type of stat (PTS, REB, AST, etc.)
        direction: OVER or UNDER
        
    Returns:
        Tuple of (allowed, reason)
    """
    category = get_stat_category(stat_type)
    min_required = MIN_MINUTES.get(category, MIN_MINUTES["default"])
    
    # Volume stat OVER with insufficient minutes
    if category == "volume":
        if expected_minutes < min_required:
            if direction.upper() in ["OVER", "HIGHER"]:
                return False, (
                    f"Volume stat OVER requires ≥{min_required} min, "
                    f"player has {expected_minutes:.1f} min"
                )
    
    # Non-volume stats have lower thresholds
    elif expected_minutes < min_required:
        if direction.upper() in ["OVER", "HIGHER"]:
            return False, (
                f"{category.upper()} OVER typically requires ≥{min_required} min, "
                f"player has {expected_minutes:.1f} min"
            )
    
    return True, "Minutes sufficient"


def check_role_access(
    role: PlayerRole,
    stat_type: str,
    direction: str
) -> Tuple[bool, str]:
    """
    Check if role supports this prop.
    
    FRINGE players are blocked from volume stats entirely.
    BENCH players get warnings but aren't blocked.
    """
    category = get_stat_category(stat_type)
    
    if role == PlayerRole.FRINGE:
        if category == "volume":
            return False, (
                f"FRINGE role blocked from volume stats - "
                f"minutes too fragile for reliable projection"
            )
    
    return True, "Role access granted"


def check_ppm_viability(
    ppm: float,
    stat_type: str,
    direction: str
) -> Tuple[bool, str]:
    """
    Check if scoring rate supports the direction.
    
    Low PPM + OVER = trap (inefficient scorer can't hit high lines)
    Very low PPM + UNDER = also risky (might not score at all)
    """
    category = get_stat_category(stat_type)
    
    if category == "volume" or "PTS" in stat_type.upper():
        if direction.upper() in ["OVER", "HIGHER"]:
            if ppm < PPM_THRESHOLDS["points_over"]:
                return False, (
                    f"PPM {ppm:.3f} < {PPM_THRESHOLDS['points_over']} - "
                    f"OVER is a trap for inefficient scorers"
                )
    
    return True, "PPM viability passed"


def check_minutes_viability(
    expected_minutes: float,
    stat_type: str,
    line: float,
    rate_per_minute: float
) -> Tuple[bool, str]:
    """
    Check if projected minutes can physically support the line.
    
    This answers: "How many minutes does this player need to hit the line?"
    """
    if rate_per_minute <= 0:
        return False, "Cannot calculate viability with zero rate"
    
    minutes_needed = line / rate_per_minute
    
    if minutes_needed > 48:
        return False, (
            f"Would need {minutes_needed:.0f} min to hit line {line} "
            f"at rate {rate_per_minute:.3f}/min (impossible)"
        )
    
    if minutes_needed > expected_minutes * 1.4:
        return False, (
            f"Would need {minutes_needed:.0f} min, "
            f"but only {expected_minutes:.0f} projected (40% gap)"
        )
    
    return True, f"Viability OK: needs {minutes_needed:.0f} min, has {expected_minutes:.0f}"


# =============================================================================
# MAIN GATE CLASS
# =============================================================================

class MinutesRoleGate:
    """
    Pre-model gate that checks opportunity-based access.
    
    This gate answers: "Is this prop physically possible?"
    
    It does NOT:
    - Adjust projections
    - Modify probabilities
    - Apply calibration
    
    It ONLY:
    - Blocks impossible props
    - Tags constraints for downstream
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.min_minutes_override = self.config.get("min_minutes", {})
    
    def check(
        self,
        expected_minutes: float,
        stat_type: str,
        direction: str,
        ppm: Optional[float] = None,
        line: Optional[float] = None,
        rate_per_minute: Optional[float] = None,
    ) -> MinutesRoleResult:
        """
        Run all access checks.
        
        Returns MinutesRoleResult with allowed/blocked status and constraints.
        """
        checks_performed = []
        
        # Classify role
        role = classify_role(expected_minutes)
        constraints = get_role_constraints(role)
        
        # Check 1: Minutes access
        allowed, reason = check_minutes_access(
            expected_minutes, stat_type, direction
        )
        checks_performed.append(f"Minutes: {reason}")
        
        if not allowed:
            self._log_block(expected_minutes, stat_type, direction, role, reason)
            return MinutesRoleResult(
                allowed=False,
                reason=reason,
                role=role.value,
                expected_minutes=expected_minutes,
                constraints={},
                checks_performed=checks_performed,
            )
        
        # Check 2: Role access
        allowed, reason = check_role_access(role, stat_type, direction)
        checks_performed.append(f"Role: {reason}")
        
        if not allowed:
            self._log_block(expected_minutes, stat_type, direction, role, reason)
            return MinutesRoleResult(
                allowed=False,
                reason=reason,
                role=role.value,
                expected_minutes=expected_minutes,
                constraints={},
                checks_performed=checks_performed,
            )
        
        # Check 3: PPM viability (if provided)
        if ppm is not None:
            allowed, reason = check_ppm_viability(ppm, stat_type, direction)
            checks_performed.append(f"PPM: {reason}")
            
            if not allowed:
                self._log_block(expected_minutes, stat_type, direction, role, reason)
                return MinutesRoleResult(
                    allowed=False,
                    reason=reason,
                    role=role.value,
                    expected_minutes=expected_minutes,
                    constraints={},
                    checks_performed=checks_performed,
                )
        
        # Check 4: Line viability (if provided)
        if line is not None and rate_per_minute is not None:
            allowed, reason = check_minutes_viability(
                expected_minutes, stat_type, line, rate_per_minute
            )
            checks_performed.append(f"Viability: {reason}")
            
            if not allowed:
                self._log_block(expected_minutes, stat_type, direction, role, reason)
                return MinutesRoleResult(
                    allowed=False,
                    reason=reason,
                    role=role.value,
                    expected_minutes=expected_minutes,
                    constraints={},
                    checks_performed=checks_performed,
                )
        
        # All checks passed
        return MinutesRoleResult(
            allowed=True,
            reason="ALL CHECKS PASSED",
            role=role.value,
            expected_minutes=expected_minutes,
            constraints={
                "slam_eligible": constraints.slam_eligible,
                "max_tier": constraints.max_tier,
                "variance_flag": constraints.variance_flag,
                "blowout_vulnerable": constraints.blowout_vulnerable,
                "parlay_eligible": constraints.parlay_eligible,
            },
            checks_performed=checks_performed,
        )
    
    def _log_block(
        self,
        minutes: float,
        stat_type: str,
        direction: str,
        role: PlayerRole,
        reason: str
    ):
        """Log blocked props for audit trail."""
        logger.info(
            f"[BLOCKED][MINUTES_ROLE_GATE] "
            f"Stat: {stat_type} {direction.upper()} | "
            f"Minutes: {minutes:.1f} | "
            f"Role: {role.value} | "
            f"Reason: {reason}"
        )


# =============================================================================
# CLI / DEMO
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    gate = MinutesRoleGate()
    
    print("=" * 70)
    print("MINUTES & ROLE ACCESS GATE - DEMO")
    print("=" * 70)
    
    # Test cases
    tests = [
        # Should PASS
        {"expected_minutes": 35.0, "stat_type": "PTS", "direction": "OVER", 
         "ppm": 0.75, "desc": "Star player, high PPM"},
        
        # Should BLOCK (low minutes for volume stat)
        {"expected_minutes": 18.0, "stat_type": "PTS", "direction": "OVER",
         "ppm": 0.55, "desc": "Bench player, volume OVER"},
        
        # Should BLOCK (fringe role)
        {"expected_minutes": 12.0, "stat_type": "PRA", "direction": "OVER",
         "desc": "Fringe player, PRA"},
        
        # Should BLOCK (low PPM)
        {"expected_minutes": 28.0, "stat_type": "PTS", "direction": "OVER",
         "ppm": 0.35, "desc": "Starter, low PPM trap"},
        
        # Should PASS (UNDER doesn't need high minutes)
        {"expected_minutes": 18.0, "stat_type": "PTS", "direction": "UNDER",
         "desc": "Bench player, UNDER"},
        
        # Should PASS (rebounds have lower threshold)
        {"expected_minutes": 20.0, "stat_type": "REB", "direction": "OVER",
         "desc": "Bench player, rebounds"},
    ]
    
    for i, test in enumerate(tests, 1):
        desc = test.pop("desc")
        result = gate.check(**test)
        
        status = "✓ PASS" if result.allowed else "✗ BLOCK"
        print(f"\nTest {i}: {desc}")
        print(f"  Input: {test}")
        print(f"  Result: {status}")
        print(f"  Reason: {result.reason}")
        print(f"  Role: {result.role}")
        if result.constraints:
            print(f"  Constraints: {result.constraints}")
