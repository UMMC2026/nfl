"""
NHL GOALIE GATE TESTS — Hard Gate Assertions
=============================================

Tests for the goalie confirmation gate.
ALL tests must pass for pipeline to proceed.

Non-negotiables:
- Goalie must be confirmed by ≥2 sources
- <5 starts → cap at 58%
- B2B penalty (-4%)
- Unknown goalie = ABORT
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sports.nhl.goalies.confirmation_gate import (
    GoalieStatus,
    GoalieConfirmationGate,
    confirm_both_goalies,
    apply_goalie_adjustments,
)


# ─────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────

@pytest.fixture
def confirmed_goalie():
    """Fully confirmed goalie status."""
    return GoalieStatus(
        name="Jeremy Swayman",
        team="BOS",
        confirmed=True,
        sources=["nhl_api", "dailyfaceoff"],
        starts_last_30=15,
        is_b2b=False,
    )


@pytest.fixture
def unconfirmed_goalie():
    """Unconfirmed goalie status."""
    return GoalieStatus(
        name="Unknown",
        team="BOS",
        confirmed=False,
        sources=[],
        starts_last_30=0,
        is_b2b=False,
    )


@pytest.fixture
def b2b_goalie():
    """Goalie on back-to-back."""
    return GoalieStatus(
        name="Jeremy Swayman",
        team="BOS",
        confirmed=True,
        sources=["nhl_api", "dailyfaceoff"],
        starts_last_30=15,
        is_b2b=True,
    )


@pytest.fixture
def low_start_goalie():
    """Goalie with <5 starts."""
    return GoalieStatus(
        name="Brandon Bussi",
        team="BOS",
        confirmed=True,
        sources=["nhl_api", "dailyfaceoff"],
        starts_last_30=3,
        is_b2b=False,
    )


@pytest.fixture
def single_source_goalie():
    """Goalie confirmed by only 1 source."""
    return GoalieStatus(
        name="Jeremy Swayman",
        team="BOS",
        confirmed=True,
        sources=["nhl_api"],  # Only 1 source
        starts_last_30=15,
        is_b2b=False,
    )


# ─────────────────────────────────────────────────────────
# GATE 1: GOALIE CONFIRMATION (≥2 sources)
# ─────────────────────────────────────────────────────────

class TestGoalieConfirmationGate:
    """Tests for goalie confirmation requirements."""
    
    def test_confirmed_goalie_passes(self, confirmed_goalie):
        """Confirmed goalie with ≥2 sources should pass."""
        gate = GoalieConfirmationGate()
        result = gate.check(confirmed_goalie)
        
        assert result.passes is True
        assert "CONFIRMED" in result.message
    
    def test_unconfirmed_goalie_fails(self, unconfirmed_goalie):
        """Unconfirmed goalie must fail gate."""
        gate = GoalieConfirmationGate()
        result = gate.check(unconfirmed_goalie)
        
        assert result.passes is False
        assert "NOT_CONFIRMED" in result.message or "ABORT" in result.message
    
    def test_single_source_fails(self, single_source_goalie):
        """Single source confirmation must fail (need ≥2)."""
        gate = GoalieConfirmationGate()
        result = gate.check(single_source_goalie)
        
        assert result.passes is False
        assert len(single_source_goalie.sources) < 2
    
    def test_both_goalies_must_be_confirmed(self, confirmed_goalie, unconfirmed_goalie):
        """Both home and away goalies must be confirmed."""
        with pytest.raises(RuntimeError, match="GOALIE_NOT_CONFIRMED|ABORT"):
            confirm_both_goalies(confirmed_goalie, unconfirmed_goalie)


# ─────────────────────────────────────────────────────────
# GATE 2: LOW STARTS CAP (< 5 starts → 58% max)
# ─────────────────────────────────────────────────────────

class TestLowStartsCap:
    """Tests for low-starts probability cap."""
    
    def test_low_starts_cap_applied(self, low_start_goalie):
        """Goalie with <5 starts must have probability capped at 58%."""
        base_prob = 0.65
        adjusted = apply_goalie_adjustments(base_prob, low_start_goalie)
        
        assert adjusted <= 0.58
    
    def test_adequate_starts_no_cap(self, confirmed_goalie):
        """Goalie with ≥5 starts should not be capped."""
        base_prob = 0.65
        adjusted = apply_goalie_adjustments(base_prob, confirmed_goalie)
        
        # Should not be capped at 58%
        assert adjusted > 0.58 or confirmed_goalie.is_b2b


# ─────────────────────────────────────────────────────────
# GATE 3: B2B PENALTY (-4%)
# ─────────────────────────────────────────────────────────

class TestB2BPenalty:
    """Tests for back-to-back penalty."""
    
    def test_b2b_penalty_applied(self, b2b_goalie):
        """B2B goalie must have -4% penalty applied."""
        base_prob = 0.65
        adjusted = apply_goalie_adjustments(base_prob, b2b_goalie)
        
        # 0.65 - 0.04 = 0.61
        assert adjusted == pytest.approx(0.61, abs=0.001)
    
    def test_no_b2b_no_penalty(self, confirmed_goalie):
        """Non-B2B goalie should not have penalty."""
        base_prob = 0.65
        adjusted = apply_goalie_adjustments(base_prob, confirmed_goalie)
        
        # Should remain at base prob (no B2B penalty)
        assert adjusted == pytest.approx(0.65, abs=0.001)
    
    def test_b2b_and_low_starts_stack(self, low_start_goalie):
        """B2B and low starts penalties should stack."""
        low_start_goalie.is_b2b = True
        base_prob = 0.65
        adjusted = apply_goalie_adjustments(base_prob, low_start_goalie)
        
        # Should hit the 58% cap from low starts (B2B would make it lower but cap applies)
        assert adjusted <= 0.58


# ─────────────────────────────────────────────────────────
# GATE 4: UNKNOWN GOALIE = ABORT
# ─────────────────────────────────────────────────────────

class TestUnknownGoalieAbort:
    """Tests for unknown goalie abort behavior."""
    
    def test_unknown_goalie_raises(self, unconfirmed_goalie):
        """Unknown goalie must raise RuntimeError."""
        gate = GoalieConfirmationGate()
        result = gate.check(unconfirmed_goalie)
        
        assert result.passes is False
        
        # If used in pipeline, should abort
        if not result.passes:
            with pytest.raises(RuntimeError):
                gate.enforce(unconfirmed_goalie)
    
    def test_pipeline_aborts_on_unknown(self):
        """Full pipeline must abort if goalie unknown."""
        # This tests the integration behavior
        from sports.nhl.goalies.confirmation_gate import GoalieConfirmationGate
        
        gate = GoalieConfirmationGate()
        unknown = GoalieStatus(
            name="Unknown",
            team="BOS",
            confirmed=False,
            sources=[],
            starts_last_30=0,
            is_b2b=False,
        )
        
        with pytest.raises(RuntimeError, match="GOALIE|ABORT|CONFIRM"):
            gate.enforce(unknown)


# ─────────────────────────────────────────────────────────
# INTEGRATION TESTS
# ─────────────────────────────────────────────────────────

class TestGoalieGateIntegration:
    """Integration tests for full goalie gate flow."""
    
    def test_full_gate_flow_passes(self, confirmed_goalie):
        """Complete gate flow with confirmed goalie."""
        gate = GoalieConfirmationGate()
        
        # Check passes
        result = gate.check(confirmed_goalie)
        assert result.passes is True
        
        # Enforce doesn't raise
        gate.enforce(confirmed_goalie)  # Should not raise
        
        # Adjustments applied correctly
        prob = apply_goalie_adjustments(0.65, confirmed_goalie)
        assert 0.58 <= prob <= 0.69  # Within valid range
    
    def test_full_gate_flow_fails_appropriately(self, unconfirmed_goalie):
        """Complete gate flow rejects unconfirmed goalie."""
        gate = GoalieConfirmationGate()
        
        # Check fails
        result = gate.check(unconfirmed_goalie)
        assert result.passes is False
        
        # Enforce raises
        with pytest.raises(RuntimeError):
            gate.enforce(unconfirmed_goalie)


# ─────────────────────────────────────────────────────────
# ASSERTION SUMMARY
# ─────────────────────────────────────────────────────────

def test_all_gate_invariants():
    """
    Master assertion test - validates all gate invariants.
    
    MUST PASS:
    1. Goalie confirmed (≥2 sources) → else ABORT
    2. <5 starts → cap 58%
    3. B2B → -4%
    4. Unknown goalie → ABORT
    """
    # Create test cases
    confirmed = GoalieStatus(
        name="Test", team="TST", confirmed=True,
        sources=["src1", "src2"], starts_last_30=10, is_b2b=False
    )
    
    unconfirmed = GoalieStatus(
        name="Test", team="TST", confirmed=False,
        sources=[], starts_last_30=0, is_b2b=False
    )
    
    low_starts = GoalieStatus(
        name="Test", team="TST", confirmed=True,
        sources=["src1", "src2"], starts_last_30=3, is_b2b=False
    )
    
    b2b = GoalieStatus(
        name="Test", team="TST", confirmed=True,
        sources=["src1", "src2"], starts_last_30=10, is_b2b=True
    )
    
    gate = GoalieConfirmationGate()
    
    # INVARIANT 1: Confirmed passes, unconfirmed fails
    assert gate.check(confirmed).passes is True
    assert gate.check(unconfirmed).passes is False
    
    # INVARIANT 2: Low starts capped
    prob = apply_goalie_adjustments(0.70, low_starts)
    assert prob <= 0.58
    
    # INVARIANT 3: B2B penalty
    prob_b2b = apply_goalie_adjustments(0.65, b2b)
    prob_normal = apply_goalie_adjustments(0.65, confirmed)
    assert prob_b2b < prob_normal
    assert prob_b2b == pytest.approx(0.61, abs=0.01)
    
    # INVARIANT 4: Unknown raises
    with pytest.raises(RuntimeError):
        gate.enforce(unconfirmed)
    
    print("✅ All goalie gate invariants PASSED")


# ─────────────────────────────────────────────────────────
# RUN TESTS
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
