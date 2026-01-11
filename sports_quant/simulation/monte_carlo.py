from typing import Dict, Optional, Tuple
import math
import numpy as np

# Note: numpy is already present; scipy optional via extras for advanced fitting.


def _fit_lognormal(mean: float, variance: float) -> Tuple[float, float]:
    """Return (mu, sigma) for lognormal given mean/variance."""
    if mean <= 0:
        mean = 1e-6
    if variance <= 0:
        variance = 1e-6
    phi = math.sqrt(variance + mean ** 2)
    mu = math.log(mean ** 2 / phi)
    sigma = math.sqrt(math.log(phi ** 2 / mean ** 2))
    return mu, sigma


def _sample(dist: str, mean: float, variance: float, n: int) -> np.ndarray:
    dist = dist.lower()
    if dist == "normal":
        std = math.sqrt(max(variance, 1e-6))
        return np.random.normal(loc=mean, scale=std, size=n)
    if dist == "poisson":
        lam = max(mean, 1e-6)
        return np.random.poisson(lam=lam, size=n).astype(float)
    if dist == "lognormal":
        mu, sigma = _fit_lognormal(mean, variance)
        return np.random.lognormal(mean=mu, sigma=sigma, size=n)
    # fallback
    std = math.sqrt(max(variance, 1e-6))
    return np.random.normal(loc=mean, scale=std, size=n)


def _confidence(mean: float, variance: float, n_sims: int) -> float:
    """Heuristic confidence using signal-to-noise and simulation count."""
    snr = abs(mean) / (math.sqrt(max(variance, 1e-8)))
    sims_factor = math.sqrt(n_sims) / (math.sqrt(n_sims) + 50.0)
    conf = 1 / (1 + math.exp(-snr))  # sigmoid
    return max(0.01, min(0.99, conf * sims_factor))


def run_monte_carlo(line: float, mean: float, variance: float, dist: str = "normal", n_sims: int = 10000,
                     clip_min: Optional[float] = None) -> Dict:
    """Run Monte Carlo simulation and return the SOP output contract."""
    samples = _sample(dist, mean, variance, n_sims)
    if clip_min is not None:
        samples = np.clip(samples, clip_min, None)
    p_over = float(np.mean(samples > line))
    p_under = 1.0 - p_over
    expected_value = float(np.mean(samples) - line)
    p05 = float(np.percentile(samples, 5))
    p95 = float(np.percentile(samples, 95))
    conf = _confidence(mean, variance, n_sims)
    return {
        "line": float(line),
        "p_over": p_over,
        "p_under": p_under,
        "expected_value": expected_value,
        "confidence": conf,
        "tail_risk": {"p05": p05, "p95": p95},
    }
