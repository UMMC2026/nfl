"""
NFL Correlation Engine - Phase 1 Implementation
===============================================
Fixes the independence assumption: P(A) × P(B) → P(A,B | game_state, usage, script)

This module provides:
1. Covariance schema for NFL stat pairs
2. Joint probability calculation with correlation adjustment
3. Same-game parlay (SGP) correlation penalties
4. Monte Carlo joint sampling for correlated outcomes

Key insight: NFL props are NOT independent. 
- QB pass_yds ↔ WR rec_yds (highly correlated within team)
- RB rush_yds ↔ game script (blowout = more runs)
- Opposing QB props (if one dominates, other may not)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Tuple
import math
import random


class CorrelationType(Enum):
    """Types of correlation relationships in NFL."""
    POSITIVE_HIGH = "+++"      # ρ ≈ 0.7-0.9 (QB→WR1 on same team)
    POSITIVE_MODERATE = "++"   # ρ ≈ 0.4-0.6 (RB→TE on same team)
    POSITIVE_WEAK = "+"        # ρ ≈ 0.2-0.3 (teammates general)
    INDEPENDENT = "0"          # ρ ≈ 0 (different games)
    NEGATIVE_WEAK = "-"        # ρ ≈ -0.2 to -0.3 (competing for touches)
    NEGATIVE_MODERATE = "--"   # ρ ≈ -0.4 to -0.6 (RB vs passing game)
    NEGATIVE_HIGH = "---"      # ρ ≈ -0.7 to -0.9 (opposite game scripts)


@dataclass
class CovarianceEntry:
    """Single entry in the covariance schema."""
    stat1: str
    stat2: str
    correlation_type: CorrelationType
    rho: float  # Actual correlation coefficient [-1, 1]
    context: str  # When this applies
    parlay_penalty: float  # % reduction to combined probability


# ==============================================================================
# NFL COVARIANCE SCHEMA
# ==============================================================================
# This is the "load-bearing" data structure. All correlation logic flows from here.

NFL_SAME_PLAYER_COVARIANCE = {
    # Same player, different stats
    ("pass_yds", "completions"): CovarianceEntry("pass_yds", "completions", CorrelationType.POSITIVE_HIGH, 0.85, "More completions = more yards", 0.12),
    ("pass_yds", "pass_tds"): CovarianceEntry("pass_yds", "pass_tds", CorrelationType.POSITIVE_MODERATE, 0.50, "High volume can lead to TDs", 0.08),
    ("rush_yds", "rush_tds"): CovarianceEntry("rush_yds", "rush_tds", CorrelationType.POSITIVE_MODERATE, 0.45, "Goal-line work correlates", 0.07),
    ("rec_yds", "receptions"): CovarianceEntry("rec_yds", "receptions", CorrelationType.POSITIVE_HIGH, 0.80, "More catches = more yards", 0.10),
    ("rec_yds", "rec_tds"): CovarianceEntry("rec_yds", "rec_tds", CorrelationType.POSITIVE_MODERATE, 0.40, "High target share", 0.06),
    ("rush_yds", "rec_yds"): CovarianceEntry("rush_yds", "rec_yds", CorrelationType.POSITIVE_WEAK, 0.25, "Dual-threat backs", 0.04),
    ("pass_yds", "rush_yds"): CovarianceEntry("pass_yds", "rush_yds", CorrelationType.NEGATIVE_WEAK, -0.20, "Scramble QBs trade off", 0.03),
    ("targets", "rec_yds"): CovarianceEntry("targets", "rec_yds", CorrelationType.POSITIVE_HIGH, 0.75, "Targets drive opportunity", 0.10),
    ("targets", "receptions"): CovarianceEntry("targets", "receptions", CorrelationType.POSITIVE_HIGH, 0.85, "Direct dependency", 0.12),
}

NFL_SAME_TEAM_COVARIANCE = {
    # QB → WR/TE correlations (high positive)
    ("pass_yds", "rec_yds"): CovarianceEntry("pass_yds", "rec_yds", CorrelationType.POSITIVE_HIGH, 0.70, "QB air yards → receiver yards", 0.10),
    ("pass_tds", "rec_tds"): CovarianceEntry("pass_tds", "rec_tds", CorrelationType.POSITIVE_HIGH, 0.80, "QB TD → receiver TD", 0.12),
    ("completions", "receptions"): CovarianceEntry("completions", "receptions", CorrelationType.POSITIVE_MODERATE, 0.55, "Completions split among receivers", 0.07),
    
    # RB vs Passing Game (negative - game script)
    ("rush_yds", "pass_yds"): CovarianceEntry("rush_yds", "pass_yds", CorrelationType.NEGATIVE_WEAK, -0.25, "Run-heavy script vs pass-heavy", 0.04),
    ("rush_attempts", "pass_yds"): CovarianceEntry("rush_attempts", "pass_yds", CorrelationType.NEGATIVE_MODERATE, -0.40, "More runs = fewer pass attempts", 0.06),
    
    # Receiver Competition (negative - target share)
    ("rec_yds", "rec_yds"): CovarianceEntry("rec_yds", "rec_yds", CorrelationType.NEGATIVE_WEAK, -0.20, "WR1 vs WR2 compete for targets", 0.03),
    ("receptions", "receptions"): CovarianceEntry("receptions", "receptions", CorrelationType.NEGATIVE_WEAK, -0.25, "Finite completions to split", 0.04),
    ("targets", "targets"): CovarianceEntry("targets", "targets", CorrelationType.NEGATIVE_WEAK, -0.30, "Target share competition", 0.05),
    
    # RB Committee (negative - touches)
    ("rush_yds", "rush_yds"): CovarianceEntry("rush_yds", "rush_yds", CorrelationType.NEGATIVE_MODERATE, -0.45, "RB1 vs RB2 split carries", 0.06),
    ("rush_attempts", "rush_attempts"): CovarianceEntry("rush_attempts", "rush_attempts", CorrelationType.NEGATIVE_MODERATE, -0.50, "Committee split", 0.07),
}

NFL_OPPOSING_TEAM_COVARIANCE = {
    # Game script - blowout effects
    ("pass_yds", "pass_yds"): CovarianceEntry("pass_yds", "pass_yds", CorrelationType.NEGATIVE_WEAK, -0.15, "Winner runs, loser passes", 0.02),
    ("rush_yds", "pass_yds"): CovarianceEntry("rush_yds", "pass_yds", CorrelationType.POSITIVE_WEAK, 0.20, "Winning team runs, losing QB passes", 0.03),
    
    # Shootout - both QBs benefit
    ("pass_tds", "pass_tds"): CovarianceEntry("pass_tds", "pass_tds", CorrelationType.POSITIVE_MODERATE, 0.40, "Shootout benefits both", 0.06),
}

# Special case: Anytime TD props
NFL_TD_CORRELATIONS = {
    "same_team_td_boost": 0.15,      # If team scores a lot, multiple TDs likely
    "opposing_team_td_penalty": 0.05, # Defensive dominance hurts both
    "redzone_rb_te_correlation": 0.35, # RB and TE compete for goal-line TDs
}


@dataclass
class NFLCorrelationResult:
    """Result of correlation analysis between two picks."""
    pick1_key: str  # "player|stat"
    pick2_key: str
    correlation_type: CorrelationType
    rho: float
    penalty: float
    reason: str
    badge: str


class NFLCorrelationEngine:
    """
    Main engine for NFL prop correlation analysis.
    
    Usage:
        engine = NFLCorrelationEngine()
        results = engine.analyze_parlay(picks)
        adjusted_prob = engine.joint_probability(picks)
    """
    
    def __init__(self):
        self._cache: Dict[str, NFLCorrelationResult] = {}
    
    def get_correlation(
        self,
        player1: str, team1: str, stat1: str,
        player2: str, team2: str, stat2: str,
        matchup_info: Optional[dict] = None
    ) -> NFLCorrelationResult:
        """
        Get correlation between two NFL props.
        
        Args:
            player1, team1, stat1: First pick details
            player2, team2, stat2: Second pick details
            matchup_info: Optional dict with game_id, home_team, away_team
            
        Returns:
            NFLCorrelationResult with correlation data
        """
        key = f"{player1}|{stat1}|{player2}|{stat2}"
        
        # Check cache
        if key in self._cache:
            return self._cache[key]
        
        # Determine relationship type
        same_player = player1.lower() == player2.lower()
        same_team = team1 == team2
        same_game = self._check_same_game(team1, team2, matchup_info)
        
        result = None
        
        if same_player:
            result = self._get_same_player_correlation(player1, stat1, stat2)
        elif same_team:
            result = self._get_same_team_correlation(player1, stat1, player2, stat2, team1)
        elif same_game:
            result = self._get_opposing_team_correlation(player1, team1, stat1, player2, team2, stat2)
        else:
            # Different games = independent
            result = NFLCorrelationResult(
                pick1_key=f"{player1}|{stat1}",
                pick2_key=f"{player2}|{stat2}",
                correlation_type=CorrelationType.INDEPENDENT,
                rho=0.0,
                penalty=0.0,
                reason="Different games",
                badge=""
            )
        
        self._cache[key] = result
        return result
    
    def _check_same_game(self, team1: str, team2: str, matchup_info: Optional[dict]) -> bool:
        """Check if two teams are in the same game."""
        if matchup_info:
            game_teams = {matchup_info.get("home_team"), matchup_info.get("away_team")}
            return team1 in game_teams and team2 in game_teams
        # Heuristic: if we don't have matchup info, assume same game if teams are different
        # This is conservative (applies penalties when unsure)
        return team1 != team2
    
    def _get_same_player_correlation(self, player: str, stat1: str, stat2: str) -> NFLCorrelationResult:
        """Get correlation for same player, different stats."""
        key = tuple(sorted([stat1, stat2]))
        
        if key in NFL_SAME_PLAYER_COVARIANCE:
            entry = NFL_SAME_PLAYER_COVARIANCE[key]
            return NFLCorrelationResult(
                pick1_key=f"{player}|{stat1}",
                pick2_key=f"{player}|{stat2}",
                correlation_type=entry.correlation_type,
                rho=entry.rho,
                penalty=entry.parlay_penalty,
                reason=f"{player}: {entry.context}",
                badge=f"🔗{entry.correlation_type.value}"
            )
        
        # Default: weak positive for same player
        return NFLCorrelationResult(
            pick1_key=f"{player}|{stat1}",
            pick2_key=f"{player}|{stat2}",
            correlation_type=CorrelationType.POSITIVE_WEAK,
            rho=0.15,
            penalty=0.02,
            reason=f"{player}: same player weak correlation",
            badge="🔗+"
        )
    
    def _get_same_team_correlation(
        self, player1: str, stat1: str, player2: str, stat2: str, team: str
    ) -> NFLCorrelationResult:
        """Get correlation for same team, different players."""
        key = tuple(sorted([stat1, stat2]))
        
        if key in NFL_SAME_TEAM_COVARIANCE:
            entry = NFL_SAME_TEAM_COVARIANCE[key]
            return NFLCorrelationResult(
                pick1_key=f"{player1}|{stat1}",
                pick2_key=f"{player2}|{stat2}",
                correlation_type=entry.correlation_type,
                rho=entry.rho,
                penalty=entry.parlay_penalty,
                reason=f"{team}: {entry.context}",
                badge=f"⚠️{entry.correlation_type.value}"
            )
        
        # Default: weak positive for teammates
        return NFLCorrelationResult(
            pick1_key=f"{player1}|{stat1}",
            pick2_key=f"{player2}|{stat2}",
            correlation_type=CorrelationType.POSITIVE_WEAK,
            rho=0.10,
            penalty=0.02,
            reason=f"{team}: teammate weak correlation",
            badge="⚠️+"
        )
    
    def _get_opposing_team_correlation(
        self, player1: str, team1: str, stat1: str,
        player2: str, team2: str, stat2: str
    ) -> NFLCorrelationResult:
        """Get correlation for opposing teams in same game."""
        key = tuple(sorted([stat1, stat2]))
        
        if key in NFL_OPPOSING_TEAM_COVARIANCE:
            entry = NFL_OPPOSING_TEAM_COVARIANCE[key]
            return NFLCorrelationResult(
                pick1_key=f"{player1}|{stat1}",
                pick2_key=f"{player2}|{stat2}",
                correlation_type=entry.correlation_type,
                rho=entry.rho,
                penalty=entry.parlay_penalty,
                reason=f"{team1}@{team2}: {entry.context}",
                badge=f"↔️{entry.correlation_type.value}"
            )
        
        # Default: independent for different teams, different stats
        return NFLCorrelationResult(
            pick1_key=f"{player1}|{stat1}",
            pick2_key=f"{player2}|{stat2}",
            correlation_type=CorrelationType.INDEPENDENT,
            rho=0.0,
            penalty=0.0,
            reason="Different positions, minimal correlation",
            badge=""
        )
    
    def analyze_parlay(self, picks: List[dict]) -> Tuple[float, List[NFLCorrelationResult]]:
        """
        Analyze all correlations in a parlay.
        
        Args:
            picks: List of pick dicts with player, team, stat keys
            
        Returns:
            (total_penalty, list of correlation results)
        """
        results = []
        total_penalty = 0.0
        
        # Check all pairs
        for i, p1 in enumerate(picks):
            for p2 in picks[i+1:]:
                result = self.get_correlation(
                    p1.get("player", ""), p1.get("team", ""), p1.get("stat", ""),
                    p2.get("player", ""), p2.get("team", ""), p2.get("stat", "")
                )
                
                if result.penalty > 0:
                    results.append(result)
                    total_penalty += result.penalty
        
        return (total_penalty, results)
    
    def joint_probability(self, picks: List[dict], base_probs: List[float]) -> float:
        """
        Calculate joint probability with correlation adjustment.
        
        Instead of P(A) × P(B) × P(C), we compute:
        P(A,B,C) = P(A) × P(B) × P(C) × (1 - correlation_penalty)
        
        This is a simplified model. Full implementation would use
        multivariate normal CDF or copula methods.
        
        Args:
            picks: List of picks
            base_probs: Individual P(hit) for each pick
            
        Returns:
            Adjusted joint probability
        """
        if len(picks) != len(base_probs):
            raise ValueError("picks and base_probs must have same length")
        
        # Independent probability
        independent_prob = 1.0
        for p in base_probs:
            independent_prob *= p
        
        # Get correlation penalty
        total_penalty, _ = self.analyze_parlay(picks)
        
        # Apply penalty (capped at 50% reduction)
        penalty_multiplier = max(0.5, 1.0 - total_penalty)
        
        return independent_prob * penalty_multiplier
    
    def monte_carlo_joint_sample(
        self,
        picks: List[dict],
        base_probs: List[float],
        n_samples: int = 10000
    ) -> float:
        """
        Monte Carlo estimation of joint probability with correlations.
        
        Uses correlated Bernoulli sampling based on correlation matrix.
        More accurate than penalty-based method for complex parlays.
        
        Args:
            picks: List of picks
            base_probs: Individual P(hit) for each pick
            n_samples: Number of Monte Carlo samples
            
        Returns:
            Estimated joint probability
        """
        n = len(picks)
        if n != len(base_probs):
            raise ValueError("picks and base_probs must have same length")
        
        # Build correlation matrix
        rho_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            rho_matrix[i][i] = 1.0
            for j in range(i+1, n):
                result = self.get_correlation(
                    picks[i].get("player", ""), picks[i].get("team", ""), picks[i].get("stat", ""),
                    picks[j].get("player", ""), picks[j].get("team", ""), picks[j].get("stat", "")
                )
                rho_matrix[i][j] = result.rho
                rho_matrix[j][i] = result.rho
        
        # Monte Carlo sampling with correlation
        hits = 0
        for _ in range(n_samples):
            # Generate correlated uniform random variables using Gaussian copula
            z = [random.gauss(0, 1) for _ in range(n)]
            
            # Apply correlation (simplified - proper method uses Cholesky decomposition)
            for i in range(n):
                for j in range(i):
                    z[i] += rho_matrix[i][j] * z[j] * 0.3  # Scaled influence
            
            # Convert to outcomes
            all_hit = True
            for i in range(n):
                # Use quantile to determine hit/miss
                threshold = self._norm_cdf_inverse(1 - base_probs[i])
                if z[i] < threshold:
                    all_hit = False
                    break
            
            if all_hit:
                hits += 1
        
        return hits / n_samples
    
    @staticmethod
    def _norm_cdf_inverse(p: float) -> float:
        """Approximate inverse normal CDF (probit function)."""
        if p <= 0:
            return -5.0
        if p >= 1:
            return 5.0
        
        # Approximation using Abramowitz and Stegun
        a = [
            -3.969683028665376e+01,
            2.209460984245205e+02,
            -2.759285104469687e+02,
            1.383577518672690e+02,
            -3.066479806614716e+01,
            2.506628277459239e+00
        ]
        b = [
            -5.447609879822406e+01,
            1.615858368580409e+02,
            -1.556989798598866e+02,
            6.680131188771972e+01,
            -1.328068155288572e+01
        ]
        c = [
            -7.784894002430293e-03,
            -3.223964580411365e-01,
            -2.400758277161838e+00,
            -2.549732539343734e+00,
            4.374664141464968e+00,
            2.938163982698783e+00
        ]
        d = [
            7.784695709041462e-03,
            3.224671290700398e-01,
            2.445134137142996e+00,
            3.754408661907416e+00
        ]
        
        p_low = 0.02425
        p_high = 1 - p_low
        
        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                   ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
                   (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
        else:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                    ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    
    def format_correlation_report(self, picks: List[dict]) -> str:
        """Generate human-readable correlation report."""
        total_penalty, results = self.analyze_parlay(picks)
        
        lines = [
            "=" * 60,
            "NFL CORRELATION ANALYSIS",
            "=" * 60,
            f"Picks analyzed: {len(picks)}",
            f"Total penalty: -{total_penalty:.1%}",
            "",
            "Correlations detected:",
            "-" * 60
        ]
        
        if not results:
            lines.append("  ✓ No significant correlations - picks appear independent")
        else:
            for r in sorted(results, key=lambda x: -x.penalty):
                lines.append(f"  {r.badge} {r.reason}")
                lines.append(f"       ρ={r.rho:.2f}, penalty={r.penalty:.1%}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def check_nfl_correlations(picks: List[dict]) -> Tuple[float, List[str]]:
    """
    Quick correlation check for NFL parlay.
    
    Returns:
        (penalty_multiplier, warning_messages)
    """
    engine = NFLCorrelationEngine()
    total_penalty, results = engine.analyze_parlay(picks)
    
    warnings = [f"{r.badge} {r.reason}" for r in results if r.penalty > 0.02]
    
    return (1.0 - total_penalty, warnings)


def get_joint_probability(picks: List[dict], base_probs: List[float], method: str = "penalty") -> float:
    """
    Calculate joint probability with correlation adjustment.
    
    Args:
        picks: List of pick dicts
        base_probs: Individual hit probabilities
        method: "penalty" (fast) or "monte_carlo" (accurate)
        
    Returns:
        Adjusted joint probability
    """
    engine = NFLCorrelationEngine()
    
    if method == "monte_carlo":
        return engine.monte_carlo_joint_sample(picks, base_probs)
    else:
        return engine.joint_probability(picks, base_probs)


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("NFL Correlation Engine - Phase 1 Test")
    print("=" * 60)
    
    # Test picks - KC vs BUF game
    picks = [
        {"player": "Patrick Mahomes", "team": "KC", "stat": "pass_yds"},
        {"player": "Travis Kelce", "team": "KC", "stat": "rec_yds"},
        {"player": "Josh Allen", "team": "BUF", "stat": "pass_yds"},
        {"player": "James Cook", "team": "BUF", "stat": "rush_yds"},
    ]
    
    base_probs = [0.55, 0.58, 0.52, 0.60]
    
    engine = NFLCorrelationEngine()
    
    # Full report
    print(engine.format_correlation_report(picks))
    
    # Probability calculations
    independent = 1.0
    for p in base_probs:
        independent *= p
    
    adjusted = engine.joint_probability(picks, base_probs)
    mc_estimate = engine.monte_carlo_joint_sample(picks, base_probs, n_samples=10000)
    
    print(f"\nJoint Probability Estimates:")
    print(f"  Independent (naive): {independent:.4f}")
    print(f"  Penalty-adjusted:    {adjusted:.4f}")
    print(f"  Monte Carlo:         {mc_estimate:.4f}")
    
    # Quick check function
    print("\n" + "=" * 60)
    print("Quick check function test:")
    mult, warnings = check_nfl_correlations(picks)
    print(f"  Multiplier: {mult:.2%}")
    print(f"  Warnings: {warnings}")
