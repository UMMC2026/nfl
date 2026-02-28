"""
FUOOM DARK MATTER - Direction Gate
====================================
Pre-model gate that validates directional thesis exists.

This is GATE 2 in the pre-model pipeline.
It answers: "Does a real directional path exist for this prop?"

Core Principle:
  Direction is decided BEFORE probability.
  If direction is weak, probability cannot fix it.

Version: 1.0.0
Date: February 10, 2026
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Obstacle penalties by type (percentage reduction)
OBSTACLE_PENALTIES = {
    "elite_defender": 0.08,
    "elite_defense_team": 0.06,
    "blowout_risk": 0.05,
    "back_to_back": 0.04,
    "usage_competition": 0.04,
    "foul_risk": 0.03,
    "pace_mismatch": 0.03,
    "minutes_uncertainty": 0.05,
    "injury_concern": 0.06,
    "rest_management": 0.04,
    "matchup_history": 0.03,
}

# Minimum z-score to have an edge
MIN_Z_SCORE = 0.50

# Hit rate thresholds for consistency check
HIT_RATE_THRESHOLDS = {
    "over_min": 0.40,   # If picking OVER, need at least 40% historical hit
    "under_max": 0.60,  # If picking UNDER, historical hit should be < 60%
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DirectionGateResult:
    """Result from the direction gate."""
    allowed: bool
    reason: str
    direction: str
    z_score: float
    raw_direction: str
    obstacle_penalty: float
    obstacles_applied: List[str]
    checks_performed: List[str]
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "direction": self.direction,
            "z_score": self.z_score,
            "raw_direction": self.raw_direction,
            "obstacle_penalty": self.obstacle_penalty,
            "obstacles_applied": self.obstacles_applied,
            "checks_performed": self.checks_performed,
        }


# =============================================================================
# DIRECTION VALIDATION
# =============================================================================

def calculate_z_score(mu: float, sigma: float, line: float) -> float:
    """Calculate z-score: how many σ is the line from μ."""
    if sigma <= 0:
        return 0.0
    return (line - mu) / sigma


def get_raw_direction(mu: float, line: float) -> str:
    """Determine which direction raw math favors."""
    if mu > line:
        return "OVER"
    elif mu < line:
        return "UNDER"
    else:
        return "NEUTRAL"


def check_direction_alignment(
    mu: float,
    line: float,
    direction: str
) -> Tuple[bool, str]:
    """
    Check if chosen direction aligns with raw math.
    
    This is the most critical check:
    - If μ > line, OVER is correct
    - If μ < line, UNDER is correct
    - Picking against the math is BLOCKED
    """
    raw_direction = get_raw_direction(mu, line)
    chosen = direction.upper()
    
    # Neutral case (μ ≈ line)
    if raw_direction == "NEUTRAL":
        return False, f"No edge: μ={mu:.2f} equals line={line:.2f}"
    
    # Normalize direction names
    if chosen in ["OVER", "HIGHER", "MORE"]:
        chosen = "OVER"
    elif chosen in ["UNDER", "LOWER", "LESS"]:
        chosen = "UNDER"
    
    # Check alignment
    if chosen != raw_direction:
        return False, (
            f"DIRECTION MISMATCH: μ={mu:.2f} vs line={line:.2f} "
            f"favors {raw_direction}, but {direction.upper()} was selected"
        )
    
    return True, f"Direction aligned: {chosen} (μ={mu:.2f} vs line={line:.2f})"


def check_edge_exists(z_score: float) -> Tuple[bool, str]:
    """
    Check if there's a meaningful edge (not a coin flip).
    
    |z| < 0.50 means the line is too close to μ for a real edge.
    """
    if abs(z_score) < MIN_Z_SCORE:
        return False, (
            f"NO EDGE: |z|={abs(z_score):.2f} < {MIN_Z_SCORE} "
            f"(coin flip zone, no reliable direction)"
        )
    
    strength = "strong" if abs(z_score) >= 1.0 else "moderate"
    return True, f"Edge exists: z={z_score:+.2f} ({strength})"


def check_hit_rate_consistency(
    direction: str,
    hit_rate: float
) -> Tuple[bool, str]:
    """
    Check if historical hit rate supports the direction.
    
    This catches cases where the system picks against history.
    """
    chosen = direction.upper()
    
    if chosen in ["OVER", "HIGHER"]:
        if hit_rate < HIT_RATE_THRESHOLDS["over_min"]:
            return False, (
                f"HIT RATE CONFLICT: {chosen} selected but only "
                f"{hit_rate:.0%} historical hit rate (< {HIT_RATE_THRESHOLDS['over_min']:.0%})"
            )
    elif chosen in ["UNDER", "LOWER"]:
        if hit_rate > HIT_RATE_THRESHOLDS["under_max"]:
            return False, (
                f"HIT RATE CONFLICT: {chosen} selected but "
                f"{hit_rate:.0%} hits OVER historically (> {HIT_RATE_THRESHOLDS['under_max']:.0%})"
            )
    
    return True, f"Hit rate consistent: {hit_rate:.0%}"


# =============================================================================
# OBSTACLE ANALYSIS
# =============================================================================

def calculate_obstacle_penalty(
    obstacles: List[str],
    direction: str,
    role: str
) -> Tuple[float, List[str]]:
    """
    Calculate cumulative obstacle penalty for the chosen direction.
    
    Some obstacles affect OVER differently than UNDER.
    Stars and bench players react differently to blowouts.
    """
    total_penalty = 0.0
    applied = []
    dir_upper = direction.upper()
    
    for obs in obstacles:
        obs_lower = obs.lower().replace(" ", "_").replace("-", "_")
        base_penalty = OBSTACLE_PENALTIES.get(obs_lower, 0.02)
        
        # Direction-specific adjustments
        if obs_lower == "blowout_risk":
            if role == "STAR":
                if dir_upper in ["OVER", "HIGHER"]:
                    # Stars sit in blowouts, OVER is vulnerable
                    base_penalty *= 1.5
                else:
                    # Stars sitting helps UNDER
                    base_penalty *= 0.5
            elif role in ["BENCH", "FRINGE"]:
                if dir_upper in ["OVER", "HIGHER"]:
                    # Bench plays more in blowouts, OVER is protected
                    base_penalty *= 0.3
                else:
                    # UNDER is vulnerable for bench in blowouts
                    base_penalty *= 1.3
        
        if obs_lower == "back_to_back":
            if dir_upper in ["OVER", "HIGHER"]:
                # B2B hurts OVER more
                base_penalty *= 1.2
            else:
                # B2B slightly helps UNDER
                base_penalty *= 0.8
        
        total_penalty += base_penalty
        applied.append(f"{obs}: -{base_penalty:.1%}")
    
    # Cap total penalty at 35%
    total_penalty = min(total_penalty, 0.35)
    
    return total_penalty, applied


def analyze_obstacles(
    obstacles: List[str],
    direction: str,
    role: str
) -> Tuple[bool, float, List[str], str]:
    """
    Analyze obstacles and determine if they kill the thesis.
    
    Returns (allowed, penalty, obstacles_applied, reason)
    """
    if not obstacles:
        return True, 0.0, [], "No obstacles identified"
    
    penalty, applied = calculate_obstacle_penalty(obstacles, direction, role)
    
    # If penalty is too high, block the pick
    if penalty >= 0.25:
        return False, penalty, applied, (
            f"Obstacle penalty {penalty:.0%} is too high - "
            f"thesis is not viable"
        )
    
    return True, penalty, applied, f"Obstacles analyzed: {penalty:.0%} penalty"


# =============================================================================
# MAIN GATE CLASS
# =============================================================================

class DirectionGate:
    """
    Pre-model gate that validates directional thesis.
    
    This gate answers: "Does a real directional path exist?"
    
    It does NOT:
    - Calculate probabilities
    - Adjust projections
    - Apply calibration
    
    It ONLY:
    - Validates direction alignment
    - Checks for meaningful edge
    - Stress-tests against obstacles
    - Blocks invalid theses
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.min_z = self.config.get("min_z_score", MIN_Z_SCORE)
    
    def validate(
        self,
        mu: float,
        sigma: float,
        line: float,
        direction: str,
        obstacles: List[str] = None,
        role: str = "STARTER",
        hit_rate: Optional[float] = None,
    ) -> DirectionGateResult:
        """
        Validate that a real directional thesis exists.
        
        Args:
            mu: Recent average (projection)
            sigma: Standard deviation
            line: Market line
            direction: Chosen direction (OVER/UNDER)
            obstacles: List of obstacle identifiers
            role: Player role (STAR/STARTER/BENCH/FRINGE)
            hit_rate: Historical hit rate (optional)
            
        Returns:
            DirectionGateResult with allowed/blocked status
        """
        checks_performed = []
        obstacles = obstacles or []
        
        # Calculate z-score
        z_score = calculate_z_score(mu, sigma, line)
        raw_direction = get_raw_direction(mu, line)
        
        # Check 1: Direction alignment
        allowed, reason = check_direction_alignment(mu, line, direction)
        checks_performed.append(f"Alignment: {reason}")
        
        if not allowed:
            self._log_block(mu, sigma, line, direction, z_score, reason)
            return DirectionGateResult(
                allowed=False,
                reason=reason,
                direction=direction,
                z_score=z_score,
                raw_direction=raw_direction,
                obstacle_penalty=0.0,
                obstacles_applied=[],
                checks_performed=checks_performed,
            )
        
        # Check 2: Edge exists
        allowed, reason = check_edge_exists(z_score)
        checks_performed.append(f"Edge: {reason}")
        
        if not allowed:
            self._log_block(mu, sigma, line, direction, z_score, reason)
            return DirectionGateResult(
                allowed=False,
                reason=reason,
                direction=direction,
                z_score=z_score,
                raw_direction=raw_direction,
                obstacle_penalty=0.0,
                obstacles_applied=[],
                checks_performed=checks_performed,
            )
        
        # Check 3: Hit rate consistency (if provided)
        if hit_rate is not None:
            allowed, reason = check_hit_rate_consistency(direction, hit_rate)
            checks_performed.append(f"Hit rate: {reason}")
            
            if not allowed:
                self._log_block(mu, sigma, line, direction, z_score, reason)
                return DirectionGateResult(
                    allowed=False,
                    reason=reason,
                    direction=direction,
                    z_score=z_score,
                    raw_direction=raw_direction,
                    obstacle_penalty=0.0,
                    obstacles_applied=[],
                    checks_performed=checks_performed,
                )
        
        # Check 4: Obstacle stress test
        allowed, penalty, applied, reason = analyze_obstacles(
            obstacles, direction, role
        )
        checks_performed.append(f"Obstacles: {reason}")
        
        if not allowed:
            self._log_block(mu, sigma, line, direction, z_score, reason)
            return DirectionGateResult(
                allowed=False,
                reason=reason,
                direction=direction,
                z_score=z_score,
                raw_direction=raw_direction,
                obstacle_penalty=penalty,
                obstacles_applied=applied,
                checks_performed=checks_performed,
            )
        
        # All checks passed
        return DirectionGateResult(
            allowed=True,
            reason="DIRECTIONAL THESIS VALIDATED",
            direction=direction.upper(),
            z_score=z_score,
            raw_direction=raw_direction,
            obstacle_penalty=penalty,
            obstacles_applied=applied,
            checks_performed=checks_performed,
        )
    
    def _log_block(
        self,
        mu: float,
        sigma: float,
        line: float,
        direction: str,
        z_score: float,
        reason: str
    ):
        """Log blocked props for audit trail."""
        logger.info(
            f"[BLOCKED][DIRECTION_GATE] "
            f"Direction: {direction.upper()} | "
            f"μ={mu:.2f}, σ={sigma:.2f}, line={line:.2f} | "
            f"z={z_score:+.2f} | "
            f"Reason: {reason}"
        )


# =============================================================================
# CLI / DEMO
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    gate = DirectionGate()
    
    print("=" * 70)
    print("DIRECTION GATE - DEMO")
    print("=" * 70)
    
    # Test cases
    tests = [
        # Should PASS - clear OVER edge
        {"mu": 18.5, "sigma": 4.0, "line": 15.5, "direction": "OVER",
         "desc": "Clear OVER edge (μ > line)"},
        
        # Should BLOCK - wrong direction
        {"mu": 1.6, "sigma": 1.7, "line": 1.5, "direction": "UNDER",
         "desc": "Wrong direction (μ=1.6 > line=1.5 but UNDER selected)"},
        
        # Should BLOCK - coin flip (z too small)
        {"mu": 10.0, "sigma": 5.0, "line": 9.8, "direction": "OVER",
         "desc": "Coin flip (z ≈ 0.04)"},
        
        # Should PASS - strong UNDER edge
        {"mu": 8.5, "sigma": 3.0, "line": 12.5, "direction": "UNDER",
         "desc": "Strong UNDER edge"},
        
        # Should BLOCK - obstacles too heavy
        {"mu": 20.0, "sigma": 5.0, "line": 16.0, "direction": "OVER",
         "obstacles": ["elite_defender", "blowout_risk", "back_to_back", "injury_concern"],
         "role": "STAR", "desc": "Too many obstacles"},
        
        # Should PASS - moderate obstacles
        {"mu": 20.0, "sigma": 5.0, "line": 16.0, "direction": "OVER",
         "obstacles": ["back_to_back"], "role": "STARTER",
         "desc": "Manageable obstacles"},
    ]
    
    for i, test in enumerate(tests, 1):
        desc = test.pop("desc")
        result = gate.validate(**test)
        
        status = "✓ PASS" if result.allowed else "✗ BLOCK"
        print(f"\nTest {i}: {desc}")
        print(f"  Result: {status}")
        print(f"  z-score: {result.z_score:+.2f}")
        print(f"  Raw direction: {result.raw_direction}")
        print(f"  Reason: {result.reason}")
        if result.obstacles_applied:
            print(f"  Obstacles: {result.obstacles_applied}")
