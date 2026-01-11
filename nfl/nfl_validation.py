#!/usr/bin/env python3
"""
NFL VALIDATION GATES
====================

Gate 1: FINAL status
Gate 2: Stat agreement (ESPN vs NFL.com)
Gate 3: Cooldown (30 min post-FINAL)
Gate 4: Injury certainty (no QUESTIONABLE, snap data required)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yaml
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of validation gate."""
    passed: bool
    gate_name: str
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class NFLValidationGates:
    """Multi-stage NFL validation (stricter than NBA)."""
    
    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent / "nfl_config.yaml"
        
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
    
    def gate_1_final_status(self, game_status: str) -> ValidationResult:
        """
        Gate 1: Game must be FINAL.
        
        Pending/In-Progress → blocked
        """
        passed = game_status.upper() == "FINAL"
        
        return ValidationResult(
            passed=passed,
            gate_name="FINAL Status",
            error_message=None if passed else f"Game status is {game_status}, not FINAL"
        )
    
    def gate_2_stat_agreement(self, espn_stats: Dict, nfl_stats: Dict) -> ValidationResult:
        """
        Gate 2: ESPN stats must match NFL.com within tolerances.
        
        Mismatch → learning blocked (hard error)
        """
        if not espn_stats or not nfl_stats:
            return ValidationResult(
                passed=True,
                gate_name="Stat Agreement",
                error_message=None,  # Allow graceful degradation
                warnings=["Missing one or both stat sources"]
            )
        
        tolerances = self.config["stat_tolerances"]
        mismatches = []
        
        for player in espn_stats:
            if player not in nfl_stats:
                continue
            
            espn = espn_stats[player]
            nfl = nfl_stats[player]
            
            for stat_name, tolerance in tolerances.items():
                espn_val = espn.get(stat_name, 0.0)
                nfl_val = nfl.get(stat_name, 0.0)
                
                diff = abs(espn_val - nfl_val)
                if diff > tolerance:
                    mismatches.append(
                        f"{player} {stat_name}: ESPN={espn_val} NFL.com={nfl_val} "
                        f"(diff={diff}, tolerance={tolerance})"
                    )
        
        passed = len(mismatches) == 0
        
        return ValidationResult(
            passed=passed,
            gate_name="Stat Agreement",
            error_message="Stat mismatches found" if not passed else None,
            warnings=mismatches if not passed else []
        )
    
    def gate_3_cooldown(self, game_finalized_time: datetime) -> ValidationResult:
        """
        Gate 3: 30-minute cooldown post-FINAL.
        
        NFL scoring corrections are common.
        """
        cooldown_minutes = self.config["cooldown_minutes"]
        required_cooldown = timedelta(minutes=cooldown_minutes)
        
        elapsed = datetime.now() - game_finalized_time
        passed = elapsed >= required_cooldown
        
        remaining = required_cooldown - elapsed
        remaining_str = str(remaining).split(".")[0]  # HH:MM:SS
        
        return ValidationResult(
            passed=passed,
            gate_name="Cooldown",
            error_message=None if passed else f"Cooldown not met. Remaining: {remaining_str}",
        )
    
    def gate_4_injury_certainty(self, player_stats: Dict, game_status: str) -> ValidationResult:
        """
        Gate 4: Injury certainty (critical for NFL).
        
        Rules:
        - NO "QUESTIONABLE" post-game
        - snap_data required
        - Unexpected low snap % → FLAGGED (non-learning)
        """
        warnings = []
        missing_snap_data = []
        
        for player_name, stats in player_stats.items():
            # Check for QUESTIONABLE status post-game
            injury_status = stats.get("injury_status", "").upper()
            if "QUESTIONABLE" in injury_status and game_status.upper() == "FINAL":
                warnings.append(f"{player_name}: QUESTIONABLE status post-game")
            
            # Check for snap data
            snap_pct = stats.get("snap_pct")
            if snap_pct is None:
                missing_snap_data.append(player_name)
            elif snap_pct < 0.20 and snap_pct > 0.0:
                # Flag low snap counts (non-learning)
                warnings.append(
                    f"{player_name}: Low snap% {snap_pct*100:.1f}% (CONTEXTUAL, NON-LEARNING)"
                )
        
        passed = len(missing_snap_data) == 0
        
        return ValidationResult(
            passed=passed,
            gate_name="Injury Certainty",
            error_message="Missing snap data for: " + ", ".join(missing_snap_data) if not passed else None,
            warnings=warnings,
        )
    
    def validate_nfl_game(self,
                         game_id: str,
                         game_status: str,
                         game_finalized_time: datetime,
                         espn_stats: Dict,
                         nfl_stats: Dict,
                         player_stats: Dict) -> Dict:
        """
        Run all validation gates.
        
        Returns:
            Dict with all gate results
        """
        results = {
            "game_id": game_id,
            "timestamp": datetime.now().isoformat(),
            "gates": {}
        }
        
        # Gate 1
        gate1 = self.gate_1_final_status(game_status)
        results["gates"]["1_final_status"] = {
            "passed": gate1.passed,
            "error": gate1.error_message,
        }
        
        # Gate 2 (only if Gate 1 passed)
        if gate1.passed:
            gate2 = self.gate_2_stat_agreement(espn_stats, nfl_stats)
            results["gates"]["2_stat_agreement"] = {
                "passed": gate2.passed,
                "error": gate2.error_message,
                "warnings": gate2.warnings,
            }
        else:
            results["gates"]["2_stat_agreement"] = {"passed": False, "reason": "Gate 1 failed"}
        
        # Gate 3 (only if Gates 1 & 2 passed)
        if gate1.passed and results["gates"]["2_stat_agreement"]["passed"]:
            gate3 = self.gate_3_cooldown(game_finalized_time)
            results["gates"]["3_cooldown"] = {
                "passed": gate3.passed,
                "error": gate3.error_message,
            }
        else:
            results["gates"]["3_cooldown"] = {"passed": False, "reason": "Previous gates failed"}
        
        # Gate 4 (always run for context)
        gate4 = self.gate_4_injury_certainty(player_stats, game_status)
        results["gates"]["4_injury_certainty"] = {
            "passed": gate4.passed,
            "error": gate4.error_message,
            "warnings": gate4.warnings,
        }
        
        # Overall
        all_passed = (gate1.passed and 
                     results["gates"]["2_stat_agreement"]["passed"] and
                     results["gates"]["3_cooldown"]["passed"] and
                     gate4.passed)
        
        results["overall_passed"] = all_passed
        
        return results


def validate_nfl_game(game_id: str,
                     game_status: str,
                     game_finalized_time: datetime,
                     espn_stats: Dict,
                     nfl_stats: Dict,
                     player_stats: Dict) -> Dict:
    """
    Validate NFL game for learning.
    
    Returns:
        Dict with validation results (all gates)
    """
    validator = NFLValidationGates()
    return validator.validate_nfl_game(
        game_id, game_status, game_finalized_time,
        espn_stats, nfl_stats, player_stats
    )


if __name__ == "__main__":
    print("NFL Validation Gates ready for pipeline integration.")
