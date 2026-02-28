"""
FUOOM DARK MATTER - Pre-Model Pipeline Orchestrator
====================================================
Orchestrates all pre-model gates in sequence.

Pipeline Order (Direction First):
    1. Direction Gate       → Does a real directional path exist?
    2. Minutes & Role Gate  → Can this player realistically hit this stat?
    3. Variance Kill Switch → Is variance existential or cosmetic?

"Direction First" philosophy:
    - If direction is wrong, nothing else matters
    - Wrong direction = no edge = immediate kill
    - Minutes/Role and Variance only matter *after* a valid thesis exists

First failure stops the pipeline. Survivors get probability modeling.

Version: 1.0.1
Date: February 10, 2026
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging

from gates.minutes_role_gate import MinutesRoleGate, MinutesRoleResult
from gates.direction_gate import DirectionGate, DirectionGateResult
from gates.variance_kill_switch import VarianceKillSwitch, VarianceResult

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PreModelResult:
    """Complete result from the pre-model pipeline."""
    
    # Overall result
    allowed: bool
    blocked_by: Optional[str]
    reason: str
    
    # Role information
    role: str
    expected_minutes: float
    
    # Direction information
    direction: str
    z_score: float
    obstacle_penalty: float
    obstacles_applied: List[str]
    
    # Variance information
    variance_level: str
    cv: float
    
    # Constraints (propagate downstream)
    constraints: Dict[str, Any]
    
    # Audit trail
    gates_passed: List[str]
    all_checks: List[str]
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "blocked_by": self.blocked_by,
            "reason": self.reason,
            "role": self.role,
            "expected_minutes": self.expected_minutes,
            "direction": self.direction,
            "z_score": self.z_score,
            "obstacle_penalty": self.obstacle_penalty,
            "obstacles_applied": self.obstacles_applied,
            "variance_level": self.variance_level,
            "cv": self.cv,
            "constraints": self.constraints,
            "gates_passed": self.gates_passed,
            "all_checks": self.all_checks,
        }
    
    def summary(self) -> str:
        """One-line summary for logging."""
        if self.allowed:
            return (
                f"[ALLOWED] Role={self.role}, z={self.z_score:+.2f}, "
                f"CV={self.cv:.1%}, Obstacles={self.obstacle_penalty:.0%}"
            )
        else:
            return f"[BLOCKED by {self.blocked_by}] {self.reason}"


# =============================================================================
# PIPELINE ORCHESTRATOR
# =============================================================================

class PreModelPipeline:
    """
    Orchestrates all pre-model gates in sequence.
    
    This is the ENTRY POINT for the judgment layer.
    
    Usage:
        pipeline = PreModelPipeline()
        result = pipeline.run(
            player_id="lebron_james",
            stat_type="PTS",
            line=25.5,
            direction="OVER",
            expected_minutes=35.0,
            mu=28.3,
            sigma=6.2,
            sample_size=10,
            ...
        )
        
        if result.allowed:
            # Proceed to probability modeling
            pass
        else:
            # Skip this prop
            log_block(result)
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Initialize gates
        self.gate1 = MinutesRoleGate(self.config.get("minutes_role", {}))
        self.gate2 = DirectionGate(self.config.get("direction", {}))
        self.gate3 = VarianceKillSwitch(self.config.get("variance", {}))
    
    def run(
        self,
        player_id: str,
        stat_type: str,
        line: float,
        direction: str,
        expected_minutes: float,
        mu: float,
        sigma: float,
        sample_size: int,
        obstacles: List[str] = None,
        ppm: float = None,
        hit_rate: float = None,
        rate_per_minute: float = None,
    ) -> PreModelResult:
        """
        Run all pre-model gates in sequence.
        First failure stops the pipeline.
        
        Args:
            player_id: Player identifier
            stat_type: Type of stat (PTS, REB, AST, etc.)
            line: Market line
            direction: OVER or UNDER
            expected_minutes: Projected minutes
            mu: Recent average (projection)
            sigma: Standard deviation
            sample_size: Number of games in sample
            obstacles: List of obstacle identifiers
            ppm: Points per minute (optional)
            hit_rate: Historical hit rate (optional)
            rate_per_minute: Stat rate per minute (optional)
            
        Returns:
            PreModelResult with allowed/blocked status and all context
        """
        obstacles = obstacles or []
        gates_passed = []
        all_checks = []
        
        # =====================================================================
        # GATE 1: DIRECTION VALIDATION (DIRECTION FIRST!)
        # =====================================================================
        # Direction is checked FIRST because:
        # - If direction is wrong, nothing else matters
        # - Wrong direction = no edge = immediate kill
        # - This is the "Direction First" philosophy
        # =====================================================================
        logger.debug(f"[GATE 1] Running Direction Gate for {player_id} (DIRECTION FIRST)")
        
        # We need role for obstacle analysis, so do a quick classification
        from gates.minutes_role_gate import classify_role
        preliminary_role = classify_role(expected_minutes).value
        
        result_dir = self.gate2.validate(
            mu=mu,
            sigma=sigma,
            line=line,
            direction=direction,
            obstacles=obstacles,
            role=preliminary_role,
            hit_rate=hit_rate,
        )
        
        all_checks.extend(result_dir.checks_performed)
        
        if not result_dir.allowed:
            self._log_pipeline_block("DIRECTION_GATE", player_id, stat_type,
                                      direction, result_dir.reason)
            return PreModelResult(
                allowed=False,
                blocked_by="DIRECTION_GATE",
                reason=result_dir.reason,
                role=preliminary_role,
                expected_minutes=expected_minutes,
                direction=direction,
                z_score=result_dir.z_score,
                obstacle_penalty=0.0,
                obstacles_applied=[],
                variance_level="UNKNOWN",
                cv=0.0,
                constraints={},
                gates_passed=gates_passed,
                all_checks=all_checks,
            )
        
        gates_passed.append("DIRECTION_GATE")
        z_score = result_dir.z_score
        obstacle_penalty = result_dir.obstacle_penalty
        obstacles_applied = result_dir.obstacles_applied
        
        # =====================================================================
        # GATE 2: Minutes & Role Access
        # =====================================================================
        logger.debug(f"[GATE 2] Running Minutes & Role Gate for {player_id}")
        
        result_min = self.gate1.check(
            expected_minutes=expected_minutes,
            stat_type=stat_type,
            direction=direction,
            ppm=ppm,
            line=line,
            rate_per_minute=rate_per_minute,
        )
        
        all_checks.extend(result_min.checks_performed)
        
        if not result_min.allowed:
            self._log_pipeline_block("MINUTES_ROLE_GATE", player_id, stat_type, 
                                      direction, result_min.reason)
            return PreModelResult(
                allowed=False,
                blocked_by="MINUTES_ROLE_GATE",
                reason=result_min.reason,
                role=result_min.role,
                expected_minutes=expected_minutes,
                direction=direction,
                z_score=z_score,
                obstacle_penalty=obstacle_penalty,
                obstacles_applied=obstacles_applied,
                variance_level="UNKNOWN",
                cv=0.0,
                constraints={},
                gates_passed=gates_passed,
                all_checks=all_checks,
            )
        
        gates_passed.append("MINUTES_ROLE_GATE")
        role = result_min.role
        constraints = result_min.constraints.copy()
        
        # =====================================================================
        # GATE 3: Variance Kill Switch
        # =====================================================================
        logger.debug(f"[GATE 3] Running Variance Kill Switch for {player_id}")
        
        result_var = self.gate3.check(
            mu=mu,
            sigma=sigma,
            stat_type=stat_type,
            sample_size=sample_size,
            direction=direction,
        )
        
        all_checks.extend(result_var.checks_performed)
        
        if not result_var.allowed:
            self._log_pipeline_block("VARIANCE_KILL_SWITCH", player_id, stat_type,
                                      direction, result_var.reason)
            return PreModelResult(
                allowed=False,
                blocked_by="VARIANCE_KILL_SWITCH",
                reason=result_var.reason,
                role=role,
                expected_minutes=expected_minutes,
                direction=direction,
                z_score=z_score,
                obstacle_penalty=obstacle_penalty,
                obstacles_applied=obstacles_applied,
                variance_level=result_var.variance_level,
                cv=result_var.cv,
                constraints=constraints,
                gates_passed=gates_passed,
                all_checks=all_checks,
            )
        
        gates_passed.append("VARIANCE_KILL_SWITCH")
        variance_level = result_var.variance_level
        cv = result_var.cv
        
        # =====================================================================
        # Apply variance-based tier caps
        # =====================================================================
        if result_var.action == "CAP_STRONG":
            constraints["max_tier"] = "STRONG"
            constraints["slam_eligible"] = False
        elif result_var.action == "CAP_SLAM":
            # Only restrict if current max is higher than SLAM
            if constraints.get("max_tier") not in ["LEAN", "STRONG"]:
                constraints["max_tier"] = "SLAM"
        
        # Add variance flag to constraints
        constraints["variance_level"] = variance_level
        constraints["cv"] = cv
        constraints["obstacle_penalty"] = obstacle_penalty
        
        # =====================================================================
        # ALL GATES PASSED
        # =====================================================================
        self._log_pipeline_pass(player_id, stat_type, direction, role,
                                 z_score, cv, obstacle_penalty)
        
        return PreModelResult(
            allowed=True,
            blocked_by=None,
            reason="ALL GATES PASSED - proceed to probability modeling",
            role=role,
            expected_minutes=expected_minutes,
            direction=direction.upper(),
            z_score=z_score,
            obstacle_penalty=obstacle_penalty,
            obstacles_applied=obstacles_applied,
            variance_level=variance_level,
            cv=cv,
            constraints=constraints,
            gates_passed=gates_passed,
            all_checks=all_checks,
        )
    
    def _log_pipeline_block(
        self,
        gate: str,
        player_id: str,
        stat_type: str,
        direction: str,
        reason: str
    ):
        """Log when pipeline blocks a prop."""
        logger.info(
            f"[BLOCKED][PRE_MODEL_PIPELINE] "
            f"Gate: {gate} | "
            f"Player: {player_id} | "
            f"Prop: {stat_type} {direction.upper()} | "
            f"Reason: {reason}"
        )
    
    def _log_pipeline_pass(
        self,
        player_id: str,
        stat_type: str,
        direction: str,
        role: str,
        z_score: float,
        cv: float,
        obstacle_penalty: float
    ):
        """Log when pipeline allows a prop."""
        logger.debug(
            f"[PASSED][PRE_MODEL_PIPELINE] "
            f"Player: {player_id} | "
            f"Prop: {stat_type} {direction.upper()} | "
            f"Role: {role} | "
            f"z={z_score:+.2f}, CV={cv:.1%}, Obstacles={obstacle_penalty:.0%}"
        )


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def run_batch(
    pipeline: PreModelPipeline,
    props: List[dict]
) -> dict:
    """
    Run pipeline on a batch of props.
    
    Returns summary statistics.
    """
    results = {
        "total": len(props),
        "allowed": 0,
        "blocked": 0,
        "blocked_by_gate": {
            "MINUTES_ROLE_GATE": 0,
            "DIRECTION_GATE": 0,
            "VARIANCE_KILL_SWITCH": 0,
        },
        "role_distribution": {},
        "passed_props": [],
        "blocked_props": [],
    }
    
    for prop in props:
        result = pipeline.run(**prop)
        
        if result.allowed:
            results["allowed"] += 1
            results["passed_props"].append({
                "player_id": prop.get("player_id"),
                "stat_type": prop.get("stat_type"),
                "direction": result.direction,
                "role": result.role,
                "z_score": result.z_score,
                "cv": result.cv,
                "constraints": result.constraints,
            })
        else:
            results["blocked"] += 1
            results["blocked_by_gate"][result.blocked_by] += 1
            results["blocked_props"].append({
                "player_id": prop.get("player_id"),
                "stat_type": prop.get("stat_type"),
                "direction": prop.get("direction"),
                "blocked_by": result.blocked_by,
                "reason": result.reason,
            })
        
        # Track role distribution
        role = result.role
        results["role_distribution"][role] = results["role_distribution"].get(role, 0) + 1
    
    # Calculate percentages
    if results["total"] > 0:
        results["pass_rate"] = results["allowed"] / results["total"]
        results["block_rate"] = results["blocked"] / results["total"]
    
    return results


# =============================================================================
# CLI / DEMO
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s"
    )
    
    pipeline = PreModelPipeline()
    
    print("=" * 75)
    print("PRE-MODEL PIPELINE - DEMO")
    print("=" * 75)
    
    # Test batch
    test_props = [
        # Should PASS - star player, clear edge
        {
            "player_id": "lebron_james",
            "stat_type": "PTS",
            "line": 22.5,
            "direction": "OVER",
            "expected_minutes": 35.0,
            "mu": 26.5,
            "sigma": 5.5,
            "sample_size": 10,
        },
        
        # Should BLOCK (Gate 2) - bench player volume OVER (Minutes & Role)
        {
            "player_id": "bench_guy",
            "stat_type": "PTS",
            "line": 8.5,
            "direction": "OVER",
            "expected_minutes": 15.0,
            "mu": 7.2,
            "sigma": 3.0,
            "sample_size": 10,
        },
        
        # Should BLOCK (Gate 1) - wrong direction (Direction First)
        {
            "player_id": "draymond_green",
            "stat_type": "3PM",
            "line": 1.5,
            "direction": "UNDER",
            "expected_minutes": 28.0,
            "mu": 1.6,
            "sigma": 1.7,
            "sample_size": 10,
        },
        
        # Should BLOCK (Gate 3) - extreme variance
        {
            "player_id": "volatile_shooter",
            "stat_type": "3PM",
            "line": 2.5,
            "direction": "OVER",
            "expected_minutes": 30.0,
            "mu": 3.0,
            "sigma": 2.5,
            "sample_size": 10,
        },
        
        # Should PASS - solid starter, moderate edge
        {
            "player_id": "solid_starter",
            "stat_type": "REB",
            "line": 6.5,
            "direction": "OVER",
            "expected_minutes": 30.0,
            "mu": 8.2,
            "sigma": 2.5,
            "sample_size": 10,
        },
        
        # Should PASS (with caps) - bench player UNDER
        {
            "player_id": "bench_player",
            "stat_type": "PTS",
            "line": 12.5,
            "direction": "UNDER",
            "expected_minutes": 20.0,
            "mu": 9.5,
            "sigma": 3.5,
            "sample_size": 10,
        },
    ]
    
    print("\nRunning batch of 6 props...\n")
    
    for i, prop in enumerate(test_props, 1):
        result = pipeline.run(**prop)
        print(f"Prop {i}: {prop['player_id']} {prop['stat_type']} {prop['direction']}")
        print(f"  {result.summary()}")
        if result.allowed:
            print(f"  Constraints: max_tier={result.constraints.get('max_tier')}, "
                  f"slam_eligible={result.constraints.get('slam_eligible')}")
        print()
    
    print("=" * 75)
    print("BATCH SUMMARY")
    print("=" * 75)
    
    summary = run_batch(pipeline, test_props)
    print(f"\nTotal props: {summary['total']}")
    print(f"Allowed: {summary['allowed']} ({summary['pass_rate']:.0%})")
    print(f"Blocked: {summary['blocked']} ({summary['block_rate']:.0%})")
    print(f"\nBlocked by gate:")
    for gate, count in summary['blocked_by_gate'].items():
        if count > 0:
            print(f"  {gate}: {count}")
    print(f"\nRole distribution:")
    for role, count in summary['role_distribution'].items():
        print(f"  {role}: {count}")
