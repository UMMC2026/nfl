"""
NFL Bayesian Priors Module - Phase 2 Implementation
====================================================
Replaces static μ/σ with data-driven priors for more accurate probability estimation.

Key concepts:
1. League-wide priors: Position-based baseline distributions
2. Player-specific posteriors: Shrunk toward league prior based on sample size
3. Matchup adjustments: Factor in opponent defensive rankings
4. Recency weighting: More recent games weighted higher

Formula:
    posterior_μ = (n × player_μ + k × prior_μ) / (n + k)
    posterior_σ = sqrt((n × player_var + k × prior_var) / (n + k))
    
Where k is the prior strength (higher = more shrinkage to league average)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import math


# ==============================================================================
# LEAGUE-WIDE POSITIONAL PRIORS (2023-2024 NFL averages)
# ==============================================================================
# These are baseline distributions by position and stat type
# Values derived from NFL historical averages

@dataclass
class StatPrior:
    """Prior distribution for a stat."""
    mu: float          # Prior mean
    sigma: float       # Prior standard deviation
    min_val: float     # Floor (physical minimum)
    max_val: float     # Ceiling (reasonable maximum)
    prior_strength: int = 5  # Equivalent sample size (higher = more trust in prior)


# NFL Positional Priors (per-game averages)
NFL_PRIORS: Dict[str, Dict[str, StatPrior]] = {
    "QB": {
        "pass_yds": StatPrior(mu=225.0, sigma=65.0, min_val=0, max_val=500, prior_strength=5),
        "pass_tds": StatPrior(mu=1.5, sigma=1.1, min_val=0, max_val=6, prior_strength=5),
        "rush_yds": StatPrior(mu=20.0, sigma=18.0, min_val=0, max_val=100, prior_strength=5),
        "completions": StatPrior(mu=22.0, sigma=6.0, min_val=0, max_val=45, prior_strength=5),
        "interceptions": StatPrior(mu=0.8, sigma=0.9, min_val=0, max_val=4, prior_strength=5),
    },
    "RB": {
        "rush_yds": StatPrior(mu=55.0, sigma=35.0, min_val=0, max_val=200, prior_strength=5),
        "rush_tds": StatPrior(mu=0.4, sigma=0.6, min_val=0, max_val=4, prior_strength=5),
        "receptions": StatPrior(mu=2.5, sigma=2.0, min_val=0, max_val=10, prior_strength=5),
        "rec_yds": StatPrior(mu=20.0, sigma=18.0, min_val=0, max_val=100, prior_strength=5),
        "rush_attempts": StatPrior(mu=12.0, sigma=6.0, min_val=0, max_val=35, prior_strength=5),
    },
    "WR": {
        "rec_yds": StatPrior(mu=55.0, sigma=35.0, min_val=0, max_val=200, prior_strength=5),
        "receptions": StatPrior(mu=4.5, sigma=2.5, min_val=0, max_val=15, prior_strength=5),
        "rec_tds": StatPrior(mu=0.4, sigma=0.55, min_val=0, max_val=3, prior_strength=5),
        "targets": StatPrior(mu=7.0, sigma=3.5, min_val=0, max_val=18, prior_strength=5),
        "rush_yds": StatPrior(mu=5.0, sigma=10.0, min_val=0, max_val=50, prior_strength=5),
    },
    "TE": {
        "rec_yds": StatPrior(mu=35.0, sigma=28.0, min_val=0, max_val=150, prior_strength=5),
        "receptions": StatPrior(mu=3.0, sigma=2.0, min_val=0, max_val=12, prior_strength=5),
        "rec_tds": StatPrior(mu=0.3, sigma=0.5, min_val=0, max_val=3, prior_strength=5),
        "targets": StatPrior(mu=4.5, sigma=2.5, min_val=0, max_val=12, prior_strength=5),
    },
    "K": {
        "fg_made": StatPrior(mu=1.8, sigma=1.2, min_val=0, max_val=6, prior_strength=5),
        "xp_made": StatPrior(mu=2.5, sigma=1.5, min_val=0, max_val=7, prior_strength=5),
        "kicking_points": StatPrior(mu=8.0, sigma=4.5, min_val=0, max_val=20, prior_strength=5),
    },
}

# Elite player adjustments (tier multipliers for known stars)
ELITE_MULTIPLIERS = {
    # Elite QBs: Higher volume
    "Patrick Mahomes": {"pass_yds": 1.15, "pass_tds": 1.20},
    "Josh Allen": {"pass_yds": 1.12, "rush_yds": 2.5, "pass_tds": 1.15},
    "Lamar Jackson": {"pass_yds": 0.95, "rush_yds": 3.0},
    "Joe Burrow": {"pass_yds": 1.18, "pass_tds": 1.15},
    "Jalen Hurts": {"pass_yds": 0.92, "rush_yds": 2.0, "rush_tds": 2.5},
    
    # Elite RBs: Higher volume
    "Derrick Henry": {"rush_yds": 1.40, "rush_attempts": 1.35},
    "Saquon Barkley": {"rush_yds": 1.30, "rec_yds": 1.25},
    "Jonathan Taylor": {"rush_yds": 1.25},
    "Bijan Robinson": {"rush_yds": 1.20, "rec_yds": 1.15},
    "Jahmyr Gibbs": {"rush_yds": 1.15, "rec_yds": 1.30},
    
    # Elite WRs: Higher target share
    "Ja'Marr Chase": {"rec_yds": 1.35, "targets": 1.25, "receptions": 1.20},
    "Justin Jefferson": {"rec_yds": 1.40, "targets": 1.30},
    "Tyreek Hill": {"rec_yds": 1.35, "targets": 1.25},
    "CeeDee Lamb": {"rec_yds": 1.30, "targets": 1.25},
    "A.J. Brown": {"rec_yds": 1.25, "targets": 1.20},
    "Amon-Ra St. Brown": {"rec_yds": 1.20, "receptions": 1.30},
    "Nico Collins": {"rec_yds": 1.25},
    
    # Elite TEs: Higher volume
    "Travis Kelce": {"rec_yds": 1.50, "receptions": 1.40, "targets": 1.45},
    "George Kittle": {"rec_yds": 1.30, "receptions": 1.20},
    "Mark Andrews": {"rec_yds": 1.25, "rec_tds": 1.40},
    "Sam LaPorta": {"rec_yds": 1.20, "targets": 1.15},
    "Dalton Kincaid": {"rec_yds": 1.15, "receptions": 1.20},
}


# ==============================================================================
# OPPONENT DEFENSIVE ADJUSTMENTS
# ==============================================================================
# Multipliers based on opponent strength vs. position
# Values > 1.0 = favorable matchup, < 1.0 = tough matchup

DEFENSIVE_RANKINGS_2024: Dict[str, Dict[str, float]] = {
    # Format: team -> {stat: multiplier}
    # 1.15 = bottom 5 defense (favorable), 0.85 = top 5 defense (tough)
    
    # AFC West
    "KC": {"pass_yds": 0.92, "rush_yds": 0.95, "rec_yds": 0.92},
    "DEN": {"pass_yds": 0.88, "rush_yds": 0.90, "rec_yds": 0.88},
    "LV": {"pass_yds": 1.08, "rush_yds": 1.05, "rec_yds": 1.08},
    "LAC": {"pass_yds": 0.90, "rush_yds": 0.88, "rec_yds": 0.90},
    
    # AFC North
    "BAL": {"pass_yds": 0.90, "rush_yds": 0.85, "rec_yds": 0.90},
    "PIT": {"pass_yds": 0.88, "rush_yds": 0.92, "rec_yds": 0.88},
    "CLE": {"pass_yds": 0.85, "rush_yds": 0.88, "rec_yds": 0.85},
    "CIN": {"pass_yds": 1.05, "rush_yds": 1.08, "rec_yds": 1.05},
    
    # AFC East
    "BUF": {"pass_yds": 0.92, "rush_yds": 0.90, "rec_yds": 0.92},
    "MIA": {"pass_yds": 1.02, "rush_yds": 1.00, "rec_yds": 1.02},
    "NYJ": {"pass_yds": 0.88, "rush_yds": 0.90, "rec_yds": 0.88},
    "NE": {"pass_yds": 1.10, "rush_yds": 1.08, "rec_yds": 1.10},
    
    # AFC South
    "HOU": {"pass_yds": 0.95, "rush_yds": 0.92, "rec_yds": 0.95},
    "IND": {"pass_yds": 1.05, "rush_yds": 1.02, "rec_yds": 1.05},
    "JAX": {"pass_yds": 1.08, "rush_yds": 1.05, "rec_yds": 1.08},
    "TEN": {"pass_yds": 1.02, "rush_yds": 1.00, "rec_yds": 1.02},
    
    # NFC West
    "SF": {"pass_yds": 0.88, "rush_yds": 0.85, "rec_yds": 0.88},
    "LAR": {"pass_yds": 1.00, "rush_yds": 0.98, "rec_yds": 1.00},
    "SEA": {"pass_yds": 1.05, "rush_yds": 1.02, "rec_yds": 1.05},
    "ARI": {"pass_yds": 1.12, "rush_yds": 1.10, "rec_yds": 1.12},
    
    # NFC North
    "DET": {"pass_yds": 1.05, "rush_yds": 0.95, "rec_yds": 1.05},
    "GB": {"pass_yds": 0.95, "rush_yds": 0.92, "rec_yds": 0.95},
    "MIN": {"pass_yds": 0.90, "rush_yds": 0.92, "rec_yds": 0.90},
    "CHI": {"pass_yds": 1.00, "rush_yds": 0.98, "rec_yds": 1.00},
    
    # NFC East
    "PHI": {"pass_yds": 0.88, "rush_yds": 0.85, "rec_yds": 0.88},
    "DAL": {"pass_yds": 0.92, "rush_yds": 0.95, "rec_yds": 0.92},
    "WSH": {"pass_yds": 1.08, "rush_yds": 1.05, "rec_yds": 1.08},
    "NYG": {"pass_yds": 1.10, "rush_yds": 1.08, "rec_yds": 1.10},
    
    # NFC South
    "TB": {"pass_yds": 1.02, "rush_yds": 1.00, "rec_yds": 1.02},
    "NO": {"pass_yds": 0.95, "rush_yds": 0.92, "rec_yds": 0.95},
    "ATL": {"pass_yds": 1.05, "rush_yds": 1.02, "rec_yds": 1.05},
    "CAR": {"pass_yds": 1.15, "rush_yds": 1.12, "rec_yds": 1.15},
}


@dataclass
class BayesianPosterior:
    """Result of Bayesian prior update."""
    mu: float               # Posterior mean
    sigma: float            # Posterior standard deviation
    prior_mu: float         # Original prior mean
    prior_sigma: float      # Original prior standard deviation
    sample_mu: float        # Sample mean (from player history)
    sample_sigma: float     # Sample standard deviation
    sample_size: int        # Number of games
    shrinkage: float        # How much toward prior (0-1)
    matchup_adj: float      # Opponent adjustment applied
    elite_adj: float        # Elite player adjustment applied
    confidence: str         # "low", "medium", "high" based on sample size


class NFLBayesianPrior:
    """
    Bayesian prior estimation for NFL player stats.
    
    Usage:
        engine = NFLBayesianPrior()
        posterior = engine.get_posterior(
            player="Josh Allen",
            position="QB",
            stat="pass_yds",
            recent_values=[285, 310, 245, 290, 275],
            opponent="KC"
        )
        # Use posterior.mu and posterior.sigma in prob_hit()
    """
    
    def __init__(self, role_mapping_path: Optional[str] = None):
        self._role_mapping = {}
        if role_mapping_path:
            self._load_role_mapping(role_mapping_path)
    
    def _load_role_mapping(self, path: str):
        """Load player classifications from JSON."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self._role_mapping = data.get("player_classifications", {})
        except Exception:
            pass
    
    def get_player_info(self, player: str) -> Tuple[str, str]:
        """Get team and position for a player."""
        info = self._role_mapping.get(player, {})
        return info.get("team", "UNK"), info.get("position", "UNK")
    
    def get_prior(self, position: str, stat: str) -> StatPrior:
        """Get league-wide prior for position/stat combination."""
        position_priors = NFL_PRIORS.get(position.upper(), NFL_PRIORS.get("WR", {}))
        return position_priors.get(stat, StatPrior(mu=50.0, sigma=30.0, min_val=0, max_val=200))
    
    def get_elite_adjustment(self, player: str, stat: str) -> float:
        """Get elite player multiplier for a stat."""
        player_adj = ELITE_MULTIPLIERS.get(player, {})
        return player_adj.get(stat, 1.0)
    
    def get_matchup_adjustment(self, opponent: str, stat: str) -> float:
        """Get defensive matchup adjustment."""
        team_def = DEFENSIVE_RANKINGS_2024.get(opponent.upper(), {})
        return team_def.get(stat, 1.0)
    
    def get_posterior(
        self,
        player: str,
        position: str,
        stat: str,
        recent_values: List[float],
        opponent: Optional[str] = None,
        recency_weight: bool = True
    ) -> BayesianPosterior:
        """
        Compute Bayesian posterior for player stat distribution.
        
        Args:
            player: Player name
            position: Position (QB, RB, WR, TE, K)
            stat: Stat type (pass_yds, rush_yds, etc.)
            recent_values: List of recent game values (most recent first)
            opponent: Opponent team code (for matchup adjustment)
            recency_weight: Whether to weight recent games more
            
        Returns:
            BayesianPosterior with updated mu and sigma
        """
        # Get prior
        prior = self.get_prior(position, stat)
        
        # Calculate sample statistics with optional recency weighting
        n = len(recent_values)
        if n == 0:
            # No data: use prior directly
            return BayesianPosterior(
                mu=prior.mu,
                sigma=prior.sigma,
                prior_mu=prior.mu,
                prior_sigma=prior.sigma,
                sample_mu=prior.mu,
                sample_sigma=prior.sigma,
                sample_size=0,
                shrinkage=1.0,
                matchup_adj=1.0,
                elite_adj=1.0,
                confidence="low"
            )
        
        # Calculate weighted sample mean and variance
        if recency_weight and n >= 3:
            # Exponential decay: recent games weighted more
            weights = [0.9 ** i for i in range(n)]
            total_weight = sum(weights)
            sample_mu = sum(w * v for w, v in zip(weights, recent_values)) / total_weight
            sample_var = sum(w * (v - sample_mu) ** 2 for w, v in zip(weights, recent_values)) / total_weight
        else:
            sample_mu = sum(recent_values) / n
            sample_var = sum((v - sample_mu) ** 2 for v in recent_values) / max(n - 1, 1)
        
        sample_sigma = math.sqrt(max(sample_var, 1e-6))
        
        # Bayesian update (conjugate normal-normal)
        k = prior.prior_strength
        posterior_mu = (n * sample_mu + k * prior.mu) / (n + k)
        
        # Pooled variance estimate
        prior_var = prior.sigma ** 2
        posterior_var = (n * sample_var + k * prior_var) / (n + k)
        posterior_sigma = math.sqrt(max(posterior_var, 1e-6))
        
        # Calculate shrinkage factor
        shrinkage = k / (n + k)
        
        # Apply elite player adjustment to mean
        elite_adj = self.get_elite_adjustment(player, stat)
        posterior_mu *= elite_adj
        
        # Apply matchup adjustment
        matchup_adj = 1.0
        if opponent:
            matchup_adj = self.get_matchup_adjustment(opponent, stat)
            posterior_mu *= matchup_adj
        
        # Clamp to physical bounds
        posterior_mu = max(prior.min_val, min(prior.max_val, posterior_mu))
        
        # Confidence level based on sample size
        if n >= 10:
            confidence = "high"
        elif n >= 5:
            confidence = "medium"
        else:
            confidence = "low"
        
        return BayesianPosterior(
            mu=posterior_mu,
            sigma=posterior_sigma,
            prior_mu=prior.mu,
            prior_sigma=prior.sigma,
            sample_mu=sample_mu,
            sample_sigma=sample_sigma,
            sample_size=n,
            shrinkage=shrinkage,
            matchup_adj=matchup_adj,
            elite_adj=elite_adj,
            confidence=confidence
        )
    
    def format_prior_report(
        self,
        player: str,
        position: str,
        stat: str,
        recent_values: List[float],
        opponent: Optional[str] = None
    ) -> str:
        """Generate human-readable prior analysis report."""
        posterior = self.get_posterior(player, position, stat, recent_values, opponent)
        
        lines = [
            f"{'=' * 60}",
            f"BAYESIAN PRIOR ANALYSIS: {player}",
            f"{'=' * 60}",
            f"Position: {position} | Stat: {stat}",
            f"Opponent: {opponent or 'N/A'}",
            f"",
            f"LEAGUE PRIOR:",
            f"  μ = {posterior.prior_mu:.1f}, σ = {posterior.prior_sigma:.1f}",
            f"",
            f"PLAYER SAMPLE (n={posterior.sample_size}):",
            f"  μ = {posterior.sample_mu:.1f}, σ = {posterior.sample_sigma:.1f}",
            f"  Games: {recent_values[:5]}{'...' if len(recent_values) > 5 else ''}",
            f"",
            f"POSTERIOR (UPDATED):",
            f"  μ = {posterior.mu:.1f}, σ = {posterior.sigma:.1f}",
            f"  Shrinkage: {posterior.shrinkage:.0%} toward prior",
            f"  Elite adj: {posterior.elite_adj:.2f}x",
            f"  Matchup adj: {posterior.matchup_adj:.2f}x",
            f"  Confidence: {posterior.confidence.upper()}",
            f"{'=' * 60}",
        ]
        
        return "\n".join(lines)


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def get_nfl_posterior(
    player: str,
    position: str,
    stat: str,
    recent_values: List[float],
    opponent: Optional[str] = None
) -> Tuple[float, float, str]:
    """
    Quick function to get posterior mu/sigma for NFL player.
    
    Returns:
        (posterior_mu, posterior_sigma, confidence_level)
    """
    engine = NFLBayesianPrior()
    posterior = engine.get_posterior(player, position, stat, recent_values, opponent)
    return (posterior.mu, posterior.sigma, posterior.confidence)


def prob_hit_with_prior(
    player: str,
    position: str,
    stat: str,
    line: float,
    direction: str,
    recent_values: List[float],
    opponent: Optional[str] = None
) -> Tuple[float, BayesianPosterior]:
    """
    Calculate P(hit) using Bayesian priors.
    
    Returns:
        (probability, posterior_object)
    """
    engine = NFLBayesianPrior()
    posterior = engine.get_posterior(player, position, stat, recent_values, opponent)
    
    # Normal CDF calculation
    z = (line - posterior.mu) / (posterior.sigma * math.sqrt(2.0))
    p_under = 0.5 * (1.0 + math.erf(z))
    
    if direction.lower() == "higher":
        p_hit = 1.0 - p_under
    elif direction.lower() == "lower":
        p_hit = p_under
    else:
        raise ValueError("direction must be 'higher' or 'lower'")
    
    return (p_hit, posterior)


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("NFL Bayesian Priors - Phase 2 Test")
    print("=" * 60)
    
    engine = NFLBayesianPrior()
    
    # Test 1: Josh Allen pass yards vs KC
    print("\n[Test 1] Josh Allen Pass Yards vs KC")
    recent = [285, 310, 245, 290, 275, 305, 260, 280]
    posterior = engine.get_posterior("Josh Allen", "QB", "pass_yds", recent, "KC")
    print(f"  Prior: μ={posterior.prior_mu:.1f}, σ={posterior.prior_sigma:.1f}")
    print(f"  Sample: μ={posterior.sample_mu:.1f} (n={posterior.sample_size})")
    print(f"  Posterior: μ={posterior.mu:.1f}, σ={posterior.sigma:.1f}")
    print(f"  Shrinkage: {posterior.shrinkage:.1%}, Elite: {posterior.elite_adj}x, Matchup: {posterior.matchup_adj}x")
    
    # Test 2: Derrick Henry rush yards vs BUF (elite RB)
    print("\n[Test 2] Derrick Henry Rush Yards vs BUF")
    recent = [105, 120, 85, 95, 110, 130, 75]
    posterior = engine.get_posterior("Derrick Henry", "RB", "rush_yds", recent, "BUF")
    print(f"  Prior: μ={posterior.prior_mu:.1f}, σ={posterior.prior_sigma:.1f}")
    print(f"  Sample: μ={posterior.sample_mu:.1f} (n={posterior.sample_size})")
    print(f"  Posterior: μ={posterior.mu:.1f}, σ={posterior.sigma:.1f}")
    print(f"  Elite adj: {posterior.elite_adj}x (Derrick Henry boost)")
    
    # Test 3: Travis Kelce rec yards (elite TE)
    print("\n[Test 3] Travis Kelce Rec Yards vs BUF")
    recent = [75, 82, 65, 90, 55, 78]
    posterior = engine.get_posterior("Travis Kelce", "TE", "rec_yds", recent, "BUF")
    print(f"  Prior: μ={posterior.prior_mu:.1f}, σ={posterior.prior_sigma:.1f}")
    print(f"  Sample: μ={posterior.sample_mu:.1f} (n={posterior.sample_size})")
    print(f"  Posterior: μ={posterior.mu:.1f}, σ={posterior.sigma:.1f}")
    print(f"  Elite adj: {posterior.elite_adj}x (Kelce boost)")
    
    # Test 4: Full report
    print("\n" + engine.format_prior_report("Josh Allen", "QB", "pass_yds", 
          [285, 310, 245, 290, 275], "KC"))
    
    # Test 5: P(hit) calculation
    print("\n[Test 5] P(hit) with Bayesian Prior")
    p_hit, post = prob_hit_with_prior(
        "Josh Allen", "QB", "pass_yds",
        line=265.5, direction="higher",
        recent_values=[285, 310, 245, 290, 275],
        opponent="KC"
    )
    print(f"  Line: 265.5 Pass Yds Higher")
    print(f"  Posterior: μ={post.mu:.1f}, σ={post.sigma:.1f}")
    print(f"  P(hit): {p_hit:.1%}")
