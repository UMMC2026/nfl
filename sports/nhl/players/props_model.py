"""
NHL PLAYER PROPS MODEL — v3.0 Module
====================================

Expanded player props modeling beyond SOG:
- Goals
- Assists  
- Points (Goals + Assists)
- Blocked Shots
- Hits

Uses Poisson/Negative Binomial distributions with opponent adjustments.

Model Notes:
    - Goals: Very low count → Poisson with λ ~0.25-0.50
    - Assists: Similar to goals → Poisson λ ~0.30-0.60
    - Points: Sum of Goals + Assists → Poisson λ ~0.60-1.20
    - Blocks/Hits: Poisson for defensemen, Negative Binomial for variability
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

# Tier thresholds (same as SOG for consistency)
class PropTier(str, Enum):
    STRONG = "STRONG"   # 62-70%
    LEAN = "LEAN"       # 58-61%
    NO_PLAY = "NO_PLAY" # <58%


TIER_THRESHOLDS = {
    PropTier.STRONG: (0.62, 0.70),
    PropTier.LEAN: (0.58, 0.619),
    PropTier.NO_PLAY: (0.0, 0.579),
}

# Stat-specific confidence caps
STAT_CONFIDENCE_CAPS = {
    "goals": 0.68,      # Goals are volatile - cap lower
    "assists": 0.66,
    "points": 0.68,
    "blocks": 0.70,
    "hits": 0.70,
    "sog": 0.70,
}

# Minimum games for reliability
MIN_GAMES_PLAYED = 10

# Position-based defaults (per game)
POSITION_DEFAULTS = {
    "F": {
        "goals": 0.28,
        "assists": 0.38,
        "points": 0.66,
        "blocks": 0.5,
        "hits": 1.5,
        "sog": 2.8,
    },
    "D": {
        "goals": 0.10,
        "assists": 0.30,
        "points": 0.40,
        "blocks": 1.8,
        "hits": 1.8,
        "sog": 1.6,
    },
}

# Variance multipliers by stat (for negative binomial)
OVERDISPERSION = {
    "goals": 1.5,   # Goals cluster/drought
    "assists": 1.3,
    "points": 1.2,
    "blocks": 1.4,
    "hits": 1.6,    # Hits very variable
    "sog": 1.2,
}


@dataclass
class PlayerPropInput:
    """Input for player prop analysis"""
    player_name: str
    team: str
    opponent: str
    position: str  # F or D
    
    # Season stats
    stat_avg: float         # Per-game average
    stat_std: float         # Standard deviation
    games_played: int
    
    # Prop line
    line: float
    stat_type: str          # goals, assists, points, blocks, hits, sog
    
    # Context
    is_home: bool = True
    is_back_to_back: bool = False
    opponent_rank: int = 16     # 1-32 (1 = best defense)


@dataclass
class PlayerPropResult:
    """Result of player prop analysis"""
    player_name: str
    opponent: str
    stat_type: str
    line: float
    
    # Probabilities
    lambda_value: float     # Expected value
    over_prob: float
    under_prob: float
    
    # Edge analysis
    best_direction: str     # "OVER" or "UNDER"
    probability: float      # Best side probability
    implied_prob: float     # Market implied (default 0.50)
    edge: float
    
    # Tier
    tier: PropTier
    playable: bool
    
    # Risk factors
    risk_flags: List[str] = field(default_factory=list)
    confidence_cap: float = 0.70
    
    def to_dict(self) -> Dict:
        return {
            "player": self.player_name,
            "opponent": self.opponent,
            "stat": self.stat_type,
            "line": self.line,
            "lambda": round(self.lambda_value, 3),
            "direction": self.best_direction,
            "probability": round(self.probability * 100, 1),
            "edge": round(self.edge * 100, 1),
            "tier": self.tier.value,
            "playable": self.playable,
            "risk_flags": self.risk_flags,
        }


# ============================================================
# PROBABILITY CALCULATIONS
# ============================================================

def poisson_over_prob(lambda_val: float, line: float) -> float:
    """
    Calculate P(X > line) using Poisson distribution.
    
    For whole number lines (1.5, 2.5, etc.):
        P(X > 1.5) = P(X >= 2) = 1 - P(X <= 1)
    """
    if lambda_val <= 0:
        return 0.0
    
    # Line is typically X.5, so need X >= ceil(line)
    k = int(math.ceil(line))
    
    # P(X >= k) = 1 - P(X <= k-1)
    prob_under = scipy_stats.poisson.cdf(k - 1, lambda_val)
    return 1.0 - prob_under


def poisson_under_prob(lambda_val: float, line: float) -> float:
    """
    Calculate P(X < line) using Poisson distribution.
    
    For whole number lines (1.5, 2.5, etc.):
        P(X < 1.5) = P(X <= 1)
    """
    if lambda_val <= 0:
        return 1.0
    
    k = int(math.floor(line))
    return scipy_stats.poisson.cdf(k, lambda_val)


def negative_binomial_over_prob(mean: float, variance: float, line: float) -> float:
    """
    Calculate P(X > line) using Negative Binomial for overdispersed counts.
    
    NB parameters:
        n = mean² / (variance - mean)
        p = mean / variance
    """
    if mean <= 0 or variance <= mean:
        # Fall back to Poisson
        return poisson_over_prob(mean, line)
    
    try:
        n = (mean ** 2) / (variance - mean)
        p = mean / variance
        
        k = int(math.ceil(line))
        prob_under = scipy_stats.nbinom.cdf(k - 1, n, p)
        return 1.0 - prob_under
    except:
        return poisson_over_prob(mean, line)


def negative_binomial_under_prob(mean: float, variance: float, line: float) -> float:
    """Calculate P(X < line) using Negative Binomial"""
    if mean <= 0 or variance <= mean:
        return poisson_under_prob(mean, line)
    
    try:
        n = (mean ** 2) / (variance - mean)
        p = mean / variance
        
        k = int(math.floor(line))
        return scipy_stats.nbinom.cdf(k, n, p)
    except:
        return poisson_under_prob(mean, line)


# ============================================================
# OPPONENT ADJUSTMENTS
# ============================================================

def get_opponent_adjustment(opponent_rank: int, stat_type: str) -> float:
    """
    Get opponent adjustment factor based on defensive ranking.
    
    Args:
        opponent_rank: Team defensive rank (1-32, 1 = best)
        stat_type: Type of stat
    
    Returns:
        Multiplier for lambda (< 1.0 = harder matchup)
    """
    # Normalize rank to adjustment factor
    # Rank 1 (best D) → 0.90 (suppress 10%)
    # Rank 16 (avg) → 1.00
    # Rank 32 (worst D) → 1.10 (boost 10%)
    
    base_adjustment = 1.0 + ((opponent_rank - 16) / 160)  # ±10% swing
    
    # Stat-specific sensitivity
    sensitivity = {
        "goals": 1.2,       # Goals more affected by defense
        "assists": 0.8,     # Assists less correlated
        "points": 1.0,
        "sog": 0.9,
        "blocks": 0.7,      # Blocks depend on opponent offense
        "hits": 0.5,        # Hits mostly player-specific
    }
    
    sens = sensitivity.get(stat_type, 1.0)
    adjustment = 1.0 + (base_adjustment - 1.0) * sens
    
    return round(adjustment, 3)


def get_b2b_adjustment(stat_type: str) -> float:
    """Get back-to-back game adjustment"""
    b2b_penalties = {
        "goals": 0.90,      # -10% on B2B
        "assists": 0.95,
        "points": 0.92,
        "sog": 0.95,
        "blocks": 0.92,
        "hits": 0.85,       # Hits drop most on tired legs
    }
    return b2b_penalties.get(stat_type, 0.95)


# ============================================================
# MAIN MODEL
# ============================================================

class PlayerPropsModel:
    """
    Model for NHL player props (Goals, Assists, Points, Blocks, Hits).
    
    Usage:
        model = PlayerPropsModel()
        result = model.analyze_prop(input_data)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def analyze_prop(
        self,
        prop: PlayerPropInput,
        implied_prob: float = 0.50,
    ) -> PlayerPropResult:
        """
        Analyze a player prop.
        
        Args:
            prop: PlayerPropInput with all context
            implied_prob: Market implied probability (default 50%)
        
        Returns:
            PlayerPropResult with probabilities and recommendation
        """
        risk_flags = []
        
        # === 1. CALCULATE ADJUSTED LAMBDA ===
        base_lambda = prop.stat_avg
        
        # Fallback to position defaults if no data
        if base_lambda <= 0 or prop.games_played < MIN_GAMES_PLAYED:
            defaults = POSITION_DEFAULTS.get(prop.position, POSITION_DEFAULTS["F"])
            base_lambda = defaults.get(prop.stat_type, 1.0)
            risk_flags.append("LOW_SAMPLE")
        
        # Apply opponent adjustment
        opp_adj = get_opponent_adjustment(prop.opponent_rank, prop.stat_type)
        
        # Apply B2B adjustment
        b2b_adj = get_b2b_adjustment(prop.stat_type) if prop.is_back_to_back else 1.0
        if prop.is_back_to_back:
            risk_flags.append("BACK_TO_BACK")
        
        # Final lambda
        lambda_val = base_lambda * opp_adj * b2b_adj
        
        # === 2. CALCULATE PROBABILITIES ===
        # Use overdispersion factor for variance
        overdispersion = OVERDISPERSION.get(prop.stat_type, 1.2)
        variance = lambda_val * overdispersion
        
        if variance > lambda_val:
            # Use Negative Binomial for overdispersed data
            over_prob = negative_binomial_over_prob(lambda_val, variance, prop.line)
            under_prob = negative_binomial_under_prob(lambda_val, variance, prop.line)
        else:
            # Use Poisson
            over_prob = poisson_over_prob(lambda_val, prop.line)
            under_prob = poisson_under_prob(lambda_val, prop.line)
        
        # Normalize (should sum to ~1)
        total = over_prob + under_prob
        if total > 0:
            over_prob /= total
            under_prob /= total
        
        # === 3. DETERMINE BEST SIDE ===
        if over_prob > under_prob:
            best_direction = "OVER"
            probability = over_prob
        else:
            best_direction = "UNDER"
            probability = under_prob
        
        # === 4. APPLY CONFIDENCE CAP ===
        cap = STAT_CONFIDENCE_CAPS.get(prop.stat_type, 0.70)
        if probability > cap:
            probability = cap
            risk_flags.append("CAPPED")
        
        # === 5. CALCULATE EDGE ===
        edge = probability - implied_prob
        
        # === 6. ASSIGN TIER ===
        tier = self._assign_tier(probability)
        playable = tier != PropTier.NO_PLAY and edge >= 0.02
        
        if edge < 0.02:
            risk_flags.append("LOW_EDGE")
            playable = False
        
        return PlayerPropResult(
            player_name=prop.player_name,
            opponent=prop.opponent,
            stat_type=prop.stat_type,
            line=prop.line,
            lambda_value=lambda_val,
            over_prob=over_prob,
            under_prob=under_prob,
            best_direction=best_direction,
            probability=probability,
            implied_prob=implied_prob,
            edge=edge,
            tier=tier,
            playable=playable,
            risk_flags=risk_flags,
            confidence_cap=cap,
        )
    
    def _assign_tier(self, probability: float) -> PropTier:
        """Assign tier based on probability"""
        if 0.62 <= probability <= 0.70:
            return PropTier.STRONG
        elif 0.58 <= probability < 0.62:
            return PropTier.LEAN
        else:
            return PropTier.NO_PLAY
    
    def analyze_batch(
        self,
        props: List[PlayerPropInput],
    ) -> List[PlayerPropResult]:
        """Analyze multiple props"""
        results = []
        for prop in props:
            result = self.analyze_prop(prop)
            results.append(result)
        return results


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def analyze_player_prop(
    player_name: str,
    stat_type: str,
    line: float,
    stat_avg: float,
    opponent: str = "UNK",
    position: str = "F",
    opponent_rank: int = 16,
    is_b2b: bool = False,
) -> PlayerPropResult:
    """
    Quick analysis of a single player prop.
    
    Args:
        player_name: Player name
        stat_type: goals, assists, points, blocks, hits
        line: Betting line
        stat_avg: Player's per-game average
        opponent: Opponent team
        position: F or D
        opponent_rank: 1-32 defensive ranking
        is_b2b: Back-to-back game
    
    Returns:
        PlayerPropResult
    """
    prop = PlayerPropInput(
        player_name=player_name,
        team="",
        opponent=opponent,
        position=position,
        stat_avg=stat_avg,
        stat_std=stat_avg * 0.5,  # Estimate
        games_played=50,
        line=line,
        stat_type=stat_type,
        is_back_to_back=is_b2b,
        opponent_rank=opponent_rank,
    )
    
    model = PlayerPropsModel()
    return model.analyze_prop(prop)


# ============================================================
# CLI TESTING
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  NHL PLAYER PROPS MODEL — TEST")
    print("=" * 60)
    
    model = PlayerPropsModel()
    
    # Test cases
    test_props = [
        # (name, stat, line, avg, opp, pos, opp_rank)
        ("Connor McDavid", "points", 1.5, 1.50, "CGY", "F", 20),
        ("Connor McDavid", "goals", 0.5, 0.55, "CGY", "F", 20),
        ("Auston Matthews", "goals", 0.5, 0.50, "BOS", "F", 5),
        ("Nathan MacKinnon", "points", 1.5, 1.40, "DET", "F", 25),
        ("Cale Makar", "points", 0.5, 1.20, "DAL", "D", 8),
        ("Alex Ovechkin", "sog", 3.5, 3.8, "PHI", "F", 28),
    ]
    
    print("\n📊 PLAYER PROP ANALYSIS")
    print("-" * 60)
    
    for name, stat, line, avg, opp, pos, rank in test_props:
        result = analyze_player_prop(
            player_name=name,
            stat_type=stat,
            line=line,
            stat_avg=avg,
            opponent=opp,
            position=pos,
            opponent_rank=rank,
        )
        
        tier_emoji = "🟢" if result.tier == PropTier.STRONG else ("🟡" if result.tier == PropTier.LEAN else "⚪")
        
        print(f"\n{tier_emoji} {result.player_name} vs {result.opponent}")
        print(f"   {result.stat_type.upper()} {result.best_direction} {result.line}")
        print(f"   λ={result.lambda_value:.2f} | Prob: {result.probability*100:.1f}% | Edge: {result.edge*100:.1f}%")
        print(f"   Tier: {result.tier.value} | Playable: {'✓' if result.playable else '✗'}")
        if result.risk_flags:
            print(f"   ⚠️  Flags: {', '.join(result.risk_flags)}")
    
    print("\n" + "=" * 60)
