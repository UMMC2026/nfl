"""
REGRESSION LOCK TESTS — Decision Governance
============================================

These tests PREVENT the governance system from ever breaking again.
Run with: pytest tests/test_governance_regression.py -v

Every test in this file represents a HARD CONTRACT that must never be violated.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Import governance modules
from core.decision_governance import (
    PickState,
    RejectionReason,
    VettedReason,
    EligibilityGate,
    EligibilityResult,
    run_eligibility_gate,
    get_optimizable_picks,
    enforce_governance,
)

from core.shot_profile_archetypes import (
    ShotProfileArchetype,
    ShotProfileClassifier,
    ThreePointGovernor,
    run_3pm_governance,
    SHOT_PROFILE_CONFIDENCE_CEILINGS,
)


# =============================================================================
# 🔐 REGRESSION LOCK: PICK STATE TRANSITIONS
# =============================================================================

class TestPickStateTransitionsRegressionLock:
    """
    These tests lock the pick state transition rules.
    ANY change to these rules requires explicit approval.
    """

    def test_low_probability_rejected(self):
        """
        REGRESSION LOCK: Probability < 55% MUST always result in REJECTED.
        This is a HARD RULE that cannot be bypassed.
        """
        gate = EligibilityGate()
        
        # Test at 54%
        pick = self._make_pick(probability=54)
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.LOW_PROBABILITY
        
        # Test at 54.9%
        pick = self._make_pick(probability=54.9)
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED
        
        # Test at 0%
        pick = self._make_pick(probability=0)
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED

    def test_high_usage_volatility_rejected(self):
        """
        REGRESSION LOCK: HIGH_USAGE_VOLATILITY flag MUST always result in REJECTED.
        Even with high probability.
        """
        gate = EligibilityGate()
        
        pick = self._make_pick(probability=70)
        pick["flags"] = ["HIGH_USAGE_VOLATILITY"]
        
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.HIGH_USAGE_VOLATILITY

    def test_fragile_never_optimizable(self):
        """
        REGRESSION LOCK: FRAGILE flag MUST result in VETTED, never OPTIMIZABLE.
        FRAGILE picks are visible but cannot enter Monte Carlo.
        """
        gate = EligibilityGate()
        
        pick = self._make_pick(probability=68)
        pick["flags"] = ["FRAGILE"]
        
        result = gate.evaluate(pick)
        assert result.state == PickState.VETTED
        assert result.vetted_reason == VettedReason.FRAGILE_FLAG
        assert result.state != PickState.OPTIMIZABLE

    def test_bench_microwave_pts_rejected(self):
        """
        REGRESSION LOCK: BENCH_MICROWAVE + PTS MUST be REJECTED.
        """
        gate = EligibilityGate()
        
        pick = self._make_pick(probability=65, stat="PTS")
        pick["archetype"] = "BENCH_MICROWAVE"
        
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.BENCH_MICROWAVE_FRAGILE

    def test_bench_microwave_ast_rejected(self):
        """
        REGRESSION LOCK: BENCH_MICROWAVE + AST MUST be REJECTED.
        """
        gate = EligibilityGate()
        
        pick = self._make_pick(probability=65, stat="AST")
        pick["archetype"] = "BENCH_MICROWAVE"
        
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED

    def _make_pick(self, probability: float, stat: str = "REB") -> Dict[str, Any]:
        """Helper to create a test pick."""
        return {
            "player": "Test Player",
            "stat": stat,
            "line": 10.0,
            "direction": "Higher",
            "probability": probability,
            "archetype": "ROTATION_CORE",
            "matchup_games_vs": 5,
            "flags": [],
        }


# =============================================================================
# 🔐 REGRESSION LOCK: MATCHUP MEMORY DECAY
# =============================================================================

class TestMatchupMemoryDecayRegressionLock:
    """
    These tests lock the matchup sample decay behavior.
    """

    def test_matchup_sample_decay_applied(self):
        """
        REGRESSION LOCK: matchup_games < 3 MUST apply 0.85 decay.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Test",
            "stat": "PTS",
            "line": 15.0,
            "direction": "Higher",
            "probability": 70,  # 70 * 0.85 = 59.5
            "archetype": "ROTATION_CORE",
            "matchup_games_vs": 2,
            "flags": [],
        }
        
        result = gate.evaluate(pick)
        
        # Decay should be applied
        assert result.final_probability < 70
        assert abs(result.final_probability - 59.5) < 0.1
        assert result.state == PickState.VETTED
        assert result.vetted_reason == VettedReason.MATCHUP_DECAY

    def test_matchup_decay_can_cause_rejection(self):
        """
        REGRESSION LOCK: If decay drops probability below 55%, MUST reject.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Test",
            "stat": "PTS",
            "line": 10.0,
            "direction": "Higher",
            "probability": 60,  # 60 * 0.85 = 51 < 55
            "archetype": "ROTATION_CORE",
            "matchup_games_vs": 1,
            "flags": [],
        }
        
        result = gate.evaluate(pick)
        
        # Should be rejected after decay
        assert result.state == PickState.REJECTED


# =============================================================================
# 🔐 REGRESSION LOCK: MONTE CARLO ENFORCEMENT
# =============================================================================

class TestMonteCarloEnforcementRegressionLock:
    """
    These tests ensure Monte Carlo NEVER receives non-OPTIMIZABLE picks.
    """

    def test_monte_carlo_rejects_non_optimizable(self):
        """
        REGRESSION LOCK: get_optimizable_picks MUST filter out REJECTED/VETTED.
        """
        gate = EligibilityGate()
        
        picks = [
            # REJECTED (low prob)
            {"player": "Low", "stat": "PTS", "line": 10, "probability": 40, 
             "archetype": "ROTATION_CORE", "matchup_games_vs": 5, "flags": []},
            # VETTED (fragile)
            {"player": "Fragile", "stat": "PTS", "line": 20, "probability": 70, 
             "archetype": "ALPHA_ANCHOR", "matchup_games_vs": 5, "flags": ["FRAGILE"]},
            # OPTIMIZABLE (clean)
            {"player": "Clean", "stat": "REB", "line": 8, "probability": 68, 
             "archetype": "ROTATION_CORE", "matchup_games_vs": 5, "flags": []},
        ]
        
        processed, _ = run_eligibility_gate(picks)
        optimizable = get_optimizable_picks(processed)
        
        # Only the clean pick should be optimizable
        assert len(optimizable) == 1
        assert optimizable[0]["player"] == "Clean"

    def test_enforce_governance_stats(self):
        """
        REGRESSION LOCK: enforce_governance MUST return accurate stats.
        """
        picks = [
            # REJECTED
            {"player": "R1", "stat": "PTS", "probability": 40, 
             "archetype": "ROTATION_CORE", "matchup_games_vs": 5, "flags": []},
            {"player": "R2", "stat": "PTS", "probability": 70, 
             "archetype": "ROTATION_CORE", "matchup_games_vs": 5, "flags": ["HIGH_USAGE_VOLATILITY"]},
            # VETTED
            {"player": "V1", "stat": "PTS", "probability": 72, 
             "archetype": "ALPHA_ANCHOR", "matchup_games_vs": 5, "flags": ["FRAGILE"]},
            # OPTIMIZABLE
            {"player": "O1", "stat": "REB", "probability": 65, 
             "archetype": "ROTATION_CORE", "matchup_games_vs": 5, "flags": []},
        ]
        
        processed, stats = run_eligibility_gate(picks)
        
        assert stats["rejected"] == 2
        assert stats["vetted"] == 1
        assert stats["optimizable"] == 1
        assert stats["total"] == 4


# =============================================================================
# 🔐 REGRESSION LOCK: FRAGILE FLEX BLOCKING
# =============================================================================

class TestFragileFlexBlockingRegressionLock:
    """
    These tests ensure FRAGILE picks cannot enter FLEX entries.
    """

    def test_fragile_identified_in_governance(self):
        """
        REGRESSION LOCK: FRAGILE must be identified and marked.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Fragile Star",
            "stat": "AST",
            "line": 8.5,
            "probability": 72,
            "archetype": "ALPHA_ANCHOR",
            "matchup_games_vs": 6,
            "flags": ["FRAGILE"],
        }
        
        result = gate.evaluate(pick)
        
        assert result.state == PickState.VETTED
        assert "FRAGILE" in result.flags_detected


# =============================================================================
# 🔐 REGRESSION LOCK: FALLBACK KELLY REDUCTION
# =============================================================================

class TestFallbackKellyReductionRegressionLock:
    """
    These tests ensure fallback mode reduces Kelly stake.
    """
    
    # Note: This test requires MonteCarloConstraints integration
    # The actual Kelly reduction is applied in monte_carlo_optimizer.py
    
    def test_fallback_mode_flag_exists(self):
        """
        REGRESSION LOCK: System must support fallback_mode flag.
        """
        # Verify the decision governance module exports the right structures
        from core.decision_governance import MonteCarloConstraints
        
        constraints = MonteCarloConstraints()
        assert hasattr(constraints, 'kelly_reduction_fallback')
        assert constraints.kelly_reduction_fallback == 0.5


# =============================================================================
# 🔐 REGRESSION LOCK: AUTHORITY CONFLICT RESOLUTION
# =============================================================================

class TestAuthorityConflictResolutionRegressionLock:
    """
    These tests ensure governance ALWAYS wins over probability.
    """

    def test_governance_overrides_high_probability(self):
        """
        REGRESSION LOCK: Even 72% probability is REJECTED with HIGH_USAGE_VOLATILITY.
        Probability does NOT imply eligibility.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "High Prob Volatile",
            "stat": "PTS",
            "line": 25.0,
            "probability": 72,
            "archetype": "ALPHA_ANCHOR",
            "matchup_games_vs": 10,
            "flags": ["HIGH_USAGE_VOLATILITY"],
        }
        
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED

    def test_governance_overrides_perfect_matchup(self):
        """
        REGRESSION LOCK: Even perfect matchup history is REJECTED if volatility flag set.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Perfect Matchup Volatile",
            "stat": "PTS",
            "line": 20.0,
            "probability": 80,
            "archetype": "ALPHA_ANCHOR",
            "matchup_games_vs": 20,  # Large sample
            "flags": ["HIGH_USAGE_VOLATILITY"],
        }
        
        result = gate.evaluate(pick)
        assert result.state == PickState.REJECTED


# =============================================================================
# 🔐 REGRESSION LOCK: 3PM SHOT PROFILE GOVERNANCE
# =============================================================================

class TestThreePointGovernanceRegressionLock:
    """
    These tests lock the 3PM-specific governance rules.
    """

    def test_catch_and_shoot_ceiling_70(self):
        """
        REGRESSION LOCK: CATCH_AND_SHOOT_SPECIALIST max conf = 70%.
        """
        ceiling = SHOT_PROFILE_CONFIDENCE_CEILINGS[ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST]
        assert ceiling == 70.0

    def test_volume_off_ball_ceiling_65(self):
        """
        REGRESSION LOCK: VOLUME_OFF_BALL_SHOOTER max conf = 65%.
        """
        ceiling = SHOT_PROFILE_CONFIDENCE_CEILINGS[ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER]
        assert ceiling == 65.0

    def test_primary_creator_ceiling_58(self):
        """
        REGRESSION LOCK: PRIMARY_CREATOR_3PT_OVERLAY max conf = 58%.
        """
        ceiling = SHOT_PROFILE_CONFIDENCE_CEILINGS[ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY]
        assert ceiling == 58.0

    def test_corner_only_ceiling_55(self):
        """
        REGRESSION LOCK: CORNER_ONLY_ROLE_PLAYER max conf = 55%.
        """
        ceiling = SHOT_PROFILE_CONFIDENCE_CEILINGS[ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER]
        assert ceiling == 55.0

    def test_3pm_ceiling_applied_correctly(self):
        """
        REGRESSION LOCK: 3PM confidence MUST be capped by archetype ceiling.
        """
        governor = ThreePointGovernor()
        
        # Klay Thompson is CATCH_AND_SHOOT_SPECIALIST (ceiling 70%)
        pick = {
            "player": "Klay Thompson",
            "stat": "3PM",
            "probability": 75,  # Above ceiling
        }
        
        governed = governor.govern(pick)
        
        assert governed["3pm_governed"] is True
        assert governed["3pm_ceiling_applied"] is True
        assert governed["3pm_governed_confidence"] == 70.0

    def test_3pm_ceiling_not_applied_to_other_stats(self):
        """
        REGRESSION LOCK: 3PM ceilings MUST NOT apply to non-3PM stats.
        """
        governor = ThreePointGovernor()
        
        pick = {
            "player": "Klay Thompson",
            "stat": "PTS",  # Not 3PM
            "probability": 75,
        }
        
        governed = governor.govern(pick)
        
        # Should not have 3PM governance applied
        assert governed.get("3pm_governed") is None or governed.get("3pm_governed") is False

    def test_known_profiles_exist_for_key_players(self):
        """
        REGRESSION LOCK: Key players must have defined shot profiles.
        """
        classifier = ShotProfileClassifier()
        
        # Catch and shoot
        assert classifier.classify("Klay Thompson") == ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST
        assert classifier.classify("Duncan Robinson") == ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST
        
        # Primary creators
        assert classifier.classify("Stephen Curry") == ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY
        assert classifier.classify("Damian Lillard") == ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY
        
        # Corner only
        assert classifier.classify("Royce O'Neale") == ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER


# =============================================================================
# 🔐 REGRESSION LOCK: GATE ORDER
# =============================================================================

class TestGateOrderRegressionLock:
    """
    These tests ensure gates are applied in the correct order.
    """

    def test_low_prob_checked_first(self):
        """
        REGRESSION LOCK: Low probability must be checked BEFORE other flags.
        """
        gate = EligibilityGate()
        
        # Low prob + FRAGILE
        pick = {
            "player": "Test",
            "stat": "PTS",
            "probability": 40,  # Would be rejected
            "archetype": "ALPHA_ANCHOR",
            "matchup_games_vs": 5,
            "flags": ["FRAGILE"],  # Would be VETTED if prob was higher
        }
        
        result = gate.evaluate(pick)
        
        # Should be REJECTED due to low prob, not VETTED due to FRAGILE
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.LOW_PROBABILITY

    def test_high_usage_volatility_before_bench_microwave(self):
        """
        REGRESSION LOCK: HIGH_USAGE_VOLATILITY checked before BENCH_MICROWAVE.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Test",
            "stat": "PTS",
            "probability": 65,
            "archetype": "BENCH_MICROWAVE",  # Would be rejected
            "matchup_games_vs": 5,
            "flags": ["HIGH_USAGE_VOLATILITY"],  # Should trigger first
        }
        
        result = gate.evaluate(pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.HIGH_USAGE_VOLATILITY

    def test_bench_microwave_before_fragile(self):
        """
        REGRESSION LOCK: BENCH_MICROWAVE rejection before FRAGILE check.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Test",
            "stat": "PTS",  # PTS on BENCH_MICROWAVE = reject
            "probability": 68,
            "archetype": "BENCH_MICROWAVE",
            "matchup_games_vs": 5,
            "flags": ["FRAGILE"],  # Would be VETTED, but BENCH triggers first
        }
        
        result = gate.evaluate(pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.BENCH_MICROWAVE_FRAGILE

    def test_fragile_before_matchup_decay(self):
        """
        REGRESSION LOCK: FRAGILE triggers before matchup decay.
        """
        gate = EligibilityGate()
        
        pick = {
            "player": "Test",
            "stat": "REB",  # Not fragile stat
            "probability": 72,
            "archetype": "ALPHA_ANCHOR",
            "matchup_games_vs": 2,  # Would apply decay
            "flags": ["FRAGILE"],  # Should trigger first (no decay)
        }
        
        result = gate.evaluate(pick)
        
        assert result.state == PickState.VETTED
        assert result.vetted_reason == VettedReason.FRAGILE_FLAG
        # Probability should NOT be decayed
        assert result.final_probability == 72


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
