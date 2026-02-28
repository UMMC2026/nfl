"""
PROBABILITY MODEL DOCUMENTATION
===============================

This document clarifies what probability models are actually used in the system,
versus what the labels might suggest.

ACTUAL PROBABILITY CALCULATION (Normal Approximation)
-----------------------------------------------------

The core probability calculation uses a NORMAL (Gaussian) approximation:

    from scipy.stats import norm
    
    if direction == "higher":
        prob = 1 - norm.cdf(line, mu, sigma)
    else:
        prob = norm.cdf(line, mu, sigma)

Where:
- mu = sample mean of player's recent performance (e.g., last 10 games)
- sigma = sample standard deviation
- line = the betting line (threshold)
- direction = "higher" or "lower"

This is NOT a sophisticated Bayesian model. It's a frequentist normal approximation
that assumes:
1. Player stats are approximately normally distributed
2. Recent sample mean/std are reasonable estimates of true parameters
3. Game-to-game performance is independent (which is false)


WHAT "BAYESIAN" COMPONENTS ACTUALLY DO
--------------------------------------

1. BayesianTuner (quant_modules/bayesian_tuner.py)
   - Uses Beta-Binomial conjugate priors
   - Learns GATE THRESHOLDS, not player probabilities
   - Updates based on historical hit/miss data
   - Does NOT affect raw probability calculations

2. Calibration Adjustments (gating/prob.py)
   - Applies caps and shrinkage to probabilities
   - Uses calibration curve fitting (not Bayesian)
   - Shrinkage is frequentist regularization, not Bayesian shrinkage

3. Matchup Memory (features/nba/player_vs_opponent.py)
   - Uses Bayesian shrinkage for small-sample adjustment
   - This IS genuinely Bayesian: blends matchup-specific mean with overall mean
   - Weight based on sample size (more games → more weight to matchup data)


WHAT IS NOT BAYESIAN
--------------------

- Raw probability calculations (normal CDF)
- Monte Carlo simulations (sampling from normal distributions)
- Confidence tier assignments
- The name "Bayesian Tuner" is a misnomer - it should be "Threshold Optimizer"


HARDENING OPTIONS (with feature flags)
--------------------------------------

If feature flags are enabled, we can use:

1. Beta Distribution for Probabilities
   - Instead of normal CDF, model success as Beta(α, β)
   - More appropriate for bounded [0,1] probabilities
   - See: quant_modules/mc_hardening.py

2. CVaR (Conditional Value at Risk)
   - Instead of expected value, use worst 5th percentile
   - More conservative risk assessment
   - See: quant_modules/mc_hardening.py

3. Correlation Adjustments
   - Account for correlated outcomes in parlays
   - Apply correlation penalty to joint probabilities
   - See: quant_modules/mc_hardening.py


HONEST LABELS
-------------

Instead of:              Use:
"Bayesian Tuner"    →    "Threshold Optimizer — Calibration-Based Gate Tuning"
"Bayesian Prob"     →    "Normal Approximation with Calibration Adjustments"
"GMM Clustering"    →    "Mixture Heuristic — Pattern Grouping (not ML)"


PROBABILITY CAPS (hardcoded reality)
------------------------------------

No matter what the model says, probabilities are capped:

    CONFIDENCE_CAPS = {
        "core": 0.75,           # 0.80 with usage gate
        "volume_micro": 0.68,
        "sequence_early": 0.65,
        "event_binary": 0.55
    }

This is a GOVERNANCE decision, not a statistical one. It acknowledges that:
1. Sports are fundamentally unpredictable
2. Model confidence should not exceed empirical hit rates
3. Edge cases always exist
"""

# This file is documentation only. No executable code.
