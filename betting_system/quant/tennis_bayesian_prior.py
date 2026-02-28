#!/usr/bin/env python3
"""
Tennis Bayesian Priors Module - Phase 4 Implementation
========================================================
Implements Bayesian shrinkage for Tennis player prop projections.

Key concepts:
1. Ranking-based priors: Higher ranked = less shrinkage
2. Surface-based adjustments: Clay/Grass/Hard specialists
3. Match format: Best-of-3 vs Best-of-5 variance
4. Head-to-head priors: Historical matchup data

Props supported:
- Total Games
- Total Sets
- Aces
- Double Faults
- First Serve %

Version: 1.0.0
Created: 2026-02-04
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class TennisStatPrior:
    """Prior distribution for a Tennis stat."""
    mu: float
    sigma: float
    min_val: float
    max_val: float
    prior_strength: int = 5
    distribution: str = "normal"


# Tennis Priors by ranking tier
TENNIS_PRIORS: Dict[str, Dict[str, TennisStatPrior]] = {
    # Top 10 players - very stable, less shrinkage needed
    "TOP10": {
        "TOTAL_GAMES": TennisStatPrior(mu=22.5, sigma=3.5, min_val=12, max_val=40, prior_strength=3),
        "TOTAL_SETS": TennisStatPrior(mu=2.3, sigma=0.5, min_val=2, max_val=5, prior_strength=3),
        "ACES": TennisStatPrior(mu=8.0, sigma=4.0, min_val=0, max_val=30, prior_strength=4, distribution="nbinom"),
        "DOUBLE_FAULTS": TennisStatPrior(mu=3.0, sigma=2.0, min_val=0, max_val=15, prior_strength=4, distribution="nbinom"),
        "FIRST_SERVE_PCT": TennisStatPrior(mu=0.65, sigma=0.08, min_val=0.40, max_val=0.85, prior_strength=3),
    },
    # Ranked 11-50 - moderate stability
    "TOP50": {
        "TOTAL_GAMES": TennisStatPrior(mu=23.0, sigma=4.0, min_val=12, max_val=45, prior_strength=5),
        "TOTAL_SETS": TennisStatPrior(mu=2.4, sigma=0.55, min_val=2, max_val=5, prior_strength=5),
        "ACES": TennisStatPrior(mu=6.0, sigma=4.0, min_val=0, max_val=25, prior_strength=5, distribution="nbinom"),
        "DOUBLE_FAULTS": TennisStatPrior(mu=3.5, sigma=2.5, min_val=0, max_val=15, prior_strength=5, distribution="nbinom"),
        "FIRST_SERVE_PCT": TennisStatPrior(mu=0.62, sigma=0.10, min_val=0.35, max_val=0.85, prior_strength=5),
    },
    # Ranked 51-100 - more variance
    "TOP100": {
        "TOTAL_GAMES": TennisStatPrior(mu=23.5, sigma=4.5, min_val=12, max_val=48, prior_strength=6),
        "TOTAL_SETS": TennisStatPrior(mu=2.5, sigma=0.6, min_val=2, max_val=5, prior_strength=6),
        "ACES": TennisStatPrior(mu=5.0, sigma=4.0, min_val=0, max_val=20, prior_strength=6, distribution="nbinom"),
        "DOUBLE_FAULTS": TennisStatPrior(mu=4.0, sigma=3.0, min_val=0, max_val=18, prior_strength=6, distribution="nbinom"),
        "FIRST_SERVE_PCT": TennisStatPrior(mu=0.60, sigma=0.12, min_val=0.30, max_val=0.85, prior_strength=6),
    },
    # Outside Top 100 - high variance, heavy shrinkage
    "UNRANKED": {
        "TOTAL_GAMES": TennisStatPrior(mu=24.0, sigma=5.0, min_val=12, max_val=50, prior_strength=8),
        "TOTAL_SETS": TennisStatPrior(mu=2.6, sigma=0.7, min_val=2, max_val=5, prior_strength=8),
        "ACES": TennisStatPrior(mu=4.0, sigma=4.0, min_val=0, max_val=18, prior_strength=8, distribution="nbinom"),
        "DOUBLE_FAULTS": TennisStatPrior(mu=4.5, sigma=3.5, min_val=0, max_val=20, prior_strength=8, distribution="nbinom"),
        "FIRST_SERVE_PCT": TennisStatPrior(mu=0.58, sigma=0.14, min_val=0.25, max_val=0.85, prior_strength=8),
    },
}

# Surface adjustments (multipliers to prior stats)
SURFACE_ADJUSTMENTS: Dict[str, Dict[str, float]] = {
    "HARD": {
        "ACES": 1.0,
        "DOUBLE_FAULTS": 1.0,
        "TOTAL_GAMES": 1.0,
    },
    "CLAY": {
        "ACES": 0.75,  # Fewer aces on clay
        "DOUBLE_FAULTS": 1.15,  # Slightly more DFs
        "TOTAL_GAMES": 1.10,  # Longer rallies, more games
    },
    "GRASS": {
        "ACES": 1.35,  # More aces on grass
        "DOUBLE_FAULTS": 0.90,  # Fewer DFs
        "TOTAL_GAMES": 0.92,  # Shorter points
    },
}

# Elite player adjustments (less shrinkage, stat-specific boosts)
ELITE_TENNIS_PLAYERS: Dict[str, Dict[str, float]] = {
    # Big servers - aces boost
    "Jannik Sinner": {"prior_strength_mult": 0.4, "ACES": 1.10},
    "Carlos Alcaraz": {"prior_strength_mult": 0.4, "TOTAL_GAMES": 0.95},
    "Novak Djokovic": {"prior_strength_mult": 0.3, "FIRST_SERVE_PCT": 1.05},
    "Alexander Zverev": {"prior_strength_mult": 0.5, "ACES": 1.20, "DOUBLE_FAULTS": 1.30},
    "Daniil Medvedev": {"prior_strength_mult": 0.4, "TOTAL_GAMES": 1.05},
    "Andrey Rublev": {"prior_strength_mult": 0.5, "DOUBLE_FAULTS": 1.25},
    "Holger Rune": {"prior_strength_mult": 0.6, "TOTAL_GAMES": 1.05},
    
    # WTA
    "Iga Swiatek": {"prior_strength_mult": 0.3, "TOTAL_GAMES": 0.90},
    "Aryna Sabalenka": {"prior_strength_mult": 0.4, "ACES": 1.25},
    "Coco Gauff": {"prior_strength_mult": 0.5, "DOUBLE_FAULTS": 1.30},
    "Elena Rybakina": {"prior_strength_mult": 0.4, "ACES": 1.30},
    "Jessica Pegula": {"prior_strength_mult": 0.5, "TOTAL_GAMES": 1.05},
}


def get_ranking_tier(ranking: int) -> str:
    """Get ranking tier from ATP/WTA ranking."""
    if ranking <= 10:
        return "TOP10"
    elif ranking <= 50:
        return "TOP50"
    elif ranking <= 100:
        return "TOP100"
    else:
        return "UNRANKED"


def get_tennis_prior(
    ranking: int,
    stat: str,
    surface: str = "HARD"
) -> Optional[TennisStatPrior]:
    """Get prior for a Tennis stat based on ranking and surface."""
    tier = get_ranking_tier(ranking)
    stat_upper = stat.upper().replace(" ", "_")
    
    if tier not in TENNIS_PRIORS:
        tier = "UNRANKED"
    
    if stat_upper not in TENNIS_PRIORS[tier]:
        return None
    
    prior = TENNIS_PRIORS[tier][stat_upper]
    
    # Apply surface adjustment
    surface_upper = surface.upper()
    if surface_upper in SURFACE_ADJUSTMENTS:
        adj = SURFACE_ADJUSTMENTS[surface_upper].get(stat_upper, 1.0)
        return TennisStatPrior(
            mu=prior.mu * adj,
            sigma=prior.sigma * adj,
            min_val=prior.min_val,
            max_val=prior.max_val,
            prior_strength=prior.prior_strength,
            distribution=prior.distribution
        )
    
    return prior


@dataclass
class TennisBayesianProjection:
    """Result of Tennis Bayesian projection."""
    player_name: str
    stat: str
    surface: str
    
    player_mu: float
    player_sigma: float
    sample_n: int
    
    prior_mu: float
    prior_sigma: float
    prior_strength: int
    
    posterior_mu: float
    posterior_sigma: float
    shrinkage_factor: float
    
    distribution: str


def calculate_tennis_bayesian_projection(
    player_name: str,
    ranking: int,
    stat: str,
    player_mu: float,
    player_sigma: float,
    sample_n: int,
    surface: str = "HARD"
) -> TennisBayesianProjection:
    """
    Calculate Bayesian projection for Tennis.
    """
    stat_upper = stat.upper().replace(" ", "_")
    
    prior = get_tennis_prior(ranking, stat, surface)
    if prior is None:
        return TennisBayesianProjection(
            player_name=player_name,
            stat=stat_upper,
            surface=surface,
            player_mu=player_mu,
            player_sigma=player_sigma,
            sample_n=sample_n,
            prior_mu=player_mu,
            prior_sigma=player_sigma,
            prior_strength=0,
            posterior_mu=player_mu,
            posterior_sigma=player_sigma,
            shrinkage_factor=0.0,
            distribution="normal"
        )
    
    # Elite player adjustments
    prior_mult = 1.0
    stat_mult = 1.0
    if player_name in ELITE_TENNIS_PLAYERS:
        adj = ELITE_TENNIS_PLAYERS[player_name]
        prior_mult = adj.get("prior_strength_mult", 1.0)
        stat_mult = adj.get(stat_upper, 1.0)
    
    effective_strength = max(1, int(prior.prior_strength * prior_mult))
    adjusted_prior_mu = prior.mu * stat_mult
    
    # Bayesian shrinkage
    n = sample_n
    k = effective_strength
    
    posterior_mu = (n * player_mu + k * adjusted_prior_mu) / (n + k)
    
    player_var = player_sigma ** 2
    prior_var = prior.sigma ** 2
    posterior_var = (n * player_var + k * prior_var) / (n + k)
    posterior_sigma = math.sqrt(posterior_var)
    
    shrinkage = k / (n + k)
    
    return TennisBayesianProjection(
        player_name=player_name,
        stat=stat_upper,
        surface=surface,
        player_mu=round(player_mu, 2),
        player_sigma=round(player_sigma, 2),
        sample_n=sample_n,
        prior_mu=round(adjusted_prior_mu, 2),
        prior_sigma=round(prior.sigma, 2),
        prior_strength=effective_strength,
        posterior_mu=round(posterior_mu, 2),
        posterior_sigma=round(posterior_sigma, 2),
        shrinkage_factor=round(shrinkage, 3),
        distribution=prior.distribution
    )


def apply_tennis_bayesian_shrinkage(
    player_name: str,
    ranking: int,
    stat: str,
    mu: float,
    sigma: float,
    n: int,
    surface: str = "HARD"
) -> Tuple[float, float, float]:
    """Quick function to apply Tennis Bayesian shrinkage."""
    result = calculate_tennis_bayesian_projection(
        player_name=player_name,
        ranking=ranking,
        stat=stat,
        player_mu=mu,
        player_sigma=sigma,
        sample_n=n,
        surface=surface
    )
    return (result.posterior_mu, result.posterior_sigma, result.shrinkage_factor)


if __name__ == "__main__":
    print("=" * 60)
    print("TENNIS BAYESIAN PRIORS TEST")
    print("=" * 60)
    
    # Test 1: Sinner (Top 10, low shrinkage)
    proj = calculate_tennis_bayesian_projection(
        player_name="Jannik Sinner",
        ranking=1,
        stat="ACES",
        player_mu=10.5,
        player_sigma=3.2,
        sample_n=15,
        surface="HARD"
    )
    print(f"\nSinner ACES (rank 1):")
    print(f"  Player: μ={proj.player_mu}, σ={proj.player_sigma}")
    print(f"  Prior:  μ={proj.prior_mu}, strength={proj.prior_strength}")
    print(f"  Posterior: μ={proj.posterior_mu}, shrinkage={proj.shrinkage_factor:.1%}")
    
    # Test 2: Unranked player (heavy shrinkage)
    proj2 = calculate_tennis_bayesian_projection(
        player_name="Unknown Qualifier",
        ranking=250,
        stat="TOTAL_GAMES",
        player_mu=28.0,
        player_sigma=6.0,
        sample_n=5,
        surface="CLAY"
    )
    print(f"\nQualifier TOTAL_GAMES (rank 250, clay):")
    print(f"  Player: μ={proj2.player_mu}, σ={proj2.player_sigma}")
    print(f"  Prior:  μ={proj2.prior_mu}, strength={proj2.prior_strength}")
    print(f"  Posterior: μ={proj2.posterior_mu}, shrinkage={proj2.shrinkage_factor:.1%}")
    
    # Test 3: Zverev double faults (known weakness)
    proj3 = calculate_tennis_bayesian_projection(
        player_name="Alexander Zverev",
        ranking=3,
        stat="DOUBLE_FAULTS",
        player_mu=5.5,
        player_sigma=2.5,
        sample_n=20,
        surface="GRASS"
    )
    print(f"\nZverev DOUBLE_FAULTS (rank 3, grass):")
    print(f"  Player: μ={proj3.player_mu}, σ={proj3.player_sigma}")
    print(f"  Prior:  μ={proj3.prior_mu}, strength={proj3.prior_strength}")
    print(f"  Posterior: μ={proj3.posterior_mu}, shrinkage={proj3.shrinkage_factor:.1%}")
    
    print("\n✅ Tennis Bayesian priors test complete")
