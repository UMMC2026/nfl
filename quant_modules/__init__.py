"""
QUANT MODULES
=============
Professional trading math for prop analysis:
- BacktestEngine: Calibration curves, Brier score, tier/stat analysis
- MonteCarloOptimizer: Entry simulation, Kelly criterion, VaR
- BayesianTuner: Beta-Binomial posteriors, gate threshold learning
- MCHardening: Beta distributions, CVaR, correlation matrix, clamped Kelly

Usage:
    from quant_modules import run_calibration_report, optimize_entries, run_bayesian_tuning
    
    # After slate analysis, call:
    run_calibration_report(picks_data)
    optimize_entries(picks_data)
    run_bayesian_tuning()
    
    # For hardened analysis (opt-in):
    from quant_modules import evaluate_pick_hardened, evaluate_portfolio_hardened
    hardened_eval = evaluate_pick_hardened(player_id, stat_type, line, direction, p_hit, payout)
"""

from .backtest_engine import BacktestEngine, run_calibration_report
from .monte_carlo_optimizer import MonteCarloOptimizer, optimize_entries, optimize_entries_unfiltered
from .bayesian_tuner import BayesianTuner, run_bayesian_tuning

# MC Hardening - opt-in features (Task 3)
from .mc_hardening import (
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
    HardenedEvaluation,
)

__all__ = [
    # Existing
    "BacktestEngine",
    "run_calibration_report",
    "MonteCarloOptimizer", 
    "optimize_entries",
    "optimize_entries_unfiltered",
    "BayesianTuner",
    "run_bayesian_tuning",
    # Hardening (Task 3)
    "BetaDistribution",
    "scalar_to_beta",
    "compute_cvar",
    "compute_clamped_kelly",
    "compute_fractional_kelly",
    "compute_portfolio_correlation",
    "evaluate_pick_hardened",
    "evaluate_portfolio_hardened",
    "estimate_loss_streak_probability",
    "estimate_max_drawdown",
    "HardenedEvaluation",
]
