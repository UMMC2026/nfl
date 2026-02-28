"""
Monte Carlo Hardening Module
============================

Addresses critical weaknesses in the base Monte Carlo optimizer:

1. FALSE PRECISION: Replaces scalar p_hit with Beta(alpha, beta) distributions
2. CORRELATION BLINDNESS: Adds stat-family correlation matrix
3. TAIL RISK: Replaces Sharpe ratio with CVaR(95%) for risk measurement
4. OVERBETTING: Clamps Kelly criterion at 2% max
5. LOSS STREAKS: Estimates probability of extended losing streaks

CRITICAL: This module is OPT-IN. Set use_hardened_mc=True in config to enable.
All existing behavior is preserved when disabled.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# BETA DISTRIBUTIONS FOR PROBABILITY UNCERTAINTY
# =============================================================================

@dataclass
class BetaDistribution:
    """
    Beta distribution to model uncertainty in probability estimates.
    
    Instead of treating p_hit = 0.55 as truth, we model it as:
    Beta(alpha, beta) where mode ≈ 0.55 but with uncertainty bounds.
    
    Interpretation:
    - alpha = "pseudo-successes" (like observed hits)
    - beta = "pseudo-failures" (like observed misses)
    - Higher (alpha + beta) = more confidence/tighter distribution
    """
    alpha: float
    beta: float
    
    @classmethod
    def from_point_estimate(cls, p: float, sample_size: int = 10, 
                            min_uncertainty: float = 0.05) -> "BetaDistribution":
        """
        Create Beta distribution from a point probability estimate.
        
        Args:
            p: Point probability estimate (0-1)
            sample_size: Effective sample size (higher = more confident)
            min_uncertainty: Minimum uncertainty to prevent overconfidence
        """
        # Clamp p to valid range
        p = max(min_uncertainty, min(1 - min_uncertainty, p))
        
        # Convert to pseudo-counts
        # Using method of moments: mean = alpha / (alpha + beta)
        alpha = p * sample_size
        beta = (1 - p) * sample_size
        
        return cls(alpha=max(1.0, alpha), beta=max(1.0, beta))
    
    @property
    def mean(self) -> float:
        """Mean of the distribution."""
        return self.alpha / (self.alpha + self.beta)
    
    @property
    def mode(self) -> float:
        """Mode (most likely value) of the distribution."""
        if self.alpha > 1 and self.beta > 1:
            return (self.alpha - 1) / (self.alpha + self.beta - 2)
        return self.mean
    
    @property
    def variance(self) -> float:
        """Variance of the distribution."""
        ab = self.alpha + self.beta
        return (self.alpha * self.beta) / (ab * ab * (ab + 1))
    
    @property
    def std_dev(self) -> float:
        """Standard deviation of the distribution."""
        return math.sqrt(self.variance)
    
    def percentile(self, q: float) -> float:
        """
        Approximate percentile using normal approximation.
        
        For more accurate results, use scipy.stats.beta.ppf
        """
        # Normal approximation (reasonable for alpha, beta > 5)
        z_scores = {0.05: -1.645, 0.10: -1.28, 0.25: -0.674, 
                    0.50: 0.0, 0.75: 0.674, 0.90: 1.28, 0.95: 1.645}
        
        z = z_scores.get(q, 0.0)
        return max(0.0, min(1.0, self.mean + z * self.std_dev))
    
    @property
    def ci_95(self) -> Tuple[float, float]:
        """95% credible interval."""
        return (self.percentile(0.025), self.percentile(0.975))
    
    def sample(self) -> float:
        """Draw a sample from the distribution."""
        # Use gamma distribution trick: Beta(a,b) = Gamma(a,1) / (Gamma(a,1) + Gamma(b,1))
        x = random.gammavariate(self.alpha, 1.0)
        y = random.gammavariate(self.beta, 1.0)
        return x / (x + y) if (x + y) > 0 else 0.5
    
    def conservative_estimate(self, risk_aversion: float = 0.1) -> float:
        """
        Get a conservative (downside-adjusted) probability estimate.
        
        For betting, we want to be conservative about our edge.
        This returns a lower percentile based on risk aversion.
        
        risk_aversion=0.1 returns ~10th percentile (conservative)
        risk_aversion=0.5 returns median
        """
        return self.percentile(risk_aversion)


def scalar_to_beta(p_hit: float, confidence: float = 0.5) -> BetaDistribution:
    """
    Convert scalar probability to Beta distribution.
    
    confidence: 0.0-1.0 indicating how certain we are about p_hit
    Higher confidence = tighter distribution around p_hit
    """
    # Map confidence to effective sample size (5 to 50)
    sample_size = int(5 + confidence * 45)
    return BetaDistribution.from_point_estimate(p_hit, sample_size)


# =============================================================================
# STAT FAMILY CORRELATION MATRIX
# =============================================================================

class StatFamily(Enum):
    """Groups of correlated statistics."""
    SCORING = "scoring"       # PTS, FGM, FGA, 3PM
    REBOUNDING = "rebounding" # REB, OREB, DREB
    PLAYMAKING = "playmaking" # AST
    DEFENSE = "defense"       # STL, BLK
    USAGE = "usage"           # Minutes-driven
    COMPOSITE = "composite"   # PRA, PR, PA, RA


# Which family each stat belongs to
STAT_TO_FAMILY: Dict[str, StatFamily] = {
    "PTS": StatFamily.SCORING,
    "FGM": StatFamily.SCORING,
    "FGA": StatFamily.SCORING,
    "3PM": StatFamily.SCORING,
    "REB": StatFamily.REBOUNDING,
    "OREB": StatFamily.REBOUNDING,
    "DREB": StatFamily.REBOUNDING,
    "AST": StatFamily.PLAYMAKING,
    "STL": StatFamily.DEFENSE,
    "BLK": StatFamily.DEFENSE,
    "TOV": StatFamily.USAGE,
    "MIN": StatFamily.USAGE,
    "PRA": StatFamily.COMPOSITE,
    "PR": StatFamily.COMPOSITE,
    "PA": StatFamily.COMPOSITE,
    "RA": StatFamily.COMPOSITE,
    "STOCKS": StatFamily.DEFENSE,
}

# Correlation matrix between stat families
# Values are Pearson correlations (empirically derived approximations)
FAMILY_CORRELATIONS: Dict[Tuple[StatFamily, StatFamily], float] = {
    # Same family = high correlation
    (StatFamily.SCORING, StatFamily.SCORING): 0.85,
    (StatFamily.REBOUNDING, StatFamily.REBOUNDING): 0.80,
    (StatFamily.PLAYMAKING, StatFamily.PLAYMAKING): 1.0,
    (StatFamily.DEFENSE, StatFamily.DEFENSE): 0.60,
    (StatFamily.USAGE, StatFamily.USAGE): 0.90,
    (StatFamily.COMPOSITE, StatFamily.COMPOSITE): 0.70,
    
    # Cross-family correlations (lower)
    (StatFamily.SCORING, StatFamily.REBOUNDING): 0.25,
    (StatFamily.SCORING, StatFamily.PLAYMAKING): 0.35,
    (StatFamily.SCORING, StatFamily.DEFENSE): 0.15,
    (StatFamily.SCORING, StatFamily.USAGE): 0.55,
    (StatFamily.SCORING, StatFamily.COMPOSITE): 0.75,
    
    (StatFamily.REBOUNDING, StatFamily.PLAYMAKING): 0.20,
    (StatFamily.REBOUNDING, StatFamily.DEFENSE): 0.30,
    (StatFamily.REBOUNDING, StatFamily.USAGE): 0.45,
    (StatFamily.REBOUNDING, StatFamily.COMPOSITE): 0.60,
    
    (StatFamily.PLAYMAKING, StatFamily.DEFENSE): 0.10,
    (StatFamily.PLAYMAKING, StatFamily.USAGE): 0.40,
    (StatFamily.PLAYMAKING, StatFamily.COMPOSITE): 0.65,
    
    (StatFamily.DEFENSE, StatFamily.USAGE): 0.20,
    (StatFamily.DEFENSE, StatFamily.COMPOSITE): 0.25,
    
    (StatFamily.USAGE, StatFamily.COMPOSITE): 0.60,
}


def get_correlation(stat1: str, stat2: str) -> float:
    """Get correlation between two stats."""
    family1 = STAT_TO_FAMILY.get(stat1.upper(), StatFamily.USAGE)
    family2 = STAT_TO_FAMILY.get(stat2.upper(), StatFamily.USAGE)
    
    if family1 == family2:
        key = (family1, family1)
    else:
        # Try both orders
        key = (family1, family2)
        if key not in FAMILY_CORRELATIONS:
            key = (family2, family1)
    
    return FAMILY_CORRELATIONS.get(key, 0.2)  # Default low correlation


def compute_portfolio_correlation(picks: List[Dict[str, Any]]) -> float:
    """
    Compute average pairwise correlation for a set of picks.
    
    High correlation = more volatile portfolio (boom or bust together)
    Low correlation = more diversified
    """
    if len(picks) < 2:
        return 0.0
    
    correlations = []
    for i in range(len(picks)):
        for j in range(i + 1, len(picks)):
            stat1 = picks[i].get("stat_type", "PTS")
            stat2 = picks[j].get("stat_type", "PTS")
            
            # Same player = higher correlation
            if picks[i].get("player_id") == picks[j].get("player_id"):
                corr = 0.9  # Very high for same player different stats
            else:
                corr = get_correlation(stat1, stat2)
            
            correlations.append(corr)
    
    return sum(correlations) / len(correlations) if correlations else 0.0


# =============================================================================
# CVAR (CONDITIONAL VALUE AT RISK) FOR TAIL RISK
# =============================================================================

def compute_cvar(returns: List[float], confidence_level: float = 0.95) -> float:
    """
    Compute CVaR (Conditional Value at Risk) at given confidence level.
    
    CVaR_95 = Expected loss in the worst 5% of outcomes
    
    Unlike Sharpe ratio which treats upside and downside symmetrically,
    CVaR focuses specifically on downside tail risk.
    
    Args:
        returns: List of possible returns (can include negative values)
        confidence_level: VaR confidence level (0.95 = 95%)
    
    Returns:
        CVaR value (negative = expected loss, positive = expected gain in tail)
    """
    if not returns:
        return 0.0
    
    sorted_returns = sorted(returns)
    
    # VaR is the return at the (1 - confidence) percentile
    var_index = int((1 - confidence_level) * len(sorted_returns))
    var_index = max(0, min(var_index, len(sorted_returns) - 1))
    
    # CVaR is the mean of returns worse than VaR
    tail_returns = sorted_returns[:var_index + 1]
    
    if not tail_returns:
        return sorted_returns[0]
    
    return sum(tail_returns) / len(tail_returns)


def compute_risk_adjusted_ev(
    ev: float,
    cvar: float,
    risk_weight: float = 0.3
) -> float:
    """
    Compute risk-adjusted expected value.
    
    Penalizes EV based on tail risk (CVaR).
    
    risk_weight: How much to weight downside risk (0-1)
    """
    # If CVaR is negative (losing in worst cases), reduce EV
    if cvar < 0:
        return ev + risk_weight * cvar  # cvar is negative, so this reduces ev
    return ev


# =============================================================================
# KELLY CRITERION WITH CLAMP
# =============================================================================

MAX_KELLY_FRACTION = 0.02  # 2% of bankroll maximum


def compute_clamped_kelly(
    p_win: float,
    odds: float,
    max_fraction: float = MAX_KELLY_FRACTION
) -> float:
    """
    Compute Kelly criterion with maximum bet size clamp.
    
    Kelly formula: f* = (bp - q) / b
    where b = odds-1, p = win prob, q = 1-p
    
    CRITICAL: We clamp at 2% to prevent ruin from model errors.
    
    Args:
        p_win: Probability of winning
        odds: Decimal odds (e.g., 3.0 for 3x payout)
        max_fraction: Maximum fraction of bankroll to bet
    
    Returns:
        Optimal bet fraction (0 to max_fraction)
    """
    if p_win <= 0 or p_win >= 1 or odds <= 1:
        return 0.0
    
    b = odds - 1  # Net odds
    q = 1 - p_win
    
    kelly = (b * p_win - q) / b
    
    # Clamp to prevent overbetting
    kelly = max(0.0, min(kelly, max_fraction))
    
    return kelly


def compute_fractional_kelly(
    p_win: float,
    odds: float,
    fraction: float = 0.25,
    max_fraction: float = MAX_KELLY_FRACTION
) -> float:
    """
    Compute fractional Kelly (more conservative).
    
    Many professionals use 1/4 Kelly to account for estimation errors.
    """
    full_kelly = compute_clamped_kelly(p_win, odds, max_fraction=1.0)
    return min(full_kelly * fraction, max_fraction)


# =============================================================================
# LOSS STREAK ESTIMATION
# =============================================================================

def estimate_loss_streak_probability(
    p_wins: List[float],
    streak_length: int = 5,
    simulations: int = 10000
) -> float:
    """
    Estimate probability of experiencing a losing streak of given length.
    
    This is critical for bankroll management and psychological preparation.
    
    Args:
        p_wins: List of win probabilities for upcoming bets
        streak_length: Length of losing streak to estimate
        simulations: Number of Monte Carlo simulations
    
    Returns:
        Probability of experiencing at least one losing streak of given length
    """
    if not p_wins or streak_length < 1:
        return 0.0
    
    if streak_length > len(p_wins):
        # Extend with average probability
        avg_p = sum(p_wins) / len(p_wins)
        p_wins = p_wins + [avg_p] * (streak_length - len(p_wins))
    
    streak_count = 0
    
    for _ in range(simulations):
        current_streak = 0
        max_streak = 0
        
        for p in p_wins:
            if random.random() < p:
                # Win - reset streak
                current_streak = 0
            else:
                # Loss - extend streak
                current_streak += 1
                max_streak = max(max_streak, current_streak)
        
        if max_streak >= streak_length:
            streak_count += 1
    
    return streak_count / simulations


def estimate_max_drawdown(
    p_wins: List[float],
    bet_size: float = 1.0,
    payouts: List[float] = None,
    simulations: int = 10000
) -> Tuple[float, float]:
    """
    Estimate maximum drawdown from a sequence of bets.
    
    Returns:
        (mean_max_drawdown, worst_case_drawdown)
    """
    if not p_wins:
        return (0.0, 0.0)
    
    if payouts is None:
        payouts = [2.0] * len(p_wins)  # Even money default
    
    drawdowns = []
    
    for _ in range(simulations):
        bankroll = 100.0  # Start with $100
        peak = bankroll
        max_dd = 0.0
        
        for p, payout in zip(p_wins, payouts):
            if random.random() < p:
                # Win
                bankroll += bet_size * (payout - 1)
            else:
                # Loss
                bankroll -= bet_size
            
            peak = max(peak, bankroll)
            drawdown = (peak - bankroll) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)
        
        drawdowns.append(max_dd)
    
    mean_dd = sum(drawdowns) / len(drawdowns)
    worst_dd = max(drawdowns)
    
    return (mean_dd, worst_dd)


# =============================================================================
# HARDENED PICK EVALUATION
# =============================================================================

@dataclass
class HardenedEvaluation:
    """Result of hardened pick evaluation with full uncertainty modeling."""
    
    # Input
    player_id: str
    stat_type: str
    line: float
    direction: str
    
    # Probability with uncertainty
    p_hit_point: float         # Original point estimate
    p_hit_beta: BetaDistribution  # Beta distribution
    p_hit_conservative: float  # Conservative (10th percentile) estimate
    
    # Risk metrics
    ev_point: float           # EV using point estimate
    ev_conservative: float    # EV using conservative estimate
    cvar_95: float            # Conditional VaR at 95%
    risk_adjusted_ev: float   # EV penalized by tail risk
    
    # Sizing
    kelly_full: float         # Full Kelly fraction
    kelly_clamped: float      # Clamped Kelly (max 2%)
    kelly_quarter: float      # Quarter Kelly (conservative)
    
    # Correlation impact
    portfolio_correlation: Optional[float] = None
    correlation_penalty: float = 0.0
    
    # Loss streak risk
    streak_5_prob: Optional[float] = None
    max_drawdown_mean: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "stat_type": self.stat_type,
            "line": self.line,
            "direction": self.direction,
            "p_hit_point": self.p_hit_point,
            "p_hit_mean": self.p_hit_beta.mean,
            "p_hit_std": self.p_hit_beta.std_dev,
            "p_hit_conservative": self.p_hit_conservative,
            "p_hit_ci_95": self.p_hit_beta.ci_95,
            "ev_point": self.ev_point,
            "ev_conservative": self.ev_conservative,
            "cvar_95": self.cvar_95,
            "risk_adjusted_ev": self.risk_adjusted_ev,
            "kelly_full": self.kelly_full,
            "kelly_clamped": self.kelly_clamped,
            "kelly_quarter": self.kelly_quarter,
            "portfolio_correlation": self.portfolio_correlation,
            "correlation_penalty": self.correlation_penalty,
            "streak_5_prob": self.streak_5_prob,
            "max_drawdown_mean": self.max_drawdown_mean,
        }


def evaluate_pick_hardened(
    player_id: str,
    stat_type: str,
    line: float,
    direction: str,
    p_hit: float,
    payout: float,
    confidence: float = 0.5,
    risk_aversion: float = 0.1,
) -> HardenedEvaluation:
    """
    Evaluate a single pick with full hardening.
    
    Args:
        player_id: Player identifier
        stat_type: Stat type (PTS, REB, etc.)
        line: Prop line
        direction: HIGHER or LOWER
        p_hit: Point probability estimate
        payout: Decimal payout odds
        confidence: Confidence in probability estimate (0-1)
        risk_aversion: Risk aversion level (0.1 = conservative)
    
    Returns:
        HardenedEvaluation with full metrics
    """
    # Convert to Beta distribution
    beta = scalar_to_beta(p_hit, confidence)
    p_conservative = beta.conservative_estimate(risk_aversion)
    
    # Compute EVs
    ev_point = p_hit * payout - 1
    ev_conservative = p_conservative * payout - 1
    
    # Simulate for CVaR
    returns = []
    for _ in range(1000):
        p_sample = beta.sample()
        if random.random() < p_sample:
            returns.append(payout - 1)  # Win
        else:
            returns.append(-1)  # Lose stake
    
    cvar = compute_cvar(returns, 0.95)
    risk_adj_ev = compute_risk_adjusted_ev(ev_point, cvar)
    
    # Kelly sizing
    kelly_full = compute_clamped_kelly(p_hit, payout, max_fraction=1.0)
    kelly_clamped = compute_clamped_kelly(p_hit, payout, MAX_KELLY_FRACTION)
    kelly_quarter = compute_fractional_kelly(p_hit, payout, fraction=0.25)
    
    return HardenedEvaluation(
        player_id=player_id,
        stat_type=stat_type,
        line=line,
        direction=direction,
        p_hit_point=p_hit,
        p_hit_beta=beta,
        p_hit_conservative=p_conservative,
        ev_point=ev_point,
        ev_conservative=ev_conservative,
        cvar_95=cvar,
        risk_adjusted_ev=risk_adj_ev,
        kelly_full=kelly_full,
        kelly_clamped=kelly_clamped,
        kelly_quarter=kelly_quarter,
    )


def evaluate_portfolio_hardened(
    picks: List[Dict[str, Any]],
    payouts: Dict[int, float],
) -> Dict[str, Any]:
    """
    Evaluate a portfolio of picks with correlation and streak risk.
    
    Args:
        picks: List of pick dicts with player_id, stat_type, p_hit
        payouts: Payout table (e.g., {2: 3.0, 3: 6.0, ...})
    
    Returns:
        Portfolio evaluation with risk metrics
    """
    if not picks:
        return {"error": "No picks provided"}
    
    # Evaluate each pick
    evaluations = []
    for pick in picks:
        eval_result = evaluate_pick_hardened(
            player_id=pick.get("player_id", "unknown"),
            stat_type=pick.get("stat_type", "PTS"),
            line=pick.get("line", 0),
            direction=pick.get("direction", "HIGHER"),
            p_hit=pick.get("p_hit", 0.5),
            payout=payouts.get(len(picks), 2.0),
            confidence=pick.get("confidence", 0.5),
        )
        evaluations.append(eval_result)
    
    # Portfolio correlation
    avg_correlation = compute_portfolio_correlation(picks)
    
    # Correlation penalty (higher correlation = higher penalty)
    # This reduces effective diversification
    correlation_penalty = avg_correlation * 0.1  # 10% penalty per correlation point
    
    # Loss streak estimation
    p_wins = [e.p_hit_conservative for e in evaluations]
    streak_prob = estimate_loss_streak_probability(p_wins, streak_length=5)
    
    # Drawdown estimation
    pick_payout = payouts.get(len(picks), 2.0)
    mean_dd, worst_dd = estimate_max_drawdown(
        p_wins,
        bet_size=1.0,
        payouts=[pick_payout] * len(p_wins)
    )
    
    # Aggregate metrics
    total_ev_point = sum(e.ev_point for e in evaluations) / len(evaluations)
    total_ev_conservative = sum(e.ev_conservative for e in evaluations) / len(evaluations)
    total_cvar = sum(e.cvar_95 for e in evaluations) / len(evaluations)
    
    # Apply correlation penalty to EV
    adjusted_ev = total_ev_point * (1 - correlation_penalty)
    
    return {
        "pick_count": len(picks),
        "evaluations": [e.to_dict() for e in evaluations],
        "portfolio_correlation": avg_correlation,
        "correlation_penalty": correlation_penalty,
        "ev_point_avg": total_ev_point,
        "ev_conservative_avg": total_ev_conservative,
        "ev_correlation_adjusted": adjusted_ev,
        "cvar_95_avg": total_cvar,
        "loss_streak_5_prob": streak_prob,
        "max_drawdown_mean": mean_dd,
        "max_drawdown_worst": worst_dd,
        "risk_summary": {
            "correlation_risk": "HIGH" if avg_correlation > 0.5 else "MEDIUM" if avg_correlation > 0.3 else "LOW",
            "streak_risk": "HIGH" if streak_prob > 0.3 else "MEDIUM" if streak_prob > 0.15 else "LOW",
            "drawdown_risk": "HIGH" if worst_dd > 0.5 else "MEDIUM" if worst_dd > 0.3 else "LOW",
        }
    }
