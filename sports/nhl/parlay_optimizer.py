"""
NHL PARLAY OPTIMIZER — v3.0 Module
==================================

Monte Carlo simulation for optimal parlay combinations.

Features:
    - Simulates 2,000+ entries
    - Correlation detection (same game, same player)
    - Kelly Criterion sizing
    - Expected value (EV) calculation
    - Top N parlay recommendations

Strategy:
    - 2-4 leg parlays for best EV
    - Avoid same-game parlays (correlated)
    - Mix STRONG + LEAN tiers
    - Diversify across games
"""

import logging
import random
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from itertools import combinations
import statistics

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

# Monte Carlo settings
NUM_SIMULATIONS = 2000
MAX_PARLAY_LEGS = 6
MIN_PARLAY_LEGS = 2

# Kelly criterion
KELLY_FRACTION = 0.25  # Quarter Kelly for safety

# Correlation penalties
SAME_GAME_PENALTY = 0.15      # -15% for same game legs
SAME_PLAYER_PENALTY = 0.30    # -30% for same player props (heavy correlation)
CORRELATED_STATS_PENALTY = 0.10  # -10% for correlated stats (goals/assists)

# Tier scoring
TIER_SCORES = {
    "STRONG": 3,
    "LEAN": 2,
    "NO_PLAY": 0,
}

# Minimum EV threshold for recommendations
MIN_EV_THRESHOLD = 0.05  # 5% expected value


@dataclass
class ParlayLeg:
    """Single leg of a parlay"""
    player: str
    team: str
    opponent: str
    game_id: str          # Unique game identifier (team1_team2_date)
    stat: str
    line: float
    direction: str        # OVER or UNDER
    probability: float    # Model probability (0-1)
    tier: str
    
    def __hash__(self):
        return hash(f"{self.player}_{self.stat}_{self.line}_{self.direction}")
    
    def __eq__(self, other):
        if not isinstance(other, ParlayLeg):
            return False
        return (self.player == other.player and 
                self.stat == other.stat and 
                self.line == other.line)


@dataclass
class ParlayResult:
    """Result of a parlay simulation"""
    legs: List[ParlayLeg]
    
    # Probabilities
    raw_probability: float      # Product of individual probs
    adjusted_probability: float  # After correlation penalties
    
    # Expected value
    implied_odds: float
    ev: float                   # Expected value (%)
    
    # Scoring
    tier_score: int
    diversity_score: int        # Games represented
    
    # Recommendations
    kelly_stake: float          # Fractional Kelly stake
    recommended: bool
    
    # Simulation results
    win_rate: float = 0.0       # From MC simulation
    avg_payout: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "legs": len(self.legs),
            "players": [leg.player for leg in self.legs],
            "raw_prob": round(self.raw_probability * 100, 2),
            "adj_prob": round(self.adjusted_probability * 100, 2),
            "ev": round(self.ev * 100, 1),
            "win_rate_mc": round(self.win_rate * 100, 1),
            "kelly_stake": round(self.kelly_stake, 3),
            "recommended": self.recommended,
        }


@dataclass
class OptimizationResult:
    """Full optimization result"""
    total_combinations: int
    simulations_run: int
    
    # Top parlays
    top_parlays: List[ParlayResult]
    
    # Summary
    best_2leg: Optional[ParlayResult] = None
    best_3leg: Optional[ParlayResult] = None
    best_4leg: Optional[ParlayResult] = None
    
    # Metadata
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# ============================================================
# CORRELATION DETECTION
# ============================================================

def detect_correlation(leg1: ParlayLeg, leg2: ParlayLeg) -> Tuple[bool, float]:
    """
    Detect correlation between two parlay legs.
    
    Returns:
        (is_correlated, penalty_factor)
    """
    # Same player = heavily correlated
    if leg1.player.lower() == leg2.player.lower():
        return True, SAME_PLAYER_PENALTY
    
    # Same game = moderately correlated
    if leg1.game_id == leg2.game_id:
        # Same team in same game = more correlated
        if leg1.team == leg2.team:
            return True, SAME_GAME_PENALTY
        else:
            return True, SAME_GAME_PENALTY * 0.5  # Opposing teams less correlated
    
    # Correlated stats (goals/assists/points)
    correlated_stats = {"goals", "assists", "points"}
    if leg1.stat.lower() in correlated_stats and leg2.stat.lower() in correlated_stats:
        if leg1.team == leg2.team:
            return True, CORRELATED_STATS_PENALTY
    
    return False, 0.0


def calculate_correlation_penalty(legs: List[ParlayLeg]) -> float:
    """
    Calculate total correlation penalty for a parlay.
    
    Returns:
        Penalty factor (0-1, where 1 = no penalty)
    """
    total_penalty = 0.0
    
    for i, leg1 in enumerate(legs):
        for leg2 in legs[i+1:]:
            is_correlated, penalty = detect_correlation(leg1, leg2)
            if is_correlated:
                total_penalty += penalty
    
    # Cap penalty at 50%
    return max(0.5, 1.0 - total_penalty)


# ============================================================
# PROBABILITY CALCULATIONS
# ============================================================

def calculate_parlay_probability(
    legs: List[ParlayLeg],
    apply_correlation: bool = True,
) -> Tuple[float, float]:
    """
    Calculate parlay probability.
    
    Returns:
        (raw_probability, adjusted_probability)
    """
    if not legs:
        return 0.0, 0.0
    
    # Raw probability = product of individual probabilities
    raw_prob = 1.0
    for leg in legs:
        raw_prob *= leg.probability
    
    # Apply correlation penalty
    if apply_correlation:
        penalty = calculate_correlation_penalty(legs)
        adjusted_prob = raw_prob * penalty
    else:
        adjusted_prob = raw_prob
    
    return raw_prob, adjusted_prob


def calculate_implied_odds(num_legs: int) -> float:
    """
    Calculate implied odds for a parlay.
    
    Assuming each leg is -110 (52.4% implied):
        2-leg: ~3.6:1
        3-leg: ~7.1:1
        4-leg: ~13.3:1
    """
    implied_per_leg = 0.524  # -110 odds
    return (1 / implied_per_leg) ** num_legs


def calculate_ev(probability: float, payout_multiplier: float) -> float:
    """
    Calculate expected value.
    
    EV = (prob × payout) - (1 - prob)
    """
    return (probability * payout_multiplier) - (1 - probability)


def calculate_kelly_stake(probability: float, odds: float) -> float:
    """
    Calculate Kelly Criterion stake.
    
    Kelly = (bp - q) / b
    where b = odds - 1, p = win prob, q = lose prob
    """
    b = odds - 1
    p = probability
    q = 1 - p
    
    if b <= 0:
        return 0.0
    
    kelly = (b * p - q) / b
    return max(0, kelly * KELLY_FRACTION)


# ============================================================
# MONTE CARLO SIMULATION
# ============================================================

def simulate_parlay(
    legs: List[ParlayLeg],
    num_sims: int = NUM_SIMULATIONS,
) -> Tuple[float, float]:
    """
    Monte Carlo simulation of parlay outcome.
    
    Returns:
        (win_rate, avg_payout)
    """
    if not legs:
        return 0.0, 0.0
    
    wins = 0
    total_payout = 0.0
    payout_mult = calculate_implied_odds(len(legs))
    
    for _ in range(num_sims):
        # Simulate each leg
        all_hit = True
        for leg in legs:
            # Random outcome based on probability
            if random.random() > leg.probability:
                all_hit = False
                break
        
        if all_hit:
            wins += 1
            total_payout += payout_mult
    
    win_rate = wins / num_sims
    avg_payout = total_payout / num_sims
    
    return win_rate, avg_payout


def simulate_with_correlation(
    legs: List[ParlayLeg],
    num_sims: int = NUM_SIMULATIONS,
) -> Tuple[float, float]:
    """
    Monte Carlo with correlation modeling.
    
    Correlated legs share a hidden "team performance" factor.
    """
    if not legs:
        return 0.0, 0.0
    
    wins = 0
    total_payout = 0.0
    payout_mult = calculate_implied_odds(len(legs))
    
    # Group legs by game
    games = {}
    for leg in legs:
        if leg.game_id not in games:
            games[leg.game_id] = []
        games[leg.game_id].append(leg)
    
    for _ in range(num_sims):
        all_hit = True
        
        # Generate game-level factors (for correlated outcomes)
        game_factors = {gid: random.gauss(0, 0.1) for gid in games}
        
        for leg in legs:
            # Adjust probability by game factor
            game_factor = game_factors.get(leg.game_id, 0)
            adjusted_prob = min(0.95, max(0.05, leg.probability + game_factor))
            
            if random.random() > adjusted_prob:
                all_hit = False
                break
        
        if all_hit:
            wins += 1
            total_payout += payout_mult
    
    win_rate = wins / num_sims
    avg_payout = total_payout / num_sims
    
    return win_rate, avg_payout


# ============================================================
# PARLAY OPTIMIZER
# ============================================================

class ParlayOptimizer:
    """
    Optimizes parlay combinations using Monte Carlo simulation.
    
    Usage:
        optimizer = ParlayOptimizer()
        optimizer.add_legs(playable_props)
        result = optimizer.optimize(max_legs=4)
    """
    
    def __init__(self, num_sims: int = NUM_SIMULATIONS):
        self.num_sims = num_sims
        self.legs: List[ParlayLeg] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def add_leg(self, leg: ParlayLeg):
        """Add a single leg to the pool"""
        self.legs.append(leg)
    
    def add_legs(self, legs: List[ParlayLeg]):
        """Add multiple legs to the pool"""
        self.legs.extend(legs)
    
    def add_from_props(self, props: List[Dict]):
        """
        Add legs from analyzed props dictionaries.
        
        Props should have: player, team, opponent, stat, line, direction, probability, tier
        """
        for prop in props:
            if prop.get("tier") in ("STRONG", "LEAN") and prop.get("playable", True):
                # Generate game_id
                team = prop.get("team", "UNK")
                opp = prop.get("opponent", "UNK")
                game_id = f"{min(team, opp)}_{max(team, opp)}"
                
                leg = ParlayLeg(
                    player=prop.get("player", "Unknown"),
                    team=team,
                    opponent=opp,
                    game_id=game_id,
                    stat=prop.get("stat", prop.get("stat_type", "sog")),
                    line=prop.get("line", 0),
                    direction=prop.get("direction", "OVER"),
                    probability=prop.get("probability", 0.55) / 100 if prop.get("probability", 0) > 1 else prop.get("probability", 0.55),
                    tier=prop.get("tier", "LEAN"),
                )
                self.legs.append(leg)
    
    def clear_legs(self):
        """Clear all legs"""
        self.legs = []
    
    def _score_parlay(self, legs: List[ParlayLeg]) -> int:
        """Score a parlay based on tier and diversity"""
        tier_score = sum(TIER_SCORES.get(leg.tier, 0) for leg in legs)
        
        # Diversity bonus: unique games
        unique_games = len(set(leg.game_id for leg in legs))
        diversity_score = unique_games * 2
        
        return tier_score + diversity_score
    
    def _evaluate_parlay(self, legs: List[ParlayLeg]) -> ParlayResult:
        """Evaluate a single parlay combination"""
        
        # Calculate probabilities
        raw_prob, adj_prob = calculate_parlay_probability(legs)
        
        # Calculate odds and EV
        implied_odds = calculate_implied_odds(len(legs))
        ev = calculate_ev(adj_prob, implied_odds)
        
        # Score
        tier_score = sum(TIER_SCORES.get(leg.tier, 0) for leg in legs)
        diversity_score = len(set(leg.game_id for leg in legs))
        
        # Kelly stake
        kelly = calculate_kelly_stake(adj_prob, implied_odds)
        
        # Run simulation
        win_rate, avg_payout = simulate_with_correlation(legs, self.num_sims)
        
        # Recommendation
        recommended = (
            ev > MIN_EV_THRESHOLD and
            adj_prob > 0.08 and  # At least 8% hit rate
            kelly > 0.005       # Kelly says bet at least 0.5%
        )
        
        return ParlayResult(
            legs=legs,
            raw_probability=raw_prob,
            adjusted_probability=adj_prob,
            implied_odds=implied_odds,
            ev=ev,
            tier_score=tier_score,
            diversity_score=diversity_score,
            kelly_stake=kelly,
            recommended=recommended,
            win_rate=win_rate,
            avg_payout=avg_payout,
        )
    
    def optimize(
        self,
        min_legs: int = MIN_PARLAY_LEGS,
        max_legs: int = MAX_PARLAY_LEGS,
        top_n: int = 10,
    ) -> OptimizationResult:
        """
        Find optimal parlay combinations.
        
        Args:
            min_legs: Minimum legs per parlay
            max_legs: Maximum legs per parlay
            top_n: Number of top parlays to return
        
        Returns:
            OptimizationResult with best combinations
        """
        if len(self.legs) < min_legs:
            return OptimizationResult(
                total_combinations=0,
                simulations_run=0,
                top_parlays=[],
            )
        
        all_results: List[ParlayResult] = []
        total_combinations = 0
        
        self.logger.info(f"Optimizing parlays with {len(self.legs)} available legs...")
        
        # Evaluate combinations for each parlay size
        for num_legs in range(min_legs, min(max_legs + 1, len(self.legs) + 1)):
            combos = list(combinations(self.legs, num_legs))
            total_combinations += len(combos)
            
            self.logger.info(f"  {num_legs}-leg: {len(combos)} combinations")
            
            for combo in combos:
                result = self._evaluate_parlay(list(combo))
                all_results.append(result)
        
        # Sort by EV (descending)
        all_results.sort(key=lambda x: x.ev, reverse=True)
        
        # Get top N
        top_parlays = all_results[:top_n]
        
        # Find best by leg count
        best_2leg = next((r for r in all_results if len(r.legs) == 2), None)
        best_3leg = next((r for r in all_results if len(r.legs) == 3), None)
        best_4leg = next((r for r in all_results if len(r.legs) == 4), None)
        
        return OptimizationResult(
            total_combinations=total_combinations,
            simulations_run=total_combinations * self.num_sims,
            top_parlays=top_parlays,
            best_2leg=best_2leg,
            best_3leg=best_3leg,
            best_4leg=best_4leg,
        )
    
    def print_results(self, result: OptimizationResult):
        """Print optimization results"""
        print("\n" + "=" * 60)
        print("  NHL PARLAY OPTIMIZER — RESULTS")
        print("=" * 60)
        print(f"  Combinations evaluated: {result.total_combinations:,}")
        print(f"  Simulations run: {result.simulations_run:,}")
        
        # Best by leg count
        if result.best_2leg:
            print("\n  📊 BEST 2-LEG PARLAY")
            self._print_parlay(result.best_2leg)
        
        if result.best_3leg:
            print("\n  📊 BEST 3-LEG PARLAY")
            self._print_parlay(result.best_3leg)
        
        if result.best_4leg:
            print("\n  📊 BEST 4-LEG PARLAY")
            self._print_parlay(result.best_4leg)
        
        # Top recommendations
        recommended = [p for p in result.top_parlays if p.recommended]
        if recommended:
            print(f"\n  ✅ TOP RECOMMENDED PARLAYS ({len(recommended)})")
            print("-" * 60)
            for i, parlay in enumerate(recommended[:5], 1):
                print(f"\n  #{i} ({len(parlay.legs)}-leg | EV: {parlay.ev*100:.1f}%)")
                for leg in parlay.legs:
                    tier_icon = "🟢" if leg.tier == "STRONG" else "🟡"
                    print(f"      {tier_icon} {leg.player}: {leg.stat} {leg.direction} {leg.line}")
                print(f"      Win Rate: {parlay.win_rate*100:.1f}% | Kelly: {parlay.kelly_stake*100:.2f}%")
    
    def _print_parlay(self, parlay: ParlayResult):
        """Print a single parlay"""
        print("-" * 40)
        for leg in parlay.legs:
            tier_icon = "🟢" if leg.tier == "STRONG" else "🟡"
            print(f"    {tier_icon} {leg.player}: {leg.stat} {leg.direction} {leg.line} ({leg.probability*100:.0f}%)")
        
        print(f"\n    Raw Prob: {parlay.raw_probability*100:.2f}%")
        print(f"    Adj Prob: {parlay.adjusted_probability*100:.2f}%")
        print(f"    EV: {parlay.ev*100:.1f}% | Kelly: {parlay.kelly_stake*100:.2f}%")
        print(f"    MC Win Rate: {parlay.win_rate*100:.1f}%")


# ============================================================
# CLI TESTING
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  NHL PARLAY OPTIMIZER — TEST")
    print("=" * 60)
    
    # Create test legs
    test_legs = [
        ParlayLeg("Connor McDavid", "EDM", "CGY", "CGY_EDM", "points", 1.5, "OVER", 0.68, "STRONG"),
        ParlayLeg("Leon Draisaitl", "EDM", "CGY", "CGY_EDM", "goals", 0.5, "OVER", 0.62, "STRONG"),
        ParlayLeg("Auston Matthews", "TOR", "BOS", "BOS_TOR", "goals", 0.5, "OVER", 0.60, "LEAN"),
        ParlayLeg("William Nylander", "TOR", "BOS", "BOS_TOR", "sog", 3.5, "OVER", 0.64, "STRONG"),
        ParlayLeg("Nathan MacKinnon", "COL", "DAL", "COL_DAL", "points", 1.5, "OVER", 0.65, "STRONG"),
        ParlayLeg("Cale Makar", "COL", "DAL", "COL_DAL", "sog", 3.5, "OVER", 0.62, "STRONG"),
        ParlayLeg("Alex Ovechkin", "WSH", "PHI", "PHI_WSH", "sog", 3.5, "OVER", 0.63, "STRONG"),
    ]
    
    optimizer = ParlayOptimizer(num_sims=5000)
    optimizer.add_legs(test_legs)
    
    print(f"\n  📊 Available legs: {len(test_legs)}")
    
    result = optimizer.optimize(min_legs=2, max_legs=4, top_n=10)
    optimizer.print_results(result)
    
    print("\n" + "=" * 60)
