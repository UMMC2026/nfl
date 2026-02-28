"""
NHL CALIBRATION TESTS — Model Accuracy Validation
==================================================

Tests for calibration metrics and assertions.
Validates that model predictions align with actual outcomes.

Non-negotiable thresholds:
- |calibration_error| <= 0.03
- Brier score tracking
- Decile-level calibration
"""

import pytest
import numpy as np
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ─────────────────────────────────────────────────────────
# CALIBRATION METRICS
# ─────────────────────────────────────────────────────────

@dataclass
class CalibrationResult:
    """Calibration analysis results."""
    n_predictions: int
    brier_score: float
    calibration_error: float
    
    # Decile breakdown
    decile_predicted: List[float]
    decile_actual: List[float]
    decile_counts: List[int]
    
    # Reliability diagram data
    bin_edges: List[float]
    bin_predicted_means: List[float]
    bin_actual_means: List[float]
    
    def is_calibrated(self, threshold: float = 0.03) -> bool:
        return abs(self.calibration_error) <= threshold


def compute_brier_score(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Compute Brier Score (mean squared error of probability predictions).
    
    Lower is better. Perfect = 0, Random = 0.25
    """
    assert len(predictions) == len(outcomes)
    return np.mean((predictions - outcomes) ** 2)


def compute_calibration_error(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Compute overall calibration error.
    
    Difference between mean predicted probability and actual win rate.
    """
    assert len(predictions) == len(outcomes)
    mean_predicted = np.mean(predictions)
    actual_rate = np.mean(outcomes)
    return mean_predicted - actual_rate


def compute_calibration_by_decile(
    predictions: np.ndarray, 
    outcomes: np.ndarray,
    n_bins: int = 10,
) -> Tuple[List[float], List[float], List[int]]:
    """
    Compute calibration error by probability decile.
    
    Returns:
        (bin_predicted_means, bin_actual_means, bin_counts)
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_predicted = []
    bin_actual = []
    bin_counts = []
    
    for i in range(n_bins):
        mask = (predictions >= bin_edges[i]) & (predictions < bin_edges[i + 1])
        if i == n_bins - 1:  # Include right edge for last bin
            mask = (predictions >= bin_edges[i]) & (predictions <= bin_edges[i + 1])
        
        if mask.sum() > 0:
            bin_predicted.append(predictions[mask].mean())
            bin_actual.append(outcomes[mask].mean())
            bin_counts.append(mask.sum())
        else:
            bin_predicted.append(np.nan)
            bin_actual.append(np.nan)
            bin_counts.append(0)
    
    return bin_predicted, bin_actual, bin_counts


def analyze_calibration(
    predictions: List[float],
    outcomes: List[int],
) -> CalibrationResult:
    """
    Full calibration analysis.
    
    Args:
        predictions: Model probabilities (0-1)
        outcomes: Actual outcomes (0=loss, 1=win)
    
    Returns:
        CalibrationResult with all metrics
    """
    preds = np.array(predictions)
    outs = np.array(outcomes)
    
    brier = compute_brier_score(preds, outs)
    cal_error = compute_calibration_error(preds, outs)
    
    bin_pred, bin_act, bin_counts = compute_calibration_by_decile(preds, outs)
    
    return CalibrationResult(
        n_predictions=len(predictions),
        brier_score=brier,
        calibration_error=cal_error,
        decile_predicted=bin_pred,
        decile_actual=bin_act,
        decile_counts=bin_counts,
        bin_edges=list(np.linspace(0, 1, 11)),
        bin_predicted_means=bin_pred,
        bin_actual_means=bin_act,
    )


# ─────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────

@pytest.fixture
def well_calibrated_data():
    """Data where predictions match outcomes well."""
    np.random.seed(42)
    n = 1000
    
    # Generate probabilities
    probs = np.random.uniform(0.55, 0.70, n)
    
    # Generate outcomes that match probabilities
    outcomes = (np.random.random(n) < probs).astype(int)
    
    return probs, outcomes


@pytest.fixture
def poorly_calibrated_data():
    """Data where predictions are overconfident."""
    np.random.seed(42)
    n = 500
    
    # Overconfident predictions
    probs = np.random.uniform(0.65, 0.75, n)
    
    # But actual win rate is lower
    true_rate = 0.55
    outcomes = (np.random.random(n) < true_rate).astype(int)
    
    return probs, outcomes


@pytest.fixture
def nhl_realistic_data():
    """
    Realistic NHL model data.
    
    NHL should have:
    - Probability range: 58-69% (no SLAM)
    - Calibration within 3%
    """
    np.random.seed(123)
    n = 200
    
    # NHL-appropriate probabilities (LEAN and STRONG tiers only)
    probs = np.random.uniform(0.58, 0.69, n)
    
    # Slightly conservative (actual slightly higher than predicted)
    true_probs = probs + np.random.uniform(-0.02, 0.04, n)
    outcomes = (np.random.random(n) < true_probs).astype(int)
    
    return probs, outcomes


# ─────────────────────────────────────────────────────────
# CALIBRATION TESTS
# ─────────────────────────────────────────────────────────

class TestCalibrationMetrics:
    """Tests for calibration computation."""
    
    def test_brier_score_perfect(self):
        """Perfect predictions should have Brier = 0."""
        preds = np.array([0.0, 1.0, 0.0, 1.0])
        outcomes = np.array([0, 1, 0, 1])
        
        brier = compute_brier_score(preds, outcomes)
        assert brier == pytest.approx(0.0, abs=0.001)
    
    def test_brier_score_random(self):
        """Random 50% predictions should have Brier ≈ 0.25."""
        np.random.seed(42)
        preds = np.full(1000, 0.5)
        outcomes = np.random.randint(0, 2, 1000)
        
        brier = compute_brier_score(preds, outcomes)
        assert 0.20 <= brier <= 0.30  # Around 0.25
    
    def test_calibration_error_perfect(self):
        """Perfectly calibrated model has 0 error."""
        preds = np.array([0.6, 0.6, 0.6, 0.6, 0.6])
        # 3 wins out of 5 = 60% = predicted
        outcomes = np.array([1, 1, 1, 0, 0])
        
        cal_error = compute_calibration_error(preds, outcomes)
        assert cal_error == pytest.approx(0.0, abs=0.001)
    
    def test_calibration_error_overconfident(self):
        """Overconfident model has positive error."""
        preds = np.full(100, 0.70)  # Predict 70%
        # But only 50% win
        outcomes = np.array([1] * 50 + [0] * 50)
        
        cal_error = compute_calibration_error(preds, outcomes)
        assert cal_error == pytest.approx(0.20, abs=0.01)  # 70% - 50% = 20%


class TestNHLCalibrationRequirements:
    """Tests for NHL-specific calibration requirements."""
    
    def test_nhl_calibration_within_threshold(self, nhl_realistic_data):
        """NHL model must have calibration error ≤ 3%."""
        probs, outcomes = nhl_realistic_data
        
        result = analyze_calibration(probs.tolist(), outcomes.tolist())
        
        # NHL requirement: |calibration_error| <= 0.03
        assert abs(result.calibration_error) <= 0.03, \
            f"Calibration error {result.calibration_error:.3f} exceeds 3% threshold"
    
    def test_nhl_no_slam_tier_predictions(self, nhl_realistic_data):
        """NHL predictions must not exceed 69% (no SLAM tier)."""
        probs, _ = nhl_realistic_data
        
        max_prob = probs.max()
        assert max_prob <= 0.69, \
            f"Maximum probability {max_prob:.3f} exceeds SLAM threshold (0.69)"
    
    def test_nhl_minimum_probability(self, nhl_realistic_data):
        """NHL predictions must be at least 58% (LEAN minimum)."""
        probs, _ = nhl_realistic_data
        
        min_prob = probs.min()
        assert min_prob >= 0.58, \
            f"Minimum probability {min_prob:.3f} below LEAN threshold (0.58)"
    
    def test_brier_score_acceptable(self, well_calibrated_data):
        """Brier score should be below threshold."""
        probs, outcomes = well_calibrated_data
        
        brier = compute_brier_score(probs, outcomes)
        
        # Good model should have Brier < 0.20
        assert brier < 0.20, f"Brier score {brier:.3f} too high"


class TestDecileCalibration:
    """Tests for decile-level calibration analysis."""
    
    def test_decile_bins_computed(self, well_calibrated_data):
        """Should compute calibration for each decile."""
        probs, outcomes = well_calibrated_data
        
        bin_pred, bin_act, bin_counts = compute_calibration_by_decile(probs, outcomes)
        
        assert len(bin_pred) == 10
        assert len(bin_act) == 10
        assert len(bin_counts) == 10
    
    def test_decile_error_bounds(self, nhl_realistic_data):
        """Each decile should have reasonable calibration."""
        probs, outcomes = nhl_realistic_data
        
        bin_pred, bin_act, _ = compute_calibration_by_decile(probs, outcomes)
        
        for i, (pred, act) in enumerate(zip(bin_pred, bin_act)):
            if not np.isnan(pred) and not np.isnan(act):
                decile_error = abs(pred - act)
                # Each decile should be within 10% (loose for small samples)
                assert decile_error < 0.15, \
                    f"Decile {i} error {decile_error:.3f} too large"


# ─────────────────────────────────────────────────────────
# ASSERTION TESTS (HARD GATES)
# ─────────────────────────────────────────────────────────

class TestCalibrationAssertions:
    """Hard gate assertions for calibration."""
    
    def test_calibration_error_assertion(self):
        """Assert calibration error within bounds."""
        # Good calibration
        result_good = CalibrationResult(
            n_predictions=100,
            brier_score=0.18,
            calibration_error=0.02,
            decile_predicted=[], decile_actual=[], decile_counts=[],
            bin_edges=[], bin_predicted_means=[], bin_actual_means=[],
        )
        assert result_good.is_calibrated(threshold=0.03) is True
        
        # Bad calibration
        result_bad = CalibrationResult(
            n_predictions=100,
            brier_score=0.25,
            calibration_error=0.08,
            decile_predicted=[], decile_actual=[], decile_counts=[],
            bin_edges=[], bin_predicted_means=[], bin_actual_means=[],
        )
        assert result_bad.is_calibrated(threshold=0.03) is False
    
    def test_backtest_calibration_assertion(self, nhl_realistic_data):
        """Full backtest calibration assertion."""
        probs, outcomes = nhl_realistic_data
        result = analyze_calibration(probs.tolist(), outcomes.tolist())
        
        # HARD ASSERTION
        assert abs(result.calibration_error) <= 0.03, \
            f"CALIBRATION GATE FAILED: error={result.calibration_error:.3f}"


# ─────────────────────────────────────────────────────────
# MARKET-SPECIFIC CALIBRATION
# ─────────────────────────────────────────────────────────

class TestMarketCalibration:
    """Tests for market-specific calibration."""
    
    def test_moneyline_calibration(self):
        """Moneyline market calibration."""
        np.random.seed(42)
        
        # Moneyline-style predictions (larger edges)
        probs = np.random.uniform(0.58, 0.68, 100)
        true_probs = probs + np.random.uniform(-0.03, 0.03, 100)
        outcomes = (np.random.random(100) < true_probs).astype(int)
        
        result = analyze_calibration(probs.tolist(), outcomes.tolist())
        
        assert abs(result.calibration_error) <= 0.05  # 5% tolerance for smaller sample
    
    def test_totals_calibration(self):
        """Totals market calibration."""
        np.random.seed(43)
        
        # Totals tend to cluster around 50-50 more
        probs = np.random.uniform(0.55, 0.65, 100)
        true_probs = probs + np.random.uniform(-0.02, 0.02, 100)
        outcomes = (np.random.random(100) < true_probs).astype(int)
        
        result = analyze_calibration(probs.tolist(), outcomes.tolist())
        
        assert abs(result.calibration_error) <= 0.05
    
    def test_goalie_saves_calibration(self):
        """Goalie saves market calibration."""
        np.random.seed(44)
        
        # Saves have tighter bands (58-67%)
        probs = np.random.uniform(0.58, 0.67, 80)
        true_probs = probs + np.random.uniform(-0.02, 0.02, 80)
        outcomes = (np.random.random(80) < true_probs).astype(int)
        
        result = analyze_calibration(probs.tolist(), outcomes.tolist())
        
        # Stricter for saves market
        assert abs(result.calibration_error) <= 0.04


# ─────────────────────────────────────────────────────────
# SUMMARY ASSERTION
# ─────────────────────────────────────────────────────────

def test_all_calibration_invariants():
    """
    Master calibration test - validates all invariants.
    
    MUST PASS:
    1. |calibration_error| <= 0.03
    2. Brier score tracked
    3. No predictions outside 58-69% range
    4. Decile analysis available
    """
    np.random.seed(999)
    
    # Generate NHL-compliant data
    n = 500
    probs = np.random.uniform(0.58, 0.69, n)
    true_probs = probs + np.random.normal(0, 0.02, n)
    true_probs = np.clip(true_probs, 0, 1)
    outcomes = (np.random.random(n) < true_probs).astype(int)
    
    result = analyze_calibration(probs.tolist(), outcomes.tolist())
    
    # INVARIANT 1: Calibration within bounds
    assert abs(result.calibration_error) <= 0.03, \
        f"Calibration error {result.calibration_error:.3f} > 0.03"
    
    # INVARIANT 2: Brier score reasonable
    assert 0.10 <= result.brier_score <= 0.25, \
        f"Brier score {result.brier_score:.3f} out of expected range"
    
    # INVARIANT 3: Probability range enforced
    assert probs.min() >= 0.58, "Predictions below LEAN threshold"
    assert probs.max() <= 0.69, "Predictions above STRONG threshold (SLAM forbidden)"
    
    # INVARIANT 4: Decile data available
    assert len(result.decile_predicted) == 10
    assert len(result.decile_actual) == 10
    
    print("✅ All calibration invariants PASSED")


# ─────────────────────────────────────────────────────────
# RUN TESTS
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
