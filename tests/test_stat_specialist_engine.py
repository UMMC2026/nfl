# tests/test_stat_specialist_engine.py
"""
Unit tests for stat_specialist_engine.py (production lock-in v1.0)

Tests:
1. Classifier rules (feature-driven)
2. Confidence caps by specialist
3. Rejection rules (eligibility)
4. FLEX ban and max legs constraints
"""
import pytest
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.stat_specialist_engine import (
    StatSpecialist,
    SPECIALIST_CONFIDENCE_CAP,
    SPECIALIST_CONFIDENCE_CAP_PCT,
    VOLATILITY_DAMPENED_SPECIALISTS,
    FLEX_BANNED_SPECIALISTS,
    SPECIALIST_MAX_LEGS,
    classify_stat_specialist,
    apply_specialist_confidence_cap,
    get_matchup_delta_weight,
    is_flex_banned,
    get_max_legs,
    should_reject_pick,
    enrich_pick_with_specialist,
    apply_specialist_governance_to_pick,
)


# =============================================================================
# CLASSIFIER TESTS
# =============================================================================

class TestClassifier:
    """Test classify_stat_specialist() feature-driven rules."""

    def test_catch_and_shoot_3pm(self):
        """High assisted_3pa, low dribbles, low pullup = C&S."""
        player = {
            "assisted_3pa_rate": 0.72,
            "dribbles_per_shot": 0.8,
            "pullup_3pa_rate": 0.12,
        }
        result = classify_stat_specialist(player, "3PM")
        assert result == StatSpecialist.CATCH_AND_SHOOT_3PM

    def test_big_man_3pm(self):
        """C/PF with high 3PA and pick-and-pop = Big Man 3PM."""
        player = {
            "position": "C",
            "avg_3pa": 3.5,
            "pick_and_pop_rate": 0.30,
        }
        result = classify_stat_specialist(player, "3PM")
        assert result == StatSpecialist.BIG_MAN_3PM

    def test_off_dribble_scorer_3pm(self):
        """High pullup rate on 3PM = off-dribble."""
        player = {
            "pullup_3pa_rate": 0.50,
        }
        result = classify_stat_specialist(player, "3PM")
        assert result == StatSpecialist.OFF_DRIBBLE_SCORER

    def test_midrange_specialist(self):
        """High midrange FGA rate, low rim rate = midrange specialist."""
        player = {
            "midrange_fga_rate": 0.40,
            "rim_fga_rate": 0.20,
        }
        result = classify_stat_specialist(player, "PTS")
        assert result == StatSpecialist.MIDRANGE_SPECIALIST

    def test_big_post_scorer(self):
        """High post touch + paint FGA = big post scorer."""
        player = {
            "post_touch_rate": 0.30,
            "paint_fga_rate": 0.50,
        }
        result = classify_stat_specialist(player, "PTS")
        assert result == StatSpecialist.BIG_POST_SCORER

    def test_rim_runner(self):
        """High assisted FG rate, close shot distance = rim runner."""
        player = {
            "assisted_fg_rate": 0.80,
            "avg_shot_distance": 4.0,
        }
        result = classify_stat_specialist(player, "REB")
        assert result == StatSpecialist.RIM_RUNNER

    def test_pass_first_creator(self):
        """High time of possession, low usage = pass-first."""
        player = {
            "time_of_possession": 6.0,
            "team_top_80_pct_touches": 5.0,
            "usage_rate": 0.20,
            "scorer_usage_threshold": 0.28,
        }
        result = classify_stat_specialist(player, "AST")
        assert result == StatSpecialist.PASS_FIRST_CREATOR

    def test_bench_microwave(self):
        """High bench minutes rate + high usage volatility = microwave."""
        player = {
            "bench_minutes_rate": 0.85,
            "usage_volatility": 0.80,
        }
        # Bench microwave is stat-agnostic
        result = classify_stat_specialist(player, "PTS")
        assert result == StatSpecialist.BENCH_MICROWAVE

    def test_generic_fallback(self):
        """No features = GENERIC."""
        player = {}
        result = classify_stat_specialist(player, "PTS")
        assert result == StatSpecialist.GENERIC

    def test_stat_alias_normalization(self):
        """Stat aliases should be normalized."""
        player = {"assisted_3pa_rate": 0.72, "dribbles_per_shot": 0.8, "pullup_3pa_rate": 0.12}
        # Test various 3PM aliases
        for stat in ["3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"]:
            result = classify_stat_specialist(player, stat)
            assert result == StatSpecialist.CATCH_AND_SHOOT_3PM


# =============================================================================
# CONFIDENCE CAP TESTS
# =============================================================================

class TestConfidenceCaps:
    """Test apply_specialist_confidence_cap()."""

    def test_cap_values_correct(self):
        """Verify cap table matches production lock-in."""
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.CATCH_AND_SHOOT_3PM] == 0.70
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.BIG_MAN_3PM] == 0.62
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.MIDRANGE_SPECIALIST] == 0.60
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.BIG_POST_SCORER] == 0.63
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.RIM_RUNNER] == 0.65
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.PASS_FIRST_CREATOR] == 0.68
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.OFF_DRIBBLE_SCORER] == 0.58
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.BENCH_MICROWAVE] == 0.55
        assert SPECIALIST_CONFIDENCE_CAP[StatSpecialist.GENERIC] == 0.65

    def test_big_man_3pm_cap(self):
        """BIG_MAN_3PM should cap at 62%."""
        conf, meta = apply_specialist_confidence_cap(0.80, StatSpecialist.BIG_MAN_3PM)
        assert conf <= 0.62
        assert meta["cap_applied"] is True

    def test_catch_and_shoot_cap(self):
        """CATCH_AND_SHOOT_3PM should cap at 70%."""
        conf, meta = apply_specialist_confidence_cap(0.85, StatSpecialist.CATCH_AND_SHOOT_3PM)
        assert conf <= 0.70
        assert meta["cap_applied"] is True

    def test_no_increase_on_cap(self):
        """Cap should never INCREASE confidence."""
        conf, meta = apply_specialist_confidence_cap(0.50, StatSpecialist.CATCH_AND_SHOOT_3PM)
        assert conf == 0.50
        assert meta["cap_applied"] is False

    def test_volatility_dampening_off_dribble(self):
        """OFF_DRIBBLE_SCORER gets 0.95 multiplier after cap."""
        conf, meta = apply_specialist_confidence_cap(0.60, StatSpecialist.OFF_DRIBBLE_SCORER)
        # Cap is 0.58, then * 0.95 = 0.551
        assert conf == pytest.approx(0.58 * 0.95, rel=1e-3)
        assert meta["volatility_dampened"] is True

    def test_volatility_dampening_bench_microwave(self):
        """BENCH_MICROWAVE gets 0.95 multiplier after cap."""
        conf, meta = apply_specialist_confidence_cap(0.60, StatSpecialist.BENCH_MICROWAVE)
        # Cap is 0.55, then * 0.95 = 0.5225
        assert conf == pytest.approx(0.55 * 0.95, rel=1e-3)
        assert meta["volatility_dampened"] is True

    def test_percent_scale(self):
        """Percent scale (0-100) should work correctly."""
        conf, meta = apply_specialist_confidence_cap(80.0, StatSpecialist.BIG_MAN_3PM, use_percent_scale=True)
        assert conf <= 62.0
        assert meta["ceiling"] == 62.0


# =============================================================================
# REJECTION RULES TESTS
# =============================================================================

class TestRejectionRules:
    """Test should_reject_pick()."""

    def test_bench_microwave_pts_rejected(self):
        """BENCH_MICROWAVE on PTS should be rejected."""
        reject, reason = should_reject_pick(StatSpecialist.BENCH_MICROWAVE, "PTS", 15.5, 0.60)
        assert reject is True
        assert "BENCH_MICROWAVE" in reason

    def test_bench_microwave_3pm_rejected(self):
        """BENCH_MICROWAVE on 3PM should be rejected."""
        reject, reason = should_reject_pick(StatSpecialist.BENCH_MICROWAVE, "3PM", 2.5, 0.60)
        assert reject is True
        assert "BENCH_MICROWAVE" in reason

    def test_bench_microwave_reb_allowed(self):
        """BENCH_MICROWAVE on REB should NOT be rejected."""
        reject, reason = should_reject_pick(StatSpecialist.BENCH_MICROWAVE, "REB", 5.5, 0.60)
        assert reject is False

    def test_off_dribble_low_confidence_rejected(self):
        """OFF_DRIBBLE_SCORER < 58% should be rejected."""
        reject, reason = should_reject_pick(StatSpecialist.OFF_DRIBBLE_SCORER, "PTS", 20.5, 0.55)
        assert reject is True
        assert "OFF_DRIBBLE" in reason

    def test_off_dribble_high_confidence_allowed(self):
        """OFF_DRIBBLE_SCORER >= 58% should be allowed."""
        reject, reason = should_reject_pick(StatSpecialist.OFF_DRIBBLE_SCORER, "PTS", 20.5, 0.60)
        assert reject is False

    def test_big_man_3pm_high_line_rejected(self):
        """BIG_MAN_3PM at line >= 3.5 should be rejected."""
        reject, reason = should_reject_pick(StatSpecialist.BIG_MAN_3PM, "3PM", 3.5, 0.60)
        assert reject is True
        assert "BIG_MAN_3PM" in reason

    def test_big_man_3pm_low_line_allowed(self):
        """BIG_MAN_3PM at line < 3.5 should be allowed."""
        reject, reason = should_reject_pick(StatSpecialist.BIG_MAN_3PM, "3PM", 2.5, 0.60)
        assert reject is False

    def test_generic_always_allowed(self):
        """GENERIC specialist should never trigger rejection."""
        reject, reason = should_reject_pick(StatSpecialist.GENERIC, "PTS", 20.5, 0.60)
        assert reject is False


# =============================================================================
# FLEX BAN AND MAX LEGS TESTS
# =============================================================================

class TestFlexBanAndMaxLegs:
    """Test FLEX ban and max legs constraints."""

    def test_flex_banned_specialists(self):
        """BENCH_MICROWAVE and OFF_DRIBBLE_SCORER are FLEX banned."""
        assert is_flex_banned(StatSpecialist.BENCH_MICROWAVE) is True
        assert is_flex_banned(StatSpecialist.OFF_DRIBBLE_SCORER) is True

    def test_flex_allowed_specialists(self):
        """Other specialists are NOT FLEX banned."""
        assert is_flex_banned(StatSpecialist.CATCH_AND_SHOOT_3PM) is False
        assert is_flex_banned(StatSpecialist.BIG_MAN_3PM) is False
        assert is_flex_banned(StatSpecialist.GENERIC) is False

    def test_big_man_3pm_max_legs(self):
        """BIG_MAN_3PM has max 2 legs."""
        assert get_max_legs(StatSpecialist.BIG_MAN_3PM) == 2

    def test_generic_no_max_legs(self):
        """GENERIC has no max legs constraint."""
        assert get_max_legs(StatSpecialist.GENERIC) is None

    def test_catch_and_shoot_no_max_legs(self):
        """CATCH_AND_SHOOT_3PM has no max legs constraint."""
        assert get_max_legs(StatSpecialist.CATCH_AND_SHOOT_3PM) is None


# =============================================================================
# MATCHUP DELTA WEIGHT TESTS
# =============================================================================

class TestMatchupDeltaWeight:
    """Test get_matchup_delta_weight()."""

    def test_3pm_specialist_upweight(self):
        """3PM + 3PM specialist = 1.25 weight."""
        weight = get_matchup_delta_weight("3PM", StatSpecialist.CATCH_AND_SHOOT_3PM)
        assert weight == 1.25
        
        weight = get_matchup_delta_weight("3PM", StatSpecialist.BIG_MAN_3PM)
        assert weight == 1.25

    def test_non_3pm_dampen(self):
        """Non-3PM specialist = 0.85 weight."""
        weight = get_matchup_delta_weight("3PM", StatSpecialist.GENERIC)
        assert weight == 0.85

    def test_non_3pm_stat_dampen(self):
        """Non-3PM stat = 0.85 weight."""
        weight = get_matchup_delta_weight("PTS", StatSpecialist.CATCH_AND_SHOOT_3PM)
        assert weight == 0.85


# =============================================================================
# INTEGRATION HELPER TESTS
# =============================================================================

class TestIntegrationHelpers:
    """Test convenience/integration functions."""

    def test_enrich_pick_with_specialist(self):
        """enrich_pick_with_specialist() adds specialist field."""
        pick = {
            "player": "Test Player",
            "stat": "3PM",
            "assisted_3pa_rate": 0.72,
            "dribbles_per_shot": 0.8,
            "pullup_3pa_rate": 0.12,
        }
        result = enrich_pick_with_specialist(pick)
        assert result["stat_specialist"] == "CATCH_AND_SHOOT_3PM"
        assert result["stat_specialist_type"] == "CATCH_AND_SHOOT_3PM"

    def test_apply_specialist_governance_to_pick(self):
        """apply_specialist_governance_to_pick() caps and checks rejection."""
        pick = {
            "player": "Test Player",
            "stat": "3PM",
            "line": 2.5,
            "confidence": 0.80,
            "assisted_3pa_rate": 0.72,
            "dribbles_per_shot": 0.8,
            "pullup_3pa_rate": 0.12,
        }
        result = apply_specialist_governance_to_pick(pick)
        assert result["stat_specialist"] == "CATCH_AND_SHOOT_3PM"
        assert result["confidence"] <= 0.70  # Capped
        assert "specialist_rejected" not in result or result["specialist_rejected"] is False


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_missing_features_graceful(self):
        """Missing features should not crash."""
        player = {}
        result = classify_stat_specialist(player, "PTS")
        assert result == StatSpecialist.GENERIC

    def test_none_stat_graceful(self):
        """None stat should not crash."""
        player = {}
        result = classify_stat_specialist(player, None)
        assert result == StatSpecialist.GENERIC

    def test_empty_stat_graceful(self):
        """Empty stat should not crash."""
        player = {}
        result = classify_stat_specialist(player, "")
        assert result == StatSpecialist.GENERIC

    def test_confidence_zero(self):
        """Zero confidence should work."""
        conf, meta = apply_specialist_confidence_cap(0.0, StatSpecialist.GENERIC)
        assert conf == 0.0

    def test_confidence_negative_graceful(self):
        """Negative confidence should be handled."""
        conf, meta = apply_specialist_confidence_cap(-0.5, StatSpecialist.GENERIC)
        assert conf == -0.5  # No cap since it's below any ceiling


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
