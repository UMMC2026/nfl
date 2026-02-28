"""
CBB Diagnostics — Direction Bias & Projection Accuracy

This module audits resolved picks for direction bias and projection accuracy.

Features:
- Calculates win rates for OVER vs UNDER picks
- Flags systematic bias if win rate difference >10%
- Tracks projection accuracy (model vs actual)
- Logs summary diagnostics for each run

Usage:
Call `run_diagnostics(resolved_picks)` after results are entered.
"""

import logging
import numpy as np

def run_diagnostics(resolved_picks):
    """
    Audits direction bias and projection accuracy.
    Returns diagnostic summary dict.
    """
    over_results = [p for p in resolved_picks if p['direction'] == 'higher']
    under_results = [p for p in resolved_picks if p['direction'] == 'lower']

    over_wins = sum(1 for p in over_results if p['result'] == 'win')
    under_wins = sum(1 for p in under_results if p['result'] == 'win')
    over_rate = over_wins / len(over_results) if over_results else 0
    under_rate = under_wins / len(under_results) if under_results else 0

    bias_flag = abs(over_rate - under_rate) > 0.10
    if bias_flag:
        logging.warning(f'Direction bias detected: OVER win rate {over_rate:.2%}, UNDER win rate {under_rate:.2%}')

    # Projection accuracy
    model_vals = np.array([p['model_projection'] for p in resolved_picks if 'model_projection' in p])
    actual_vals = np.array([p['actual'] for p in resolved_picks if 'actual' in p])
    if len(model_vals) and len(actual_vals):
        mae = np.mean(np.abs(model_vals - actual_vals))
        logging.info(f'Projection MAE: {mae:.2f}')
    else:
        mae = None

    summary = {
        'over_win_rate': over_rate,
        'under_win_rate': under_rate,
        'direction_bias_flag': bias_flag,
        'projection_mae': mae
    }
    return summary
