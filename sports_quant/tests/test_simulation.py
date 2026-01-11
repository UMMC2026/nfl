from sports_quant.simulation.monte_carlo import run_monte_carlo


def test_basic_sim():
    out = run_monte_carlo(line=44.5, mean=50.0, variance=100.0, dist="normal", n_sims=5000)
    assert 0.0 <= out["p_over"] <= 1.0
    assert out["tail_risk"]["p05"] < out["tail_risk"]["p95"]
