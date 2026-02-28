import math

from quant_modules.monte_carlo_optimizer import MonteCarloOptimizer, Pick


def test_exact_power_2leg_ev_matches_closed_form():
    # For 2-leg power: payout=3.0 if 2/2 hit, else 0.0. Net = payout - 1.
    # With p1=p2=0.5: P(2 hits)=0.25 => EV = (3-1)*0.25 + (0-1)*0.75 = 2*0.25 - 0.75 = -0.25
    optimizer = MonteCarloOptimizer(method="exact")
    picks = [
        Pick(player="A", stat="pts", line=10.0, direction="higher", p_hit=0.5, team="X"),
        Pick(player="B", stat="reb", line=5.0, direction="higher", p_hit=0.5, team="Y"),
    ]
    res = optimizer.simulate_entry(picks, entry_type="power")
    assert math.isclose(res.ev, -0.25, abs_tol=1e-12)
    assert res.n_sims == 0


def test_exact_flex_3leg_all_certain_profit():
    optimizer = MonteCarloOptimizer(method="exact")
    picks = [
        Pick(player="A", stat="pts", line=10.0, direction="higher", p_hit=1.0, team="X"),
        Pick(player="B", stat="reb", line=5.0, direction="higher", p_hit=1.0, team="Y"),
        Pick(player="C", stat="ast", line=7.0, direction="higher", p_hit=1.0, team="Z"),
    ]
    res = optimizer.simulate_entry(picks, entry_type="flex")
    # Flex 3: payout 2.25 at 3 hits => net +1.25
    assert math.isclose(res.ev, 1.25, abs_tol=1e-12)
    assert math.isclose(res.prob_profit, 1.0, abs_tol=1e-12)
    assert math.isclose(res.mean_hits, 3.0, abs_tol=1e-12)


def test_exact_respects_same_game_correlation_penalty_floor():
    optimizer = MonteCarloOptimizer(method="exact")
    # Same team/game, so penalty will reduce p_hit but should be clamped within [0.01, 0.99]
    picks = [
        Pick(player="A", stat="pts", line=10.0, direction="higher", p_hit=0.02, team="X"),
        Pick(player="B", stat="reb", line=5.0, direction="higher", p_hit=0.02, team="X"),
    ]
    res = optimizer.simulate_entry(picks, entry_type="power", correlation_penalty=0.5)
    # Ensure it runs and produces a valid EV (not NaN)
    assert not math.isnan(res.ev)
