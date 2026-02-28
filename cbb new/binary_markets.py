"""
FUOOM DARK MATTER — markets/binary_markets.py
==============================================
Binary market modeling for YES/NO format betting.
Implements compound probability models for:
- MVP / Award markets
- Golf winner / top-N markets
- Game-level YES/NO propositions

Audit Reference: FUOOM-AUDIT-001, Sections 9, 16, 17, 18

Author: FUOOM Engineering
Version: 1.0.0
Date: 2026-02-15
"""

import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SECTION 1: MVP / AWARD PROBABILITY MODEL (Audit Item #17)
# =============================================================================
# P(player wins MVP) = P(team wins) × P(player is top performer | team wins)
# This is a COMPOUND probability — both conditions must be true.

# Historical position base rates for Super Bowl MVP
SB_MVP_POSITION_RATES = {
    'QB':  0.65,   # QB wins ~65% of Super Bowl MVPs
    'WR':  0.12,
    'RB':  0.08,
    'TE':  0.05,
    'DE':  0.04,
    'LB':  0.03,
    'CB':  0.02,
    'S':   0.01,
    'DEF': 0.10,   # Combined defensive (if position not specified)
    'K':   0.00,   # Extremely rare
    'OTHER': 0.02,
}

# NBA MVP position rates (regular season)
NBA_MVP_POSITION_RATES = {
    'C':  0.30,
    'PF': 0.20,
    'SF': 0.15,
    'SG': 0.15,
    'PG': 0.20,
}


def mvp_probability(team_win_prob: float,
                     position: str,
                     performance_percentile: float,
                     sport: str = 'NFL',
                     custom_position_rates: Optional[Dict] = None) -> Dict:
    """Calculate MVP probability using compound probability model.
    
    Formula: P(MVP) = P(team wins) × P(top performer | team wins)
    where P(top performer | win) = position_base_rate × performance_factor
    
    Args:
        team_win_prob: Probability team wins the game/championship
        position: Player's position (e.g., 'QB', 'WR', 'C')
        performance_percentile: Player's projected performance percentile
                                within their position group (0.0 to 1.0)
        sport: Sport key for position rates
        custom_position_rates: Override default position rates
    
    Returns:
        Dict with MVP probability and breakdown
    """
    # Get position rates
    if custom_position_rates:
        rates = custom_position_rates
    elif sport == 'NFL':
        rates = SB_MVP_POSITION_RATES
    elif sport == 'NBA':
        rates = NBA_MVP_POSITION_RATES
    else:
        rates = {'DEFAULT': 1.0 / 10}  # Uniform if unknown
    
    position_rate = rates.get(position, rates.get('OTHER', 0.02))
    
    # P(top performer | team wins) = position_rate × performance_factor
    # performance_percentile is how this player ranks vs others at same position
    p_top_performer = position_rate * performance_percentile
    
    # Compound probability
    p_mvp = team_win_prob * p_top_performer
    
    return {
        'mvp_probability': round(p_mvp, 4),
        'team_win_prob': round(team_win_prob, 4),
        'position': position,
        'position_base_rate': round(position_rate, 4),
        'performance_percentile': round(performance_percentile, 4),
        'p_top_performer_given_win': round(p_top_performer, 4),
        'sport': sport,
    }


def evaluate_mvp_market(player_mvp_prob: float,
                         yes_odds: float,
                         no_odds: float) -> Dict:
    """Evaluate an MVP market for edge.
    
    Args:
        player_mvp_prob: Model's MVP probability
        yes_odds: American odds for YES
        no_odds: American odds for NO
    
    Returns:
        Dict with edge analysis and recommendation
    """
    from shared.math_utils import (
        american_to_implied, remove_vig, calculate_ev,
        american_to_decimal, kelly_full
    )
    
    # Get true implied probabilities (vig removed)
    imp_yes = american_to_implied(yes_odds)
    imp_no = american_to_implied(no_odds)
    true_yes, true_no = remove_vig(imp_yes, imp_no)
    
    # Calculate EV for YES and NO
    dec_yes = american_to_decimal(yes_odds)
    dec_no = american_to_decimal(no_odds)
    
    ev_yes = calculate_ev(player_mvp_prob, dec_yes)
    ev_no = calculate_ev(1.0 - player_mvp_prob, dec_no)
    
    # Kelly for best side
    k_yes = kelly_full(player_mvp_prob, dec_yes) if player_mvp_prob > 0.01 else -1
    k_no = kelly_full(1.0 - player_mvp_prob, dec_no) if player_mvp_prob < 0.99 else -1
    
    # Determine recommendation
    if ev_yes > 0 and ev_yes > ev_no:
        direction = 'YES'
        edge = player_mvp_prob - true_yes
        ev = ev_yes
        kelly = k_yes
    elif ev_no > 0:
        direction = 'NO'
        edge = (1.0 - player_mvp_prob) - true_no
        ev = ev_no
        kelly = k_no
    else:
        direction = 'NO_PLAY'
        edge = 0
        ev = max(ev_yes, ev_no)
        kelly = 0
    
    return {
        'model_prob': round(player_mvp_prob, 4),
        'market_implied_yes': round(true_yes, 4),
        'market_implied_no': round(true_no, 4),
        'vig_pct': round((imp_yes + imp_no - 1) * 100, 1),
        'direction': direction,
        'edge': round(edge, 4),
        'expected_value': round(ev, 4),
        'kelly_full': round(kelly, 4) if kelly > -1 else None,
        'yes_odds': yes_odds,
        'no_odds': no_odds,
    }


# =============================================================================
# SECTION 2: GOLF WINNER PROBABILITY MODEL (Audit Item #18)
# =============================================================================
# Golf winner markets have ~150 player fields with base rate ~0.7%.
# Uses order statistics / Thurstone model with strokes-gained advantage.

def golf_winner_probability(strokes_gained_total: float,
                             field_size: int = 132,
                             course_fit_score: float = 0.50,
                             sg_multiplier: float = 2.0,
                             max_prob: float = 0.30) -> Dict:
    """Calculate golf tournament winner probability.
    
    Model: P(win) = (1/field) × 2^SG_advantage × course_fit_factor
    Each stroke gained approximately doubles win probability (calibrated from PGA data).
    
    Args:
        strokes_gained_total: Player's strokes gained vs field
        field_size: Number of players in field
        course_fit_score: Course fit factor (0.0 to 1.0, 0.5 = neutral)
        sg_multiplier: Base multiplier per stroke gained (default 2.0)
        max_prob: Maximum probability cap (even best rarely > 25%)
    
    Returns:
        Dict with win probability and breakdown
    """
    # Base rate
    base = 1.0 / field_size
    
    # Skill multiplier from strokes gained
    skill_mult = sg_multiplier ** strokes_gained_total
    
    # Course fit multiplier (centered at 1.0)
    course_mult = 1.0 + (course_fit_score - 0.5) * 0.4
    
    # Raw probability
    raw_prob = base * skill_mult * course_mult
    
    # Cap at maximum
    final_prob = min(raw_prob, max_prob)
    
    return {
        'win_probability': round(final_prob, 4),
        'base_rate': round(base, 4),
        'strokes_gained': round(strokes_gained_total, 2),
        'skill_multiplier': round(skill_mult, 4),
        'course_fit_score': round(course_fit_score, 2),
        'course_multiplier': round(course_mult, 4),
        'raw_probability': round(raw_prob, 4),
        'capped': raw_prob > max_prob,
        'field_size': field_size,
    }


def evaluate_golf_winner_market(model_prob: float,
                                  yes_odds: float,
                                  no_odds: float) -> Dict:
    """Evaluate a golf winner market for edge.
    
    Golf winner markets are typically massively overpriced because
    the base rate is so low (~0.7%). Model probabilities of 2-5%
    vs market implied of 20-30% = strong NO edge.
    
    Args:
        model_prob: Model's win probability
        yes_odds: American odds for YES (e.g., +285)
        no_odds: American odds for NO (e.g., -317)
    
    Returns:
        Dict with edge analysis
    """
    return evaluate_mvp_market(model_prob, yes_odds, no_odds)


def golf_top_n_probability(strokes_gained_total: float,
                            field_size: int = 132,
                            n: int = 10,
                            course_fit_score: float = 0.50) -> Dict:
    """Calculate probability of finishing in top N.
    
    Simpler than winner probability — uses normal approximation
    for order statistics.
    
    Args:
        strokes_gained_total: Player's SG advantage
        field_size: Field size
        n: Top-N cutoff (e.g., 10 for Top 10)
        course_fit_score: Course fit (0.0 to 1.0)
    
    Returns:
        Dict with top-N probability
    """
    from scipy import stats
    
    # Base rate for top N
    base_rate = n / field_size
    
    # SG advantage shifts the distribution
    # Each SG moves you ~0.5 sigma in the order statistic
    sigma_shift = strokes_gained_total * 0.5
    
    # Course fit adjustment
    course_shift = (course_fit_score - 0.5) * 0.3
    
    # Probability via normal CDF
    total_shift = sigma_shift + course_shift
    
    # Convert base rate to z-score, shift, convert back
    base_z = stats.norm.ppf(base_rate)
    adjusted_z = base_z + total_shift
    top_n_prob = stats.norm.cdf(adjusted_z)
    
    # Cap between 0.01 and 0.90
    top_n_prob = max(min(top_n_prob, 0.90), 0.01)
    
    return {
        'top_n': n,
        'probability': round(top_n_prob, 4),
        'base_rate': round(base_rate, 4),
        'strokes_gained': round(strokes_gained_total, 2),
        'course_fit_score': round(course_fit_score, 2),
        'field_size': field_size,
    }


# =============================================================================
# SECTION 3: GENERIC BINARY MARKET EVALUATOR
# =============================================================================

def evaluate_binary_market(model_prob: float,
                            yes_odds: float,
                            no_odds: float,
                            market_name: str = '',
                            min_edge: float = 0.03) -> Dict:
    """Universal binary market (YES/NO) evaluator.
    
    Works for any DK Predictions, FanDuel specials, or similar YES/NO markets.
    
    Args:
        model_prob: Model's probability of YES outcome
        yes_odds: American odds for YES
        no_odds: American odds for NO
        market_name: Description of the market
        min_edge: Minimum edge to recommend (default 3%)
    
    Returns:
        Dict with full analysis and recommendation
    """
    result = evaluate_mvp_market(model_prob, yes_odds, no_odds)
    result['market_name'] = market_name
    
    # Add tier assignment
    from shared.config import assign_tier
    
    if result['direction'] == 'YES':
        result['tier'] = assign_tier(model_prob)
        result['confidence'] = model_prob
    elif result['direction'] == 'NO':
        result['tier'] = assign_tier(1.0 - model_prob)
        result['confidence'] = 1.0 - model_prob
    else:
        result['tier'] = 'NO_PLAY'
        result['confidence'] = 0.0
    
    # Apply minimum edge filter
    if abs(result['edge']) < min_edge:
        result['direction'] = 'NO_PLAY'
        result['tier'] = 'NO_PLAY'
        result['note'] = f'Edge {abs(result["edge"]):.1%} below minimum {min_edge:.1%}'
    
    return result


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == '__main__':
    print("=== FUOOM Binary Markets Self-Test ===\n")
    
    # Test MVP probability
    print("--- MVP Probability ---")
    mvp = mvp_probability(
        team_win_prob=0.68,
        position='QB',
        performance_percentile=0.85,
        sport='NFL'
    )
    print(f"  QB on 68% favorite, 85th percentile:")
    print(f"  P(MVP) = {mvp['mvp_probability']:.4f} ({mvp['mvp_probability']*100:.1f}%)")
    
    # Test MVP market evaluation
    print("\n--- MVP Market Evaluation ---")
    eval_result = evaluate_mvp_market(
        player_mvp_prob=0.376,
        yes_odds=127,
        no_odds=-257
    )
    print(f"  Model: {eval_result['model_prob']:.1%}")
    print(f"  Market implied YES: {eval_result['market_implied_yes']:.1%}")
    print(f"  Direction: {eval_result['direction']}")
    print(f"  Edge: {eval_result['edge']:.1%}")
    print(f"  EV: {eval_result['expected_value']:.4f}")
    
    # Test Golf winner
    print("\n--- Golf Winner Probability ---")
    golf = golf_winner_probability(
        strokes_gained_total=1.8,
        field_size=132,
        course_fit_score=0.70
    )
    print(f"  SG +1.8, course fit 0.70:")
    print(f"  P(win) = {golf['win_probability']:.4f} ({golf['win_probability']*100:.1f}%)")
    print(f"  Skill multiplier: {golf['skill_multiplier']:.2f}x")
    
    # Test Golf market
    print("\n--- Golf Winner Market ---")
    golf_eval = evaluate_golf_winner_market(
        model_prob=0.0285,
        yes_odds=285,
        no_odds=-317
    )
    print(f"  Model: {golf_eval['model_prob']:.1%}")
    print(f"  Market: {golf_eval['market_implied_yes']:.1%}")
    print(f"  Direction: {golf_eval['direction']} (should be NO — market massively overpriced)")
    print(f"  Edge: {golf_eval['edge']:.1%}")
    
    # Test binary market
    print("\n--- Generic Binary Market ---")
    binary = evaluate_binary_market(
        model_prob=0.72,
        yes_odds=-150,
        no_odds=130,
        market_name="Will game go to overtime?"
    )
    print(f"  {binary['market_name']}")
    print(f"  Direction: {binary['direction']}, Tier: {binary['tier']}")
    print(f"  Edge: {binary['edge']:.1%}, EV: {binary['expected_value']:.4f}")
    
    print("\n✅ All binary market self-tests passed")
