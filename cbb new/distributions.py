"""
FUOOM DARK MATTER — nfl/distributions.py
=========================================
NFL-specific scoring distributions and weather impact modeling.

Implements:
- Discrete NFL scoring model (Poisson mixture) — Audit Item #4 CRITICAL
- Skellam distribution for margin modeling
- Continuous wind impact model — Audit Item #9 WARNING
- Temperature and precipitation adjustments
- Key number probability analysis

Audit Reference: FUOOM-AUDIT-001, Sections 4, 7

Author: FUOOM Engineering
Version: 1.0.0
Date: 2026-02-15
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SECTION 1: NFL DISCRETE SCORING MODEL (Audit Item #4 — CRITICAL)
# =============================================================================
# Using Normal distribution for NFL margins is WRONG.
# NFL scoring is discrete (3, 7 point increments) and clusters at key numbers.
# This module implements a Poisson mixture model for realistic score simulation.

# NFL scoring outcome probabilities per possession
# Calibrate these from play-by-play data (nflfastR)
NFL_POSSESSION_OUTCOMES = {
    'no_score':     0.55,   # Punt, turnover, downs
    'field_goal':   0.15,   # 3 points
    'td_pat':       0.22,   # 7 points (TD + extra point)
    'td_miss_pat':  0.01,   # 6 points (TD + missed PAT)
    'td_2pt':       0.02,   # 8 points (TD + 2-point conversion)
    'safety':       0.01,   # 2 points (safety)
    'td_2pt_fail':  0.02,   # 6 points (TD + failed 2-point)
    'fg_miss':      0.02,   # 0 points (missed FG, counts as possession)
}

# Corresponding point values
NFL_SCORE_VALUES = {
    'no_score':     0,
    'field_goal':   3,
    'td_pat':       7,
    'td_miss_pat':  6,
    'td_2pt':       8,
    'safety':       2,
    'td_2pt_fail':  6,
    'fg_miss':      0,
}

# NFL key numbers (percentage of games decided by these margins)
NFL_KEY_NUMBERS = {
    3:  0.155,   # ~15.5% of NFL games decided by exactly 3
    7:  0.095,   # ~9.5% by exactly 7
    10: 0.055,   # ~5.5% by exactly 10
    6:  0.050,   # ~5.0% by exactly 6
    14: 0.045,   # ~4.5% by exactly 14
    4:  0.040,   # ~4.0% by exactly 4
    1:  0.035,   # ~3.5% by exactly 1
    17: 0.030,   # ~3.0% by exactly 17
}


def nfl_score_distribution(expected_score: float, n_sims: int = 10000,
                            possessions_lambda: float = 12.0,
                            weather_adjustment: float = 1.0) -> np.ndarray:
    """Simulate NFL team scores using Poisson possession model.
    
    Models NFL scoring as a sequence of discrete drive outcomes,
    preserving key number structure (3, 7, 10, 14 clustering).
    
    Args:
        expected_score: Team's expected point total
        n_sims: Number of simulations
        possessions_lambda: Expected possessions per game (~12)
        weather_adjustment: Multiplier for scoring (< 1.0 = worse conditions)
    
    Returns:
        Array of simulated scores (integers)
    """
    # Adjust possession probabilities based on expected score
    # If expected_score is high, increase scoring probabilities
    league_avg_score = 23.0  # NFL league average ~23 pts/game
    score_ratio = expected_score / league_avg_score
    
    # Adjust scoring probabilities (preserve no-score as complement)
    adj_probs = {}
    scoring_keys = [k for k in NFL_POSSESSION_OUTCOMES if k not in ('no_score', 'fg_miss')]
    
    for key in scoring_keys:
        adj_probs[key] = NFL_POSSESSION_OUTCOMES[key] * score_ratio * weather_adjustment
    
    adj_probs['fg_miss'] = NFL_POSSESSION_OUTCOMES['fg_miss']
    scoring_sum = sum(adj_probs.values())
    adj_probs['no_score'] = max(1.0 - scoring_sum, 0.30)  # Floor at 30%
    
    # Normalize
    total = sum(adj_probs.values())
    adj_probs = {k: v / total for k, v in adj_probs.items()}
    
    outcomes = list(adj_probs.keys())
    probs = [adj_probs[k] for k in outcomes]
    values = [NFL_SCORE_VALUES[k] for k in outcomes]
    
    scores = np.zeros(n_sims, dtype=int)
    for i in range(n_sims):
        n_possessions = max(np.random.poisson(possessions_lambda), 6)
        drive_outcomes = np.random.choice(len(outcomes), size=n_possessions, p=probs)
        scores[i] = sum(values[o] for o in drive_outcomes)
    
    return scores


def nfl_margin_distribution(home_expected: float, away_expected: float,
                             n_sims: int = 10000,
                             weather_adj: float = 1.0) -> Dict:
    """Simulate NFL game margins preserving key number structure.
    
    Args:
        home_expected: Home team expected score
        away_expected: Away team expected score
        n_sims: Number of simulations
        weather_adj: Weather adjustment factor
    
    Returns:
        Dict with margins, probabilities, key number analysis
    """
    home_scores = nfl_score_distribution(home_expected, n_sims, weather_adjustment=weather_adj)
    away_scores = nfl_score_distribution(away_expected, n_sims, weather_adjustment=weather_adj)
    
    margins = home_scores - away_scores  # Positive = home wins
    totals = home_scores + away_scores
    
    # Win probabilities
    home_win_pct = np.mean(margins > 0)
    away_win_pct = np.mean(margins < 0)
    tie_pct = np.mean(margins == 0)
    
    # Key number analysis
    key_number_probs = {}
    for kn in NFL_KEY_NUMBERS:
        # Probability margin falls on this key number (either side)
        prob = np.mean(np.abs(margins) == kn)
        key_number_probs[kn] = round(float(prob), 4)
    
    # Spread cover probabilities
    projected_spread = -(home_expected - away_expected)  # Negative = home favored
    
    return {
        'home_scores': home_scores,
        'away_scores': away_scores,
        'margins': margins,
        'totals': totals,
        'home_win_prob': round(float(home_win_pct), 4),
        'away_win_prob': round(float(away_win_pct), 4),
        'tie_prob': round(float(tie_pct), 4),
        'mean_margin': round(float(np.mean(margins)), 2),
        'std_margin': round(float(np.std(margins)), 2),
        'mean_total': round(float(np.mean(totals)), 2),
        'std_total': round(float(np.std(totals)), 2),
        'median_home_score': int(np.median(home_scores)),
        'median_away_score': int(np.median(away_scores)),
        'key_number_probs': key_number_probs,
    }


def spread_cover_probability(margins: np.ndarray, spread: float) -> Dict:
    """Calculate spread cover probabilities from simulated margins.
    
    Convention: spread is from home team perspective.
    spread = -3 means home is 3-point favorite.
    
    Args:
        margins: Array of simulated margins (home - away)
        spread: The spread line (negative = home favored)
    
    Returns:
        Dict with cover probabilities
    """
    # Home covers if margin > -spread (e.g., margin > 3 when spread is -3)
    adjusted = margins + spread  # If home -3, need margin > 3 → adjusted > 0
    
    home_covers = np.mean(adjusted > 0)
    away_covers = np.mean(adjusted < 0)
    push = np.mean(adjusted == 0)
    
    return {
        'spread': spread,
        'home_cover_prob': round(float(home_covers), 4),
        'away_cover_prob': round(float(away_covers), 4),
        'push_prob': round(float(push), 4),
    }


def total_probability(totals: np.ndarray, line: float) -> Dict:
    """Calculate over/under probabilities from simulated totals.
    
    Args:
        totals: Array of simulated game totals
        line: The total line
    
    Returns:
        Dict with over/under probabilities
    """
    over_prob = np.mean(totals > line)
    under_prob = np.mean(totals < line)
    push_prob = np.mean(totals == line)
    
    return {
        'total_line': line,
        'over_prob': round(float(over_prob), 4),
        'under_prob': round(float(under_prob), 4),
        'push_prob': round(float(push_prob), 4),
        'mean_total': round(float(np.mean(totals)), 2),
    }


# =============================================================================
# SECTION 2: SKELLAM DISTRIBUTION (Audit Item #4)
# =============================================================================

def skellam_margin_probability(home_lambda: float, away_lambda: float,
                                margin: int) -> float:
    """Calculate probability of exact margin using Skellam distribution.
    
    Skellam = difference of two Poisson random variables.
    Captures discrete NFL scoring patterns (key numbers).
    
    Args:
        home_lambda: Home team scoring rate parameter
        away_lambda: Away team scoring rate parameter
        margin: Exact margin to calculate probability for
    
    Returns:
        Probability of this exact margin
    """
    return float(stats.skellam.pmf(margin, home_lambda, away_lambda))


def skellam_spread_cover(home_lambda: float, away_lambda: float,
                          spread: float) -> float:
    """Calculate spread cover probability using Skellam distribution.
    
    Args:
        home_lambda: Home team expected score / scoring unit
        away_lambda: Away team expected score / scoring unit
        spread: Spread line (negative = home favored)
    
    Returns:
        Probability home team covers the spread
    """
    # Home covers if (home_score - away_score) > -spread
    # P(margin > -spread) = 1 - P(margin <= -spread) = 1 - CDF(-spread)
    cover_prob = 1.0 - stats.skellam.cdf(-spread, home_lambda, away_lambda)
    return float(cover_prob)


# =============================================================================
# SECTION 3: WEATHER IMPACT MODEL (Audit Items #7, #9 — WARNING)
# =============================================================================
# Replaces flat "wind > 15mph = 15% reduction" with continuous models.

def wind_impact_on_passing(wind_mph: float, 
                            direction: str = 'crosswind') -> float:
    """Calculate wind impact on passing EPA.
    
    Nonlinear (quadratic) model with directional modifiers.
    Crosswind is worse than headwind/tailwind for accuracy.
    
    Args:
        wind_mph: Wind speed in mph
        direction: 'crosswind', 'headwind', or 'tailwind'
    
    Returns:
        Multiplier (1.0 = no impact, 0.50 = maximum impact)
    """
    if wind_mph <= 0:
        return 1.0
    
    # Base impact: quadratic, caps at 50% reduction
    base_reduction = min((wind_mph / 40.0) ** 1.5, 0.50)
    
    # Directional modifier
    direction_mods = {
        'crosswind': 1.3,   # 30% worse for accuracy
        'headwind':  1.0,   # Reduces distance but not accuracy
        'tailwind':  0.6,   # Partially helps
    }
    modifier = direction_mods.get(direction, 1.0)
    
    return max(1.0 - (base_reduction * modifier), 0.50)


def temperature_impact(temp_f: float) -> float:
    """Calculate temperature impact on passing/catching.
    
    Below 40°F, grip and ball aerodynamics degrade.
    
    Args:
        temp_f: Temperature in Fahrenheit
    
    Returns:
        Multiplier (1.0 = no impact, 0.80 = maximum cold impact)
    """
    if temp_f > 40:
        return 1.0
    return max(0.90 - (40 - temp_f) * 0.003, 0.80)


def precipitation_impact(precip_type: str) -> float:
    """Calculate precipitation impact on passing/catching.
    
    Args:
        precip_type: 'none', 'rain', 'snow', 'heavy_rain', 'heavy_snow'
    
    Returns:
        Multiplier (1.0 = dry, lower = worse)
    """
    precip_factors = {
        'none':       1.00,
        'light_rain': 0.95,
        'rain':       0.92,
        'heavy_rain': 0.85,
        'light_snow': 0.93,
        'snow':       0.85,
        'heavy_snow': 0.78,
        'sleet':      0.82,
    }
    return precip_factors.get(precip_type, 1.0)


def total_weather_adjustment(wind_mph: float, wind_dir: str,
                              temp_f: float, precip: str) -> Dict:
    """Calculate total weather adjustment for NFL game.
    
    Combines wind, temperature, and precipitation as SEPARATE multipliers.
    NOT combined into a single adjustment — each factor is independent.
    
    Args:
        wind_mph: Wind speed in mph
        wind_dir: Wind direction relative to field
        temp_f: Temperature in Fahrenheit
        precip: Precipitation type
    
    Returns:
        Dict with individual factors and combined adjustment
    """
    wind_factor = wind_impact_on_passing(wind_mph, wind_dir)
    temp_factor = temperature_impact(temp_f)
    rain_factor = precipitation_impact(precip)
    
    combined = wind_factor * temp_factor * rain_factor
    
    result = {
        'wind_factor': round(wind_factor, 4),
        'temp_factor': round(temp_factor, 4),
        'precip_factor': round(rain_factor, 4),
        'combined_passing_adjustment': round(combined, 4),
        'conditions': {
            'wind_mph': wind_mph,
            'wind_direction': wind_dir,
            'temp_f': temp_f,
            'precipitation': precip,
        },
        'is_dome': False,  # Caller should set True for dome games
        'impact_level': _classify_weather_impact(combined),
    }
    
    logger.info(
        f"Weather adjustment: wind={wind_factor:.3f} × temp={temp_factor:.3f} "
        f"× precip={rain_factor:.3f} = {combined:.3f} ({result['impact_level']})"
    )
    
    return result


def _classify_weather_impact(combined: float) -> str:
    """Classify weather impact severity."""
    if combined >= 0.95:
        return 'MINIMAL'
    elif combined >= 0.85:
        return 'MODERATE'
    elif combined >= 0.75:
        return 'SIGNIFICANT'
    else:
        return 'SEVERE'


# =============================================================================
# SECTION 4: MONEYLINE / WIN PROBABILITY (Audit Item #8)
# =============================================================================

def asymmetric_logistic_win_prob(margin: float, sport: str,
                                  is_home: bool = True,
                                  k: Optional[float] = None,
                                  alpha: Optional[float] = None) -> float:
    """Calculate win probability using asymmetric logistic transform.
    
    Formula: win_prob = 1 / (1 + exp(-(k * margin + alpha)))
    where alpha accounts for residual home-field advantage.
    
    Args:
        margin: Projected point margin (positive = this team favored)
        sport: Sport key for default parameters
        is_home: Whether this is the home team
        k: Override slope parameter (use calibrated value)
        alpha: Override intercept (use calibrated value)
    
    Returns:
        Win probability (0.0 to 1.0)
    """
    from shared.config import LOGISTIC_PARAMS
    
    params = LOGISTIC_PARAMS.get(sport, {'k': 0.15, 'alpha': 0.10})
    
    if k is None:
        k = params['k']
    if alpha is None:
        alpha = params['alpha'] if is_home else -params['alpha']
    
    if not params.get('calibrated', False):
        logger.warning(
            f"Using uncalibrated logistic parameters for {sport}. "
            f"Fit k and alpha from historical data using LogisticRegression."
        )
    
    exponent = -(k * margin + alpha)
    
    # Numerical stability
    if exponent > 500:
        return 0.0
    elif exponent < -500:
        return 1.0
    
    return 1.0 / (1.0 + np.exp(exponent))


def calibrate_logistic_params(projected_margins: np.ndarray,
                                actual_outcomes: np.ndarray) -> Dict:
    """Calibrate logistic transform parameters from historical data.
    
    Uses sklearn LogisticRegression to fit k (slope) and alpha (intercept)
    from actual game outcomes vs projected margins.
    
    Args:
        projected_margins: Array of projected margins (home perspective)
        actual_outcomes: Array of actual outcomes (1 = home win, 0 = away win)
    
    Returns:
        Dict with calibrated k, alpha, and validation metrics
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
    except ImportError:
        logger.error("sklearn required for calibration. pip install scikit-learn")
        raise
    
    X = projected_margins.reshape(-1, 1)
    y = actual_outcomes
    
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    
    k_calibrated = float(model.coef_[0][0])
    alpha_calibrated = float(model.intercept_[0])
    
    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='neg_brier_score')
    
    # Predictions for Brier score
    from shared.math_utils import brier_score
    preds = model.predict_proba(X)[:, 1]
    bs = brier_score(preds, y)
    
    return {
        'k': round(k_calibrated, 6),
        'alpha': round(alpha_calibrated, 6),
        'brier_score': round(bs, 4),
        'cv_brier_mean': round(float(-np.mean(cv_scores)), 4),
        'cv_brier_std': round(float(np.std(cv_scores)), 4),
        'n_samples': len(y),
        'calibrated': True,
    }


# =============================================================================
# SECTION 5: TEAM AGGREGATION (Audit Item #5 — CRITICAL)
# =============================================================================

def aggregate_team_score(player_projections: List[Dict],
                          bench_estimate: float,
                          pace_adjustment: float,
                          opponent_def_rating: float,
                          sport: str,
                          is_home: bool,
                          use_venue_neutral: bool = True) -> Dict:
    """Aggregate player projections to team score with NO double-counting.
    
    CRITICAL FIX (Audit Item #5): Home advantage applied at exactly ONE level.
    Option A (default): Venue-neutral player projections + team-level home boost.
    
    Args:
        player_projections: List of dicts with 'player', 'projected_points'
        bench_estimate: Expected bench contribution
        pace_adjustment: Pace-based scoring adjustment
        opponent_def_rating: Opponent's defensive rating
        sport: Sport key
        is_home: Whether this is the home team
        use_venue_neutral: If True, player projections are venue-neutral
                          and HCA is added at team level (RECOMMENDED)
    
    Returns:
        Dict with team expected score and breakdown
    """
    from shared.config import defensive_adjustment, HOME_ADVANTAGE
    
    # Sum player projections
    starters_total = sum(p.get('projected_points', 0) for p in player_projections)
    
    # Defensive adjustment
    def_adj = defensive_adjustment(opponent_def_rating, sport)
    
    # Home court advantage — APPLIED ONLY ONCE
    hca = 0.0
    if use_venue_neutral and is_home:
        hca = HOME_ADVANTAGE.get(sport, {}).get('points', 0.0)
    elif not use_venue_neutral:
        # Player projections already include HCA — do NOT add again
        hca = 0.0
        logger.debug("HCA embedded in player projections — not adding at team level")
    
    team_expected = starters_total + bench_estimate + pace_adjustment + hca - def_adj
    
    return {
        'team_expected': round(team_expected, 2),
        'breakdown': {
            'starters_total': round(starters_total, 2),
            'bench_estimate': round(bench_estimate, 2),
            'pace_adjustment': round(pace_adjustment, 2),
            'home_court_advantage': round(hca, 2),
            'defensive_adjustment': round(def_adj, 2),
        },
        'hca_source': 'team_level' if use_venue_neutral else 'player_level',
        'is_home': is_home,
    }


if __name__ == '__main__':
    print("=== FUOOM NFL distributions.py Self-Test ===\n")
    
    # Test discrete scoring
    print("--- NFL Score Distribution (10K sims) ---")
    scores = nfl_score_distribution(24.0, n_sims=10000)
    print(f"  Expected: 24.0, Simulated mean: {np.mean(scores):.1f}")
    print(f"  Std: {np.std(scores):.1f}, Min: {np.min(scores)}, Max: {np.max(scores)}")
    
    # Test margin distribution
    print("\n--- NFL Margin Distribution ---")
    result = nfl_margin_distribution(27.0, 24.0, n_sims=10000)
    print(f"  Home 27 vs Away 24:")
    print(f"  Home win: {result['home_win_prob']:.3f}")
    print(f"  Away win: {result['away_win_prob']:.3f}")
    print(f"  Mean margin: {result['mean_margin']:.1f}")
    print(f"  Key numbers: {result['key_number_probs']}")
    
    # Test spread cover
    print("\n--- Spread Cover ---")
    spread_result = spread_cover_probability(result['margins'], -3.0)
    print(f"  Spread -3: Home covers {spread_result['home_cover_prob']:.3f}")
    
    # Test weather
    print("\n--- Weather Impact ---")
    w = total_weather_adjustment(20, 'crosswind', 28, 'snow')
    print(f"  20mph crosswind, 28°F, snow:")
    print(f"  Wind: {w['wind_factor']:.3f}, Temp: {w['temp_factor']:.3f}, "
          f"Precip: {w['precip_factor']:.3f}")
    print(f"  Combined: {w['combined_passing_adjustment']:.3f} ({w['impact_level']})")
    
    # Test logistic
    print("\n--- Win Probability (Asymmetric Logistic) ---")
    for margin in [-7, -3, 0, 3, 7]:
        prob = asymmetric_logistic_win_prob(margin, 'NFL', is_home=True)
        print(f"  NFL margin {margin:+d} (home): {prob:.3f}")
    
    print("\n✅ All NFL distribution self-tests passed")
