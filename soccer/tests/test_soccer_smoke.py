"""Minimal smoke tests for soccer module.

These are lightweight sanity checks (not a full calibration suite).
"""

from soccer.models.dr_soccer_bayes import estimate_match_lambdas
from soccer.sim.soccer_sim import scoreline_distribution, derived_market_probs


def test_lambda_estimation_positive():
    lambdas = estimate_match_lambdas(
        home_xg_for=1.5,
        home_xg_against=1.1,
        away_xg_for=1.2,
        away_xg_against=1.0,
        home_matches=20,
        away_matches=20,
        home_adv_mult=1.12,
    )
    assert lambdas["home"].lam > 0
    assert lambdas["away"].lam > 0


def test_distribution_sums_to_one():
    dist = scoreline_distribution(1.4, 1.1, max_goals=8)
    total = sum(dist.values())
    assert abs(total - 1.0) < 1e-6


def test_derived_probs_reasonable():
    dist = scoreline_distribution(1.4, 1.1, max_goals=8)
    probs = derived_market_probs(dist)
    assert 0.0 <= probs["draw"] <= 1.0
    assert abs(probs["home_win"] + probs["draw"] + probs["away_win"] - 1.0) < 1e-6
