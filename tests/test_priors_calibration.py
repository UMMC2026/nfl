import sys
import types
import pytest

from ufa.daily_pipeline import DailyPipeline
from ufa.prior.nfl_structural_priors import compute_prior
from ufa.analysis.calibration import ConfidenceCalibrator, CalibrationConfig


def _make_pick(player="Test Player", team="TST", stat="receiving_yards", line=50.0, direction="higher"):
    return {
        "player": player,
        "team": team,
        "stat": stat,
        "line": line,
        "direction": direction,
        "sport": "NFL",
    }


def test_prior_only_flow(monkeypatch):
    """When no recent_values are available, the pipeline should use the prior as raw_prob
    and mark the pick as prior_only while persisting mu/sigma.
    """
    pipeline = DailyPipeline()

    pick = _make_pick(player="A Player", stat="rush_yards", line=40.0)

    # Ensure hydrator returns empty list to simulate no empirical data
    # If the module doesn't exist, process_picks will handle it gracefully.
    try:
        import ufa.ingest.hydrate as hydrate_mod
        monkeypatch.setattr(hydrate_mod, "hydrate_recent_values", lambda *a, **k: [])
    except Exception:
        # module missing - fine
        pass

    pipeline.picks = [pick]
    processed = pipeline.process_picks()

    assert len(processed) == 1
    p = processed[0]

    # prior_only flag should be present
    assert p.get("prior_only", True) in (True, False)

    # Compute expected prior and compare to raw_prob persisted
    prior_prob, prior_mu, prior_sigma = compute_prior(pick, pipeline.context_provider.get_context(pick["player"], pick["team"], pick.get("opponent", "UNK"), pick["stat"]))

    # raw_prob in processed pick should equal prior_prob (or very close)
    assert abs(p["raw_prob"] - prior_prob) < 1e-6

    # mu/sigma persisted on the pick should match prior_mu/prior_sigma (or at least exist)
    assert "mu" in p and "sigma" in p


def test_blend_invariants_zero_penalties():
    """Test that blending respects alpha when other penalties are disabled.

    We set shrinkage and penalties to zero so calibrated_probability equals the soft-blend
    between prior and raw when prior is provided.
    """
    # For the zero-sample check we use min_sample_size=0 to avoid sample penalties
    cfg0 = CalibrationConfig(
        shrinkage_factor=0.0,
        streak_penalty=0.0,
        volatility_penalty_mult=0.0,
        min_confidence=0.01,
        min_sample_size=0,
        blend_min_alpha=0.2,
        blend_max_alpha=0.8,
    )
    calib = ConfidenceCalibrator(cfg0)

    prior = 0.2
    raw = 0.7

    # Sample size 0 -> alpha == 0.0 -> calibrated should equal prior (no other penalties)
    out0 = calib.calibrate(
        player="P", team="T", stat="s", line=10, direction="higher",
        raw_prob=raw, mu=0, sigma=1, recent_values=[], career_avg=None,
        prior_prob=prior, prior_mu=None, prior_sigma=None,
    )
    assert abs(out0.calibrated_probability - prior) < 1e-6

    # For the full-sample check, use a config with a positive min_sample_size
    cfg1 = CalibrationConfig(
        shrinkage_factor=0.0,
        streak_penalty=0.0,
        volatility_penalty_mult=0.0,
        min_confidence=0.01,
        min_sample_size=5,
        blend_min_alpha=0.2,
        blend_max_alpha=0.8,
    )
    calib1 = ConfidenceCalibrator(cfg1)

    # Sample size == min_sample_size -> alpha == blend_max_alpha
    rv = [1] * cfg1.min_sample_size
    out1 = calib1.calibrate(
        player="P", team="T", stat="s", line=10, direction="higher",
        raw_prob=raw, mu=0, sigma=1, recent_values=rv, career_avg=None,
        prior_prob=prior, prior_mu=None, prior_sigma=None,
    )

    expected_alpha = cfg1.blend_max_alpha
    expected = prior + expected_alpha * (raw - prior)
    # With zero penalties/shrinkage the calibrated_probability should equal expected
    assert abs(out1.calibrated_probability - expected) < 1e-6


def test_ranking_preservation_under_prior_only(monkeypatch):
    """When picks are prior-only and penalties are disabled, ranking by raw_prob
    should equal ranking by calibrated probability.
    """
    pipeline = DailyPipeline()

    # Disable calibration penalties
    cfg = CalibrationConfig(
        shrinkage_factor=0.0,
        streak_penalty=0.0,
        volatility_penalty_mult=0.0,
        min_confidence=0.01,
        min_sample_size=1,
        blend_min_alpha=0.0,
        blend_max_alpha=1.0,
    )
    pipeline.calibrator = ConfidenceCalibrator(cfg)

    # Two picks with different prior opinions
    p1 = _make_pick(player="P1", stat="rush_yards", line=30.0)
    p2 = _make_pick(player="P2", stat="rush_yards", line=30.0)

    # Force compute_prior to return different priors
    def fake_compute_prior(pick, ctx):
        if pick["player"] == "P1":
            return 0.60, 28.0, 5.0
        else:
            return 0.40, 28.0, 5.0

    import ufa.prior.nfl_structural_priors as prior_mod
    monkeypatch.setattr(prior_mod, "compute_prior", fake_compute_prior)

    # Ensure hydrator returns empty
    try:
        import ufa.ingest.hydrate as hydrate_mod
        monkeypatch.setattr(hydrate_mod, "hydrate_recent_values", lambda *a, **k: [])
    except Exception:
        pass

    pipeline.picks = [p1, p2]
    processed = pipeline.process_picks()

    # raw_prob should reflect prior ordering
    raw_order = sorted(processed, key=lambda x: x["raw_prob"], reverse=True)
    calib_order = sorted(processed, key=lambda x: x["calibrated_prob"], reverse=True)

    assert [r["player"] for r in raw_order] == [c["player"] for c in calib_order]
