"""
Unit tests for core/decision_governance.py
UNIFIED DECISION GOVERNANCE (SOP v2.4)

Tests the full Pick State Machine and Eligibility Gate.
"""
import pytest
from unittest.mock import patch, MagicMock

# Import the module under test
from core.decision_governance import (
    PickState,
    RejectionReason,
    VettedReason,
    EligibilityResult,
    EligibilityGate,
    MonteCarloConstraints,
    run_eligibility_gate,
    get_optimizable_picks,
    get_visible_picks,
    get_rejected_picks,
    enforce_governance,
    require_governance_check,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def clean_pick():
    """A pick that should pass all gates and become OPTIMIZABLE."""
    return {
        "player": "LeBron James",
        "stat": "PTS",
        "line": 25.5,
        "direction": "Higher",
        "probability": 0.72,
        "archetype": "ALPHA_ANCHOR",
        "role_volatility": "LOW",
        "matchup_games": 5,
        "flags": [],
    }


@pytest.fixture
def low_prob_pick():
    """A pick below 55% that should be REJECTED."""
    return {
        "player": "Bench Player",
        "stat": "PTS",
        "line": 8.5,
        "direction": "Higher",
        "probability": 0.52,
        "archetype": "BENCH_MICROWAVE",
        "role_volatility": "MODERATE",
        "matchup_games": 3,
        "flags": [],
    }


@pytest.fixture
def high_usage_volatility_pick():
    """A pick with HIGH_USAGE_VOLATILITY flag that should be REJECTED."""
    return {
        "player": "Role Player",
        "stat": "REB",
        "line": 6.5,
        "direction": "Higher",
        "probability": 0.68,
        "archetype": "ROTATION_CORE",
        "role_volatility": "HIGH",
        "matchup_games": 4,
        "flags": ["HIGH_USAGE_VOLATILITY"],
    }


@pytest.fixture
def bench_microwave_pts_pick():
    """A BENCH_MICROWAVE with PTS stat that should be REJECTED."""
    return {
        "player": "6th Man",
        "stat": "PTS",
        "line": 12.5,
        "direction": "Higher",
        "probability": 0.65,
        "archetype": "BENCH_MICROWAVE",
        "role_volatility": "MODERATE",
        "matchup_games": 5,
        "flags": [],
    }


@pytest.fixture
def bench_microwave_ast_pick():
    """A BENCH_MICROWAVE with AST stat that should be REJECTED."""
    return {
        "player": "6th Man",
        "stat": "AST",
        "line": 3.5,
        "direction": "Higher",
        "probability": 0.67,
        "archetype": "BENCH_MICROWAVE",
        "role_volatility": "LOW",
        "matchup_games": 6,
        "flags": [],
    }


@pytest.fixture
def bench_microwave_reb_pick():
    """A BENCH_MICROWAVE with REB stat (NOT PTS/AST) that should PASS."""
    return {
        "player": "6th Man",
        "stat": "REB",
        "line": 5.5,
        "direction": "Higher",
        "probability": 0.66,
        "archetype": "BENCH_MICROWAVE",
        "role_volatility": "LOW",
        "matchup_games": 5,
        "flags": [],
    }


@pytest.fixture
def fragile_pick():
    """A FRAGILE pick that should become VETTED (visible, not optimizable)."""
    return {
        "player": "Injury Prone Star",
        "stat": "PTS",
        "line": 22.5,
        "direction": "Higher",
        "probability": 0.70,
        "archetype": "ALPHA_ANCHOR",
        "role_volatility": "LOW",
        "matchup_games": 5,
        "flags": ["FRAGILE"],
    }


@pytest.fixture
def low_matchup_pick():
    """A pick with < 3 matchup games that should become VETTED with decay."""
    return {
        "player": "New Trade",
        "stat": "PTS",
        "line": 18.5,
        "direction": "Higher",
        "probability": 0.70,
        "archetype": "ROTATION_CORE",
        "role_volatility": "LOW",
        "matchup_games": 2,
        "flags": [],
    }


@pytest.fixture
def mixed_picks_batch(
    clean_pick,
    low_prob_pick,
    high_usage_volatility_pick,
    bench_microwave_pts_pick,
    fragile_pick,
    low_matchup_pick,
):
    """A batch of picks with various states."""
    return [
        clean_pick,
        low_prob_pick,
        high_usage_volatility_pick,
        bench_microwave_pts_pick,
        fragile_pick,
        low_matchup_pick,
    ]


# =============================================================================
# PICK STATE ENUM TESTS
# =============================================================================

class TestPickStateEnum:
    """Test PickState enum values and ordering."""

    def test_all_states_exist(self):
        """Verify all 5 states exist."""
        assert hasattr(PickState, "RAW")
        assert hasattr(PickState, "ADJUSTED")
        assert hasattr(PickState, "VETTED")
        assert hasattr(PickState, "OPTIMIZABLE")
        assert hasattr(PickState, "REJECTED")

    def test_state_values_are_strings(self):
        """States should be string values for JSON serialization."""
        assert PickState.RAW.value == "RAW"
        assert PickState.ADJUSTED.value == "ADJUSTED"
        assert PickState.VETTED.value == "VETTED"
        assert PickState.OPTIMIZABLE.value == "OPTIMIZABLE"
        assert PickState.REJECTED.value == "REJECTED"


# =============================================================================
# REJECTION REASON ENUM TESTS
# =============================================================================

class TestRejectionReasonEnum:
    """Test RejectionReason enum."""

    def test_all_rejection_reasons_exist(self):
        """Verify all rejection reasons exist."""
        assert hasattr(RejectionReason, "LOW_PROBABILITY")
        assert hasattr(RejectionReason, "HIGH_USAGE_VOLATILITY")
        assert hasattr(RejectionReason, "BENCH_MICROWAVE_FRAGILE_STAT")


# =============================================================================
# VETTED REASON ENUM TESTS
# =============================================================================

class TestVettedReasonEnum:
    """Test VettedReason enum."""

    def test_all_vetted_reasons_exist(self):
        """Verify all vetted reasons exist."""
        assert hasattr(VettedReason, "FRAGILE")
        assert hasattr(VettedReason, "LOW_MATCHUP_SAMPLE")


# =============================================================================
# ELIGIBILITY GATE TESTS
# =============================================================================

class TestEligibilityGate:
    """Test EligibilityGate class with all rules in sequence."""

    def test_clean_pick_becomes_optimizable(self, clean_pick):
        """A clean pick with good probability should be OPTIMIZABLE."""
        gate = EligibilityGate()
        result = gate.evaluate(clean_pick)
        
        assert result.state == PickState.OPTIMIZABLE
        assert result.rejection_reason is None
        assert result.vetted_reason is None
        assert result.adjusted_probability == clean_pick["probability"]

    def test_low_probability_rejected(self, low_prob_pick):
        """Probability < 55% should be REJECTED."""
        gate = EligibilityGate()
        result = gate.evaluate(low_prob_pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.LOW_PROBABILITY

    def test_exactly_55_percent_passes(self):
        """Exactly 55% should pass (boundary test)."""
        pick = {
            "player": "Boundary",
            "stat": "PTS",
            "line": 10.0,
            "direction": "Higher",
            "probability": 0.55,
            "archetype": "ROTATION_CORE",
            "role_volatility": "LOW",
            "matchup_games": 5,
            "flags": [],
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        assert result.state == PickState.OPTIMIZABLE

    def test_54_99_percent_rejected(self):
        """54.99% should be REJECTED (boundary test)."""
        pick = {
            "player": "Boundary",
            "stat": "PTS",
            "line": 10.0,
            "direction": "Higher",
            "probability": 0.5499,
            "archetype": "ROTATION_CORE",
            "role_volatility": "LOW",
            "matchup_games": 5,
            "flags": [],
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.LOW_PROBABILITY

    def test_high_usage_volatility_rejected(self, high_usage_volatility_pick):
        """HIGH_USAGE_VOLATILITY flag should be REJECTED."""
        gate = EligibilityGate()
        result = gate.evaluate(high_usage_volatility_pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.HIGH_USAGE_VOLATILITY

    def test_bench_microwave_pts_rejected(self, bench_microwave_pts_pick):
        """BENCH_MICROWAVE with PTS should be REJECTED."""
        gate = EligibilityGate()
        result = gate.evaluate(bench_microwave_pts_pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.BENCH_MICROWAVE_FRAGILE_STAT

    def test_bench_microwave_ast_rejected(self, bench_microwave_ast_pick):
        """BENCH_MICROWAVE with AST should be REJECTED."""
        gate = EligibilityGate()
        result = gate.evaluate(bench_microwave_ast_pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.BENCH_MICROWAVE_FRAGILE_STAT

    def test_bench_microwave_reb_passes(self, bench_microwave_reb_pick):
        """BENCH_MICROWAVE with REB (not PTS/AST) should PASS."""
        gate = EligibilityGate()
        result = gate.evaluate(bench_microwave_reb_pick)
        
        assert result.state == PickState.OPTIMIZABLE

    def test_fragile_becomes_vetted(self, fragile_pick):
        """FRAGILE flag should result in VETTED state."""
        gate = EligibilityGate()
        result = gate.evaluate(fragile_pick)
        
        assert result.state == PickState.VETTED
        assert result.vetted_reason == VettedReason.FRAGILE
        assert result.rejection_reason is None

    def test_low_matchup_becomes_vetted_with_decay(self, low_matchup_pick):
        """matchup_games < 3 should result in VETTED with 0.85 decay."""
        gate = EligibilityGate()
        result = gate.evaluate(low_matchup_pick)
        
        assert result.state == PickState.VETTED
        assert result.vetted_reason == VettedReason.LOW_MATCHUP_SAMPLE
        # Probability should be decayed by 0.85
        expected_prob = 0.70 * 0.85
        assert abs(result.adjusted_probability - expected_prob) < 0.001

    def test_low_matchup_decay_then_reject_if_under_55(self):
        """If decay drops probability below 55%, should be REJECTED."""
        pick = {
            "player": "New Trade",
            "stat": "PTS",
            "line": 15.0,
            "direction": "Higher",
            "probability": 0.60,  # After 0.85 decay = 0.51 → REJECTED
            "archetype": "ROTATION_CORE",
            "role_volatility": "LOW",
            "matchup_games": 1,
            "flags": [],
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        # 0.60 * 0.85 = 0.51 < 0.55 → REJECTED
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.LOW_PROBABILITY

    def test_gate_rule_order_high_usage_before_bench(self):
        """HIGH_USAGE_VOLATILITY should trigger before BENCH_MICROWAVE."""
        pick = {
            "player": "Combo Case",
            "stat": "PTS",
            "line": 10.0,
            "direction": "Higher",
            "probability": 0.65,
            "archetype": "BENCH_MICROWAVE",  # Would be rejected
            "role_volatility": "HIGH",
            "matchup_games": 5,
            "flags": ["HIGH_USAGE_VOLATILITY"],  # Should trigger first
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.HIGH_USAGE_VOLATILITY

    def test_gate_rule_order_bench_before_fragile(self):
        """BENCH_MICROWAVE rejection should trigger before FRAGILE check."""
        pick = {
            "player": "Combo Case",
            "stat": "PTS",
            "line": 12.0,
            "direction": "Higher",
            "probability": 0.68,
            "archetype": "BENCH_MICROWAVE",  # Should reject
            "role_volatility": "LOW",
            "matchup_games": 5,
            "flags": ["FRAGILE"],  # Would be VETTED, but BENCH triggers first
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.BENCH_MICROWAVE_FRAGILE_STAT

    def test_gate_rule_order_fragile_before_matchup(self):
        """FRAGILE should trigger before low matchup sample."""
        pick = {
            "player": "Combo Case",
            "stat": "REB",
            "line": 8.0,
            "direction": "Higher",
            "probability": 0.72,
            "archetype": "ALPHA_ANCHOR",
            "role_volatility": "LOW",
            "matchup_games": 2,  # Would apply decay
            "flags": ["FRAGILE"],  # Should trigger first (no decay applied)
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        assert result.state == PickState.VETTED
        assert result.vetted_reason == VettedReason.FRAGILE
        # Probability should NOT be decayed because FRAGILE triggered first
        assert result.adjusted_probability == 0.72


# =============================================================================
# BATCH PROCESSING TESTS
# =============================================================================

class TestBatchProcessing:
    """Test batch processing functions."""

    def test_run_eligibility_gate_batch(self, mixed_picks_batch):
        """run_eligibility_gate should process all picks."""
        results = run_eligibility_gate(mixed_picks_batch)
        
        assert len(results) == len(mixed_picks_batch)
        # Check each pick has a result
        for pick, result in results:
            assert isinstance(result, EligibilityResult)
            assert result.state in PickState

    def test_get_optimizable_picks(self, mixed_picks_batch):
        """get_optimizable_picks should return only OPTIMIZABLE state."""
        results = run_eligibility_gate(mixed_picks_batch)
        optimizable = get_optimizable_picks(results)
        
        # Only clean_pick should be optimizable
        assert len(optimizable) == 1
        pick, result = optimizable[0]
        assert pick["player"] == "LeBron James"
        assert result.state == PickState.OPTIMIZABLE

    def test_get_visible_picks(self, mixed_picks_batch):
        """get_visible_picks should return OPTIMIZABLE and VETTED."""
        results = run_eligibility_gate(mixed_picks_batch)
        visible = get_visible_picks(results)
        
        # clean_pick (OPTIMIZABLE), fragile_pick (VETTED), low_matchup_pick (VETTED)
        assert len(visible) == 3
        states = [r.state for _, r in visible]
        assert PickState.OPTIMIZABLE in states
        assert PickState.VETTED in states
        assert PickState.REJECTED not in states

    def test_get_rejected_picks(self, mixed_picks_batch):
        """get_rejected_picks should return only REJECTED state."""
        results = run_eligibility_gate(mixed_picks_batch)
        rejected = get_rejected_picks(results)
        
        # low_prob_pick, high_usage_volatility_pick, bench_microwave_pts_pick
        assert len(rejected) == 3
        for _, result in rejected:
            assert result.state == PickState.REJECTED

    def test_empty_batch_handling(self):
        """Empty batch should return empty results."""
        results = run_eligibility_gate([])
        assert results == []
        
        optimizable = get_optimizable_picks(results)
        assert optimizable == []


# =============================================================================
# ENFORCE GOVERNANCE TESTS
# =============================================================================

class TestEnforceGovernance:
    """Test the main enforce_governance entry point."""

    def test_enforce_governance_returns_dict(self, mixed_picks_batch):
        """enforce_governance should return a governance dict."""
        gov = enforce_governance(mixed_picks_batch)
        
        assert "all_results" in gov
        assert "optimizable" in gov
        assert "visible" in gov
        assert "rejected" in gov
        assert "stats" in gov

    def test_enforce_governance_stats(self, mixed_picks_batch):
        """Stats should have correct counts."""
        gov = enforce_governance(mixed_picks_batch)
        stats = gov["stats"]
        
        assert stats["total"] == 6
        assert stats["optimizable"] == 1
        assert stats["vetted"] == 2
        assert stats["rejected"] == 3

    def test_enforce_governance_with_force_apply(self, clean_pick):
        """force_apply=True should mark all picks as OPTIMIZABLE."""
        picks = [clean_pick]
        # Add a pick that would normally be rejected
        picks.append({
            "player": "Forced",
            "stat": "PTS",
            "line": 5.0,
            "direction": "Higher",
            "probability": 0.30,  # Would be rejected
            "archetype": "BENCH_MICROWAVE",
            "role_volatility": "HIGH",
            "matchup_games": 1,
            "flags": ["HIGH_USAGE_VOLATILITY", "FRAGILE"],
        })
        
        gov = enforce_governance(picks, force_apply=True)
        
        # Both should be OPTIMIZABLE when forced
        assert gov["stats"]["optimizable"] == 2
        assert gov["stats"]["rejected"] == 0


# =============================================================================
# REQUIRE GOVERNANCE CHECK TESTS
# =============================================================================

class TestRequireGovernanceCheck:
    """Test the assertion function."""

    def test_require_governance_check_passes_with_optimizable(self, clean_pick):
        """Should not raise when all picks are OPTIMIZABLE."""
        gov = enforce_governance([clean_pick])
        # Should not raise
        require_governance_check(gov)

    def test_require_governance_check_fails_without_optimizable(self, low_prob_pick):
        """Should raise when no picks are OPTIMIZABLE."""
        gov = enforce_governance([low_prob_pick])
        
        with pytest.raises(RuntimeError, match="No OPTIMIZABLE picks"):
            require_governance_check(gov)

    def test_require_governance_check_with_allow_empty(self, low_prob_pick):
        """allow_empty=True should not raise even with no OPTIMIZABLE."""
        gov = enforce_governance([low_prob_pick])
        # Should not raise
        require_governance_check(gov, allow_empty=True)


# =============================================================================
# MONTE CARLO CONSTRAINTS TESTS
# =============================================================================

class TestMonteCarloConstraints:
    """Test MonteCarloConstraints validation."""

    def test_constraints_default_values(self):
        """Default constraints should be set correctly."""
        constraints = MonteCarloConstraints()
        
        assert constraints.max_legs_with_fragile == 2
        assert constraints.allow_flex_with_fragile is False
        assert constraints.kelly_reduction_fallback == 0.5

    def test_constraints_custom_values(self):
        """Custom constraint values should be accepted."""
        constraints = MonteCarloConstraints(
            max_legs_with_fragile=3,
            allow_flex_with_fragile=True,
            kelly_reduction_fallback=0.75,
        )
        
        assert constraints.max_legs_with_fragile == 3
        assert constraints.allow_flex_with_fragile is True
        assert constraints.kelly_reduction_fallback == 0.75

    def test_validate_entry_without_fragile(self, clean_pick):
        """Entry without FRAGILE should pass all validations."""
        constraints = MonteCarloConstraints()
        gov = enforce_governance([clean_pick])
        entry = gov["optimizable"]
        
        is_valid, reason = constraints.validate_entry(entry, is_flex=True)
        assert is_valid is True
        assert reason is None

    def test_validate_entry_with_fragile_blocks_flex(self, fragile_pick):
        """Entry with FRAGILE should block FLEX."""
        constraints = MonteCarloConstraints()
        gov = enforce_governance([fragile_pick])
        entry = gov["visible"]  # FRAGILE is VETTED, so in visible
        
        is_valid, reason = constraints.validate_entry(entry, is_flex=True)
        assert is_valid is False
        assert "FRAGILE" in reason

    def test_validate_entry_with_fragile_caps_legs(self, fragile_pick, clean_pick):
        """Entry with FRAGILE should cap at max_legs_with_fragile."""
        constraints = MonteCarloConstraints(max_legs_with_fragile=2)
        
        # Create a 3-leg entry with fragile
        gov = enforce_governance([fragile_pick, clean_pick, clean_pick.copy()])
        entry = gov["visible"]
        
        is_valid, reason = constraints.validate_entry(entry, is_flex=False, leg_count=3)
        assert is_valid is False
        assert "2-leg" in reason.lower() or "max" in reason.lower()


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_missing_probability_field(self):
        """Pick without probability should handle gracefully."""
        pick = {
            "player": "Missing Prob",
            "stat": "PTS",
            "line": 10.0,
            "direction": "Higher",
            # No probability field
            "archetype": "ROTATION_CORE",
            "matchup_games": 5,
            "flags": [],
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        # Should be REJECTED due to missing/low probability
        assert result.state == PickState.REJECTED

    def test_missing_flags_field(self, clean_pick):
        """Pick without flags should default to empty list."""
        del clean_pick["flags"]
        gate = EligibilityGate()
        result = gate.evaluate(clean_pick)
        
        # Should still be OPTIMIZABLE
        assert result.state == PickState.OPTIMIZABLE

    def test_missing_archetype_field(self, clean_pick):
        """Pick without archetype should handle gracefully."""
        del clean_pick["archetype"]
        gate = EligibilityGate()
        result = gate.evaluate(clean_pick)
        
        # Should still be OPTIMIZABLE (BENCH_MICROWAVE check won't trigger)
        assert result.state == PickState.OPTIMIZABLE

    def test_missing_matchup_games_field(self, clean_pick):
        """Pick without matchup_games should default to passing."""
        del clean_pick["matchup_games"]
        gate = EligibilityGate()
        result = gate.evaluate(clean_pick)
        
        # Should be OPTIMIZABLE (no low matchup decay)
        assert result.state == PickState.OPTIMIZABLE

    def test_none_values_handled(self):
        """None values should be handled gracefully."""
        pick = {
            "player": "None Values",
            "stat": None,
            "line": None,
            "direction": None,
            "probability": 0.70,
            "archetype": None,
            "matchup_games": None,
            "flags": None,
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        # Should be OPTIMIZABLE (None values don't trigger rejection)
        assert result.state == PickState.OPTIMIZABLE

    def test_uppercase_stat_matching(self):
        """Stat matching should be case-insensitive."""
        pick = {
            "player": "Case Test",
            "stat": "pts",  # lowercase
            "line": 10.0,
            "direction": "Higher",
            "probability": 0.65,
            "archetype": "BENCH_MICROWAVE",
            "matchup_games": 5,
            "flags": [],
        }
        gate = EligibilityGate()
        result = gate.evaluate(pick)
        
        # Should be REJECTED (BENCH_MICROWAVE with PTS)
        assert result.state == PickState.REJECTED
        assert result.rejection_reason == RejectionReason.BENCH_MICROWAVE_FRAGILE_STAT


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_full_slate_processing(self):
        """Process a realistic slate of picks."""
        slate = [
            # OPTIMIZABLE picks
            {"player": "Star 1", "stat": "PTS", "line": 25.5, "probability": 0.75,
             "archetype": "ALPHA_ANCHOR", "matchup_games": 5, "flags": []},
            {"player": "Star 2", "stat": "REB", "line": 10.5, "probability": 0.68,
             "archetype": "ROTATION_CORE", "matchup_games": 4, "flags": []},
            
            # VETTED picks
            {"player": "Fragile Star", "stat": "AST", "line": 8.5, "probability": 0.72,
             "archetype": "ALPHA_ANCHOR", "matchup_games": 6, "flags": ["FRAGILE"]},
            {"player": "New Trade", "stat": "PTS", "line": 15.5, "probability": 0.66,
             "archetype": "ROTATION_CORE", "matchup_games": 2, "flags": []},
            
            # REJECTED picks
            {"player": "Low Prob", "stat": "PTS", "line": 12.5, "probability": 0.50,
             "archetype": "ROTATION_CORE", "matchup_games": 5, "flags": []},
            {"player": "Volatile", "stat": "REB", "line": 6.5, "probability": 0.62,
             "archetype": "ROTATION_CORE", "matchup_games": 4, "flags": ["HIGH_USAGE_VOLATILITY"]},
            {"player": "Bench Scorer", "stat": "PTS", "line": 10.5, "probability": 0.63,
             "archetype": "BENCH_MICROWAVE", "matchup_games": 5, "flags": []},
        ]
        
        gov = enforce_governance(slate)
        
        assert gov["stats"]["total"] == 7
        assert gov["stats"]["optimizable"] == 2
        assert gov["stats"]["vetted"] == 2
        assert gov["stats"]["rejected"] == 3

    def test_governance_before_monte_carlo(self):
        """Ensure governance is checked before optimization."""
        picks = [
            {"player": "Low Prob 1", "stat": "PTS", "line": 10.0, "probability": 0.40,
             "archetype": "ROTATION_CORE", "matchup_games": 5, "flags": []},
            {"player": "Low Prob 2", "stat": "REB", "line": 8.0, "probability": 0.45,
             "archetype": "ROTATION_CORE", "matchup_games": 5, "flags": []},
        ]
        
        gov = enforce_governance(picks)
        
        # Should have no optimizable picks
        assert gov["stats"]["optimizable"] == 0
        
        # Attempting require_governance_check should fail
        with pytest.raises(RuntimeError):
            require_governance_check(gov)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
