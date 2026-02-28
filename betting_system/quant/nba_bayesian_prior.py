#!/usr/bin/env python3
"""
NBA Bayesian Priors Module - Phase 2 Implementation
====================================================
Implements Bayesian shrinkage for NBA player prop projections.

Key concepts:
1. Position-based priors: Baseline distributions by role
2. Usage-based adjustments: High usage = higher variance
3. Archetype-specific priors: Star vs role player baselines
4. Sample size shrinkage: Less data = more regression to prior

Formula:
    posterior_μ = (n × player_μ + k × prior_μ) / (n + k)
    posterior_σ = sqrt((n × player_var + k × prior_var) / (n + k))
    
Where k is the prior strength (higher = more shrinkage to league average)

Version: 2.1.0
Created: 2026-02-04
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


# ==============================================================================
# NBA POSITIONAL PRIORS (2025-26 season averages)
# ==============================================================================

@dataclass
class StatPrior:
    """Prior distribution for a stat."""
    mu: float          # Prior mean
    sigma: float       # Prior standard deviation
    min_val: float     # Floor
    max_val: float     # Ceiling
    prior_strength: int = 5  # Equivalent sample size
    distribution: str = "normal"  # normal, nbinom, poisson


# NBA Positional Priors (per-game averages by primary position)
NBA_PRIORS: Dict[str, Dict[str, StatPrior]] = {
    "PG": {
        "PTS": StatPrior(mu=15.0, sigma=6.0, min_val=0, max_val=50, prior_strength=5),
        "AST": StatPrior(mu=6.0, sigma=2.5, min_val=0, max_val=18, prior_strength=5, distribution="nbinom"),
        "REB": StatPrior(mu=4.0, sigma=1.5, min_val=0, max_val=12, prior_strength=5, distribution="nbinom"),
        "3PM": StatPrior(mu=2.0, sigma=1.2, min_val=0, max_val=10, prior_strength=5, distribution="nbinom"),
        "STL": StatPrior(mu=1.2, sigma=0.8, min_val=0, max_val=5, prior_strength=5, distribution="nbinom"),
        "BLK": StatPrior(mu=0.3, sigma=0.4, min_val=0, max_val=3, prior_strength=5, distribution="nbinom"),
        "PRA": StatPrior(mu=25.0, sigma=8.0, min_val=0, max_val=70, prior_strength=5),
    },
    "SG": {
        "PTS": StatPrior(mu=14.0, sigma=6.0, min_val=0, max_val=50, prior_strength=5),
        "AST": StatPrior(mu=3.5, sigma=2.0, min_val=0, max_val=12, prior_strength=5, distribution="nbinom"),
        "REB": StatPrior(mu=3.5, sigma=1.5, min_val=0, max_val=10, prior_strength=5, distribution="nbinom"),
        "3PM": StatPrior(mu=2.2, sigma=1.3, min_val=0, max_val=10, prior_strength=5, distribution="nbinom"),
        "STL": StatPrior(mu=1.0, sigma=0.7, min_val=0, max_val=5, prior_strength=5, distribution="nbinom"),
        "BLK": StatPrior(mu=0.3, sigma=0.4, min_val=0, max_val=3, prior_strength=5, distribution="nbinom"),
        "PRA": StatPrior(mu=21.0, sigma=7.0, min_val=0, max_val=60, prior_strength=5),
    },
    "SF": {
        "PTS": StatPrior(mu=13.0, sigma=6.0, min_val=0, max_val=45, prior_strength=5),
        "AST": StatPrior(mu=2.5, sigma=1.5, min_val=0, max_val=10, prior_strength=5, distribution="nbinom"),
        "REB": StatPrior(mu=5.0, sigma=2.0, min_val=0, max_val=15, prior_strength=5, distribution="nbinom"),
        "3PM": StatPrior(mu=1.5, sigma=1.0, min_val=0, max_val=8, prior_strength=5, distribution="nbinom"),
        "STL": StatPrior(mu=0.9, sigma=0.6, min_val=0, max_val=4, prior_strength=5, distribution="nbinom"),
        "BLK": StatPrior(mu=0.5, sigma=0.5, min_val=0, max_val=4, prior_strength=5, distribution="nbinom"),
        "PRA": StatPrior(mu=20.5, sigma=7.0, min_val=0, max_val=60, prior_strength=5),
    },
    "PF": {
        "PTS": StatPrior(mu=12.0, sigma=5.5, min_val=0, max_val=45, prior_strength=5),
        "AST": StatPrior(mu=2.0, sigma=1.5, min_val=0, max_val=8, prior_strength=5, distribution="nbinom"),
        "REB": StatPrior(mu=6.5, sigma=2.5, min_val=0, max_val=18, prior_strength=5, distribution="nbinom"),
        "3PM": StatPrior(mu=1.2, sigma=1.0, min_val=0, max_val=7, prior_strength=5, distribution="nbinom"),
        "STL": StatPrior(mu=0.7, sigma=0.5, min_val=0, max_val=4, prior_strength=5, distribution="nbinom"),
        "BLK": StatPrior(mu=0.8, sigma=0.7, min_val=0, max_val=5, prior_strength=5, distribution="nbinom"),
        "PRA": StatPrior(mu=20.5, sigma=7.0, min_val=0, max_val=60, prior_strength=5),
    },
    "C": {
        "PTS": StatPrior(mu=12.0, sigma=5.0, min_val=0, max_val=40, prior_strength=5),
        "AST": StatPrior(mu=2.0, sigma=1.5, min_val=0, max_val=10, prior_strength=5, distribution="nbinom"),
        "REB": StatPrior(mu=8.0, sigma=3.0, min_val=0, max_val=20, prior_strength=5, distribution="nbinom"),
        "3PM": StatPrior(mu=0.5, sigma=0.8, min_val=0, max_val=5, prior_strength=5, distribution="nbinom"),
        "STL": StatPrior(mu=0.5, sigma=0.4, min_val=0, max_val=3, prior_strength=5, distribution="nbinom"),
        "BLK": StatPrior(mu=1.2, sigma=0.9, min_val=0, max_val=6, prior_strength=5, distribution="nbinom"),
        "PRA": StatPrior(mu=22.0, sigma=7.5, min_val=0, max_val=65, prior_strength=5),
    },
}

# Stat aliases
STAT_ALIASES = {
    "points": "PTS",
    "assists": "AST",
    "rebounds": "REB",
    "3pm": "3PM",
    "threes": "3PM",
    "steals": "STL",
    "blocks": "BLK",
    "pts+reb+ast": "PRA",
}


# ==============================================================================
# ELITE PLAYER ADJUSTMENTS
# ==============================================================================
# Multipliers applied to prior_strength (lower = less shrinkage for stars)

ELITE_ADJUSTMENTS: Dict[str, Dict[str, float]] = {
    # Superstars: Trust their data more (lower prior_strength multiplier)
    "Nikola Jokic": {"prior_strength_mult": 0.3, "PTS": 1.20, "AST": 1.50, "REB": 1.30},
    "Giannis Antetokounmpo": {"prior_strength_mult": 0.3, "PTS": 1.30, "REB": 1.25},
    "Luka Doncic": {"prior_strength_mult": 0.4, "PTS": 1.25, "AST": 1.35},
    "Shai Gilgeous-Alexander": {"prior_strength_mult": 0.4, "PTS": 1.25},
    "Jayson Tatum": {"prior_strength_mult": 0.5, "PTS": 1.15, "REB": 1.10},
    
    # High usage guards: More variance
    "Stephen Curry": {"prior_strength_mult": 0.5, "3PM": 1.50, "PTS": 1.15},
    "Anthony Edwards": {"prior_strength_mult": 0.6, "PTS": 1.15},
    "Damian Lillard": {"prior_strength_mult": 0.5, "PTS": 1.15, "3PM": 1.25},
    "Jalen Brunson": {"prior_strength_mult": 0.5, "PTS": 1.15, "AST": 1.20},
    "Tyrese Haliburton": {"prior_strength_mult": 0.4, "AST": 1.40},
    
    # Young volatile: More shrinkage
    "Victor Wembanyama": {"prior_strength_mult": 1.5, "BLK": 1.50},
    "LaMelo Ball": {"prior_strength_mult": 1.2, "AST": 1.20},
    
    # Minutes managed: More uncertainty
    "Joel Embiid": {"prior_strength_mult": 1.0, "PTS": 1.20, "REB": 1.15},
    "Kevin Durant": {"prior_strength_mult": 0.8, "PTS": 1.15},
}


# ==============================================================================
# BAYESIAN CALCULATIONS
# ==============================================================================

@dataclass
class BayesianProjection:
    """Result of Bayesian projection calculation."""
    player_name: str
    stat: str
    
    # Raw player stats
    player_mu: float
    player_sigma: float
    sample_n: int
    
    # Prior used
    prior_mu: float
    prior_sigma: float
    prior_strength: int
    
    # Posterior (final projection)
    posterior_mu: float
    posterior_sigma: float
    
    # Shrinkage info
    shrinkage_factor: float  # 0 = all player data, 1 = all prior
    elite_adjustment: float  # Multiplier applied
    distribution: str        # normal, nbinom, poisson


def get_position_prior(position: str, stat: str) -> Optional[StatPrior]:
    """Get positional prior for a stat."""
    # Normalize stat name
    stat_upper = STAT_ALIASES.get(stat.lower(), stat.upper())
    
    # Try exact position match
    if position in NBA_PRIORS:
        if stat_upper in NBA_PRIORS[position]:
            return NBA_PRIORS[position][stat_upper]
    
    # Fall back to generic guard/forward/center
    position_map = {
        "G": "PG",
        "F": "SF",
        "G-F": "SG",
        "F-G": "SF",
        "F-C": "PF",
        "C-F": "C",
    }
    mapped = position_map.get(position, "SF")  # Default to SF
    if mapped in NBA_PRIORS and stat_upper in NBA_PRIORS[mapped]:
        return NBA_PRIORS[mapped][stat_upper]
    
    return None


def get_elite_adjustment(player_name: str, stat: str) -> Tuple[float, float]:
    """
    Get elite player adjustment.
    
    Returns: (prior_strength_multiplier, stat_multiplier)
    """
    if player_name not in ELITE_ADJUSTMENTS:
        return (1.0, 1.0)
    
    adj = ELITE_ADJUSTMENTS[player_name]
    prior_mult = adj.get("prior_strength_mult", 1.0)
    stat_mult = adj.get(stat.upper(), 1.0)
    
    return (prior_mult, stat_mult)


def calculate_bayesian_projection(
    player_name: str,
    position: str,
    stat: str,
    player_mu: float,
    player_sigma: float,
    sample_n: int
) -> BayesianProjection:
    """
    Calculate Bayesian projection with shrinkage toward positional prior.
    
    Args:
        player_name: Player name for elite adjustments
        position: NBA position (PG, SG, SF, PF, C)
        stat: Stat type (PTS, AST, REB, 3PM, etc.)
        player_mu: Player's sample mean
        player_sigma: Player's sample std dev
        sample_n: Number of games in sample
    
    Returns:
        BayesianProjection with posterior mu/sigma
    """
    stat_upper = STAT_ALIASES.get(stat.lower(), stat.upper())
    
    # Get prior
    prior = get_position_prior(position, stat_upper)
    if prior is None:
        # No prior available, return player data as-is
        return BayesianProjection(
            player_name=player_name,
            stat=stat_upper,
            player_mu=player_mu,
            player_sigma=player_sigma,
            sample_n=sample_n,
            prior_mu=player_mu,
            prior_sigma=player_sigma,
            prior_strength=0,
            posterior_mu=player_mu,
            posterior_sigma=player_sigma,
            shrinkage_factor=0.0,
            elite_adjustment=1.0,
            distribution="normal"
        )
    
    # Get elite adjustments
    prior_mult, stat_mult = get_elite_adjustment(player_name, stat_upper)
    
    # Adjust prior strength for elite players
    effective_prior_strength = int(prior.prior_strength * prior_mult)
    effective_prior_strength = max(1, effective_prior_strength)  # At least 1
    
    # Adjust prior mean for elite players
    adjusted_prior_mu = prior.mu * stat_mult
    
    # Calculate posterior mean (shrinkage)
    n = sample_n
    k = effective_prior_strength
    
    posterior_mu = (n * player_mu + k * adjusted_prior_mu) / (n + k)
    
    # Calculate posterior variance
    player_var = player_sigma ** 2
    prior_var = prior.sigma ** 2
    posterior_var = (n * player_var + k * prior_var) / (n + k)
    posterior_sigma = math.sqrt(posterior_var)
    
    # Shrinkage factor (0 = no shrinkage, 1 = full shrinkage)
    shrinkage_factor = k / (n + k)
    
    return BayesianProjection(
        player_name=player_name,
        stat=stat_upper,
        player_mu=round(player_mu, 2),
        player_sigma=round(player_sigma, 2),
        sample_n=sample_n,
        prior_mu=round(adjusted_prior_mu, 2),
        prior_sigma=round(prior.sigma, 2),
        prior_strength=effective_prior_strength,
        posterior_mu=round(posterior_mu, 2),
        posterior_sigma=round(posterior_sigma, 2),
        shrinkage_factor=round(shrinkage_factor, 3),
        elite_adjustment=stat_mult,
        distribution=prior.distribution
    )


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def apply_bayesian_shrinkage(
    player_name: str,
    position: str,
    stat: str,
    mu: float,
    sigma: float,
    n: int
) -> Tuple[float, float, float]:
    """
    Quick function to apply Bayesian shrinkage.
    
    Returns: (posterior_mu, posterior_sigma, shrinkage_factor)
    """
    result = calculate_bayesian_projection(
        player_name=player_name,
        position=position,
        stat=stat,
        player_mu=mu,
        player_sigma=sigma,
        sample_n=n
    )
    return (result.posterior_mu, result.posterior_sigma, result.shrinkage_factor)


def format_projection_report(proj: BayesianProjection) -> str:
    """Format Bayesian projection as readable report."""
    lines = []
    lines.append(f"┌─ BAYESIAN PROJECTION ─────────────────────────────────")
    lines.append(f"│  {proj.player_name} — {proj.stat}")
    lines.append(f"│")
    lines.append(f"│  Player Data (n={proj.sample_n}):")
    lines.append(f"│    μ = {proj.player_mu:.1f}, σ = {proj.player_sigma:.1f}")
    lines.append(f"│")
    lines.append(f"│  Prior (strength={proj.prior_strength}):")
    lines.append(f"│    μ = {proj.prior_mu:.1f}, σ = {proj.prior_sigma:.1f}")
    if proj.elite_adjustment != 1.0:
        lines.append(f"│    Elite adjustment: {proj.elite_adjustment:.2f}x")
    lines.append(f"│")
    lines.append(f"│  Posterior:")
    lines.append(f"│    μ = {proj.posterior_mu:.1f}, σ = {proj.posterior_sigma:.1f}")
    lines.append(f"│    Shrinkage: {proj.shrinkage_factor:.1%} toward prior")
    lines.append(f"│    Distribution: {proj.distribution}")
    lines.append(f"└───────────────────────────────────────────────────────")
    return "\n".join(lines)


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("NBA BAYESIAN PRIORS TEST")
    print("=" * 60)
    
    # Test 1: Jokic AST (elite, minimal shrinkage)
    proj = calculate_bayesian_projection(
        player_name="Nikola Jokic",
        position="C",
        stat="AST",
        player_mu=9.5,
        player_sigma=2.8,
        sample_n=20
    )
    print("\nTest 1: Jokic AST (elite player)")
    print(format_projection_report(proj))
    
    # Test 2: Unknown rookie (heavy shrinkage)
    proj2 = calculate_bayesian_projection(
        player_name="Random Rookie",
        position="PG",
        stat="PTS",
        player_mu=18.0,
        player_sigma=8.0,
        sample_n=5
    )
    print("\nTest 2: Rookie PTS (small sample)")
    print(format_projection_report(proj2))
    
    # Test 3: Wemby BLK (young volatile, extra shrinkage)
    proj3 = calculate_bayesian_projection(
        player_name="Victor Wembanyama",
        position="C",
        stat="BLK",
        player_mu=4.0,
        player_sigma=1.8,
        sample_n=15
    )
    print("\nTest 3: Wembanyama BLK (young volatile)")
    print(format_projection_report(proj3))
    
    print("\n✅ Bayesian priors test complete")
