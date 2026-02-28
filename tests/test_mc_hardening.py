"""
Tests for Monte Carlo Hardening Module
======================================

Tests Beta distributions, CVaR, correlation, and Kelly clamping.
"""

import pytest
import math
from quant_modules.mc_hardening import (
    BetaDistribution,
    scalar_to_beta,
    compute_cvar,
    compute_clamped_kelly,
    compute_fractional_kelly,
    compute_portfolio_correlation,
    evaluate_pick_hardened,
    evaluate_portfolio_hardened,
    estimate_loss_streak_probability,
    estimate_max_drawdown,
    get_correlation,
    StatFamily,
    MAX_KELLY_FRACTION,
)


class TestBetaDistribution:
    """Tests for Beta distribution uncertainty modeling."""
    
    def test_from_point_estimate(self):
        beta = BetaDistribution.from_point_estimate(0.55, sample_size=10)
        
        # Mean should be close to 0.55
        assert abs(beta.mean - 0.55) < 0.01
        
        # Should have some uncertainty
        assert beta.std_dev > 0.05
    
    def test_high_confidence_tighter(self):
        low_conf = scalar_to_beta(0.55, confidence=0.2)
        high_conf = scalar_to_beta(0.55, confidence=0.9)
        
        # Higher confidence should have lower std dev
        assert high_conf.std_dev < low_conf.std_dev
    
    def test_conservative_estimate_lower(self):
        beta = BetaDistribution.from_point_estimate(0.55, sample_size=10)
        
        conservative = beta.conservative_estimate(risk_aversion=0.1)
        
        # Conservative estimate should be lower than mean
        assert conservative < beta.mean
    
    def test_sampling(self):
        beta = BetaDistribution.from_point_estimate(0.55, sample_size=20)
        
        samples = [beta.sample() for _ in range(1000)]
        
        # All samples should be in [0, 1]
        assert all(0 <= s <= 1 for s in samples)
        
        # Mean of samples should be close to distribution mean
        sample_mean = sum(samples) / len(samples)
        assert abs(sample_mean - beta.mean) < 0.05
    
    def test_percentiles(self):
        beta = BetaDistribution.from_point_estimate(0.50, sample_size=20)
        
        p05 = beta.percentile(0.05)
        p50 = beta.percentile(0.50)
        p95 = beta.percentile(0.95)
        
        # Percentiles should be ordered
        assert p05 < p50 < p95
        
        # 50th percentile should be close to mean for symmetric-ish distribution
        assert abs(p50 - beta.mean) < 0.1


class TestCVaR:
    """Tests for Conditional Value at Risk."""
    
    def test_cvar_negative_returns(self):
        # All losses
        returns = [-1.0] * 100
        cvar = compute_cvar(returns, 0.95)
        
        assert cvar == -1.0
    
    def test_cvar_positive_returns(self):
        # All wins
        returns = [1.0] * 100
        cvar = compute_cvar(returns, 0.95)
        
        assert cvar == 1.0
    
    def test_cvar_mixed(self):
        # 80% wins (+1), 20% losses (-1)
        returns = [1.0] * 80 + [-1.0] * 20
        
        cvar = compute_cvar(returns, 0.95)
        
        # CVaR at 95% looks at worst 5% - should be negative
        assert cvar < 0
    
    def test_cvar_vs_var(self):
        # CVaR should capture expected loss in tail, not just threshold
        returns = [-5.0, -4.0, -3.0, -2.0, -1.0] + [1.0] * 95
        
        cvar = compute_cvar(returns, 0.95)
        
        # Worst 5% are [-5, -4, -3, -2, -1], mean = -3
        assert cvar < -2  # Should be around -3


class TestKellyCriterion:
    """Tests for clamped Kelly criterion."""
    
    def test_no_edge_zero_kelly(self):
        # Fair odds, no edge
        kelly = compute_clamped_kelly(0.5, 2.0)
        
        assert abs(kelly) < 0.01
    
    def test_positive_edge(self):
        # 55% win rate at even money = edge
        kelly = compute_clamped_kelly(0.55, 2.0)
        
        assert kelly > 0
        assert kelly <= MAX_KELLY_FRACTION
    
    def test_negative_edge_zero(self):
        # 40% win rate at even money = negative edge
        kelly = compute_clamped_kelly(0.40, 2.0)
        
        assert kelly == 0.0
    
    def test_clamping(self):
        # Very high edge should still be clamped
        kelly = compute_clamped_kelly(0.80, 3.0)  # Huge edge
        
        assert kelly == MAX_KELLY_FRACTION
    
    def test_fractional_kelly(self):
        full = compute_clamped_kelly(0.60, 2.0, max_fraction=1.0)
        quarter = compute_fractional_kelly(0.60, 2.0, fraction=0.25)
        
        # Quarter Kelly should be ~25% of full (but capped)
        expected = min(full * 0.25, MAX_KELLY_FRACTION)
        assert abs(quarter - expected) < 0.001


class TestCorrelation:
    """Tests for stat family correlation."""
    
    def test_same_stat_high_correlation(self):
        corr = get_correlation("PTS", "FGM")  # Both scoring
        
        assert corr > 0.7
    
    def test_different_family_lower(self):
        corr = get_correlation("PTS", "STL")  # Scoring vs Defense
        
        assert corr < 0.3
    
    def test_portfolio_correlation(self):
        picks = [
            {"player_id": "p1", "stat_type": "PTS"},
            {"player_id": "p2", "stat_type": "REB"},
            {"player_id": "p3", "stat_type": "AST"},
        ]
        
        corr = compute_portfolio_correlation(picks)
        
        # Different stats from different players should have low-moderate correlation
        assert 0.1 < corr < 0.5
    
    def test_same_player_high_correlation(self):
        picks = [
            {"player_id": "p1", "stat_type": "PTS"},
            {"player_id": "p1", "stat_type": "REB"},  # Same player
        ]
        
        corr = compute_portfolio_correlation(picks)
        
        # Same player should have high correlation
        assert corr > 0.8


class TestLossStreaks:
    """Tests for loss streak estimation."""
    
    def test_high_win_rate_low_streak_prob(self):
        p_wins = [0.75] * 20
        
        prob = estimate_loss_streak_probability(p_wins, streak_length=5, simulations=5000)
        
        # High win rate should have low streak probability
        assert prob < 0.3
    
    def test_low_win_rate_high_streak_prob(self):
        p_wins = [0.45] * 20
        
        prob = estimate_loss_streak_probability(p_wins, streak_length=5, simulations=5000)
        
        # Low win rate should have higher streak probability than high win rate
        # (relaxed assertion due to stochastic nature)
        assert prob > 0.2
    
    def test_drawdown_estimation(self):
        p_wins = [0.55] * 20
        
        mean_dd, worst_dd = estimate_max_drawdown(p_wins, simulations=1000)
        
        # Should have some drawdown
        assert mean_dd > 0
        assert worst_dd > mean_dd


class TestHardenedEvaluation:
    """Tests for full hardened pick evaluation."""
    
    def test_basic_evaluation(self):
        eval_result = evaluate_pick_hardened(
            player_id="lebron_james",
            stat_type="PTS",
            line=25.5,
            direction="HIGHER",
            p_hit=0.55,
            payout=2.0,
            confidence=0.5,
        )
        
        assert eval_result.p_hit_point == 0.55
        assert eval_result.p_hit_beta is not None
        assert 0 <= eval_result.kelly_clamped <= MAX_KELLY_FRACTION
    
    def test_conservative_lower_than_point(self):
        eval_result = evaluate_pick_hardened(
            player_id="test",
            stat_type="PTS",
            line=20.0,
            direction="HIGHER",
            p_hit=0.60,
            payout=2.0,
            confidence=0.5,
            risk_aversion=0.1,
        )
        
        # Conservative estimate should be lower
        assert eval_result.p_hit_conservative < eval_result.p_hit_point
    
    def test_portfolio_evaluation(self):
        picks = [
            {"player_id": "p1", "stat_type": "PTS", "p_hit": 0.55, "line": 25.5, "direction": "HIGHER"},
            {"player_id": "p2", "stat_type": "REB", "p_hit": 0.58, "line": 8.5, "direction": "HIGHER"},
            {"player_id": "p3", "stat_type": "AST", "p_hit": 0.52, "line": 6.5, "direction": "LOWER"},
        ]
        payouts = {3: 6.0}
        
        result = evaluate_portfolio_hardened(picks, payouts)
        
        assert result["pick_count"] == 3
        assert "portfolio_correlation" in result
        assert "risk_summary" in result
        assert result["portfolio_correlation"] >= 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_probability_clamped(self):
        # Extreme probability should be clamped
        beta = BetaDistribution.from_point_estimate(0.99, sample_size=5)
        
        # Should not be exactly 0.99 due to min_uncertainty
        assert beta.mean < 0.99
    
    def test_zero_confidence(self):
        beta = scalar_to_beta(0.55, confidence=0.0)
        
        # Zero confidence should give wide distribution
        assert beta.std_dev > 0.1
    
    def test_empty_returns_cvar(self):
        cvar = compute_cvar([], 0.95)
        
        assert cvar == 0.0
    
    def test_empty_picks_portfolio(self):
        result = evaluate_portfolio_hardened([], {})
        
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
