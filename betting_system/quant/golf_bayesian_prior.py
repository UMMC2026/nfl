#!/usr/bin/env python3
"""
Golf Bayesian Priors Module - Phase 4 Implementation
======================================================
Implements Bayesian shrinkage for Golf player prop projections.

Key concepts:
1. OWGR-based priors: Higher ranked = less shrinkage
2. Strokes Gained category specialization
3. Course fit adjustments: Length, difficulty, surface type
4. Tournament type: Major vs regular event variance

Props supported:
- Tournament Finish Position
- Strokes Gained: Total
- Strokes Gained: Off-the-Tee
- Strokes Gained: Approach
- Strokes Gained: Around Green
- Strokes Gained: Putting

Version: 1.0.0
Created: 2026-02-04
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import math


@dataclass
class GolfStatPrior:
    """Prior distribution for a Golf stat."""
    mu: float
    sigma: float
    min_val: float
    max_val: float
    prior_strength: int = 5
    distribution: str = "normal"


# Golf Priors by OWGR ranking tier
GOLF_PRIORS: Dict[str, Dict[str, GolfStatPrior]] = {
    # Top 10 - elite, very stable
    "TOP10": {
        "SG_TOTAL": GolfStatPrior(mu=2.0, sigma=1.5, min_val=-3, max_val=8, prior_strength=3),
        "SG_OTT": GolfStatPrior(mu=0.5, sigma=0.8, min_val=-2, max_val=3, prior_strength=3),
        "SG_APP": GolfStatPrior(mu=0.6, sigma=0.9, min_val=-2, max_val=4, prior_strength=3),
        "SG_ARG": GolfStatPrior(mu=0.3, sigma=0.5, min_val=-1.5, max_val=2, prior_strength=3),
        "SG_PUTT": GolfStatPrior(mu=0.4, sigma=0.7, min_val=-2, max_val=3, prior_strength=3),
        "FINISH_POSITION": GolfStatPrior(mu=15, sigma=15, min_val=1, max_val=80, prior_strength=4),
    },
    # Ranked 11-30 - strong players
    "TOP30": {
        "SG_TOTAL": GolfStatPrior(mu=1.2, sigma=1.8, min_val=-4, max_val=7, prior_strength=5),
        "SG_OTT": GolfStatPrior(mu=0.3, sigma=0.9, min_val=-2.5, max_val=3, prior_strength=5),
        "SG_APP": GolfStatPrior(mu=0.35, sigma=1.0, min_val=-2.5, max_val=4, prior_strength=5),
        "SG_ARG": GolfStatPrior(mu=0.15, sigma=0.6, min_val=-1.5, max_val=2, prior_strength=5),
        "SG_PUTT": GolfStatPrior(mu=0.2, sigma=0.8, min_val=-2, max_val=3, prior_strength=5),
        "FINISH_POSITION": GolfStatPrior(mu=25, sigma=20, min_val=1, max_val=100, prior_strength=5),
    },
    # Ranked 31-75 - tour regulars
    "TOP75": {
        "SG_TOTAL": GolfStatPrior(mu=0.5, sigma=2.0, min_val=-5, max_val=6, prior_strength=6),
        "SG_OTT": GolfStatPrior(mu=0.1, sigma=1.0, min_val=-3, max_val=3, prior_strength=6),
        "SG_APP": GolfStatPrior(mu=0.15, sigma=1.1, min_val=-3, max_val=4, prior_strength=6),
        "SG_ARG": GolfStatPrior(mu=0.05, sigma=0.7, min_val=-2, max_val=2, prior_strength=6),
        "SG_PUTT": GolfStatPrior(mu=0.1, sigma=0.9, min_val=-2.5, max_val=3, prior_strength=6),
        "FINISH_POSITION": GolfStatPrior(mu=35, sigma=22, min_val=1, max_val=120, prior_strength=6),
    },
    # Ranked 76-150 - fringe players
    "TOP150": {
        "SG_TOTAL": GolfStatPrior(mu=0.0, sigma=2.2, min_val=-6, max_val=5, prior_strength=7),
        "SG_OTT": GolfStatPrior(mu=0.0, sigma=1.1, min_val=-3, max_val=3, prior_strength=7),
        "SG_APP": GolfStatPrior(mu=0.0, sigma=1.2, min_val=-3, max_val=3, prior_strength=7),
        "SG_ARG": GolfStatPrior(mu=0.0, sigma=0.8, min_val=-2, max_val=2, prior_strength=7),
        "SG_PUTT": GolfStatPrior(mu=0.0, sigma=1.0, min_val=-3, max_val=3, prior_strength=7),
        "FINISH_POSITION": GolfStatPrior(mu=45, sigma=25, min_val=1, max_val=140, prior_strength=7),
    },
    # Outside 150 - heavy shrinkage
    "UNRANKED": {
        "SG_TOTAL": GolfStatPrior(mu=-0.3, sigma=2.5, min_val=-7, max_val=4, prior_strength=8),
        "SG_OTT": GolfStatPrior(mu=-0.1, sigma=1.2, min_val=-3.5, max_val=2.5, prior_strength=8),
        "SG_APP": GolfStatPrior(mu=-0.1, sigma=1.3, min_val=-3.5, max_val=3, prior_strength=8),
        "SG_ARG": GolfStatPrior(mu=-0.05, sigma=0.9, min_val=-2.5, max_val=2, prior_strength=8),
        "SG_PUTT": GolfStatPrior(mu=-0.05, sigma=1.1, min_val=-3, max_val=2.5, prior_strength=8),
        "FINISH_POSITION": GolfStatPrior(mu=55, sigma=28, min_val=1, max_val=156, prior_strength=8),
    },
}

# Course type adjustments
COURSE_ADJUSTMENTS: Dict[str, Dict[str, float]] = {
    "LONG": {  # 7400+ yards
        "SG_OTT": 1.20,  # Driving matters more
        "SG_APP": 0.90,  # Long approaches harder to control
    },
    "SHORT": {  # <7000 yards
        "SG_OTT": 0.85,  # Driving matters less
        "SG_APP": 1.10,  # Approach play more important
        "SG_ARG": 1.10,  # Short game matters
    },
    "LINKS": {  # British Open style
        "SG_OTT": 1.15,  # Must find fairways
        "SG_ARG": 1.25,  # Links chipping crucial
        "SG_PUTT": 0.90,  # Greens more predictable
    },
    "MAJOR": {  # Major championship setup
        "SG_TOTAL": 0.90,  # Tighter distribution
        "FINISH_POSITION": 0.85,  # More variance in finishes
    },
}

# Elite player adjustments
ELITE_GOLFERS: Dict[str, Dict[str, float]] = {
    "Scottie Scheffler": {"prior_strength_mult": 0.3, "SG_APP": 1.20, "SG_TOTAL": 1.15},
    "Rory McIlroy": {"prior_strength_mult": 0.3, "SG_OTT": 1.25},
    "Jon Rahm": {"prior_strength_mult": 0.3, "SG_TOTAL": 1.10},
    "Xander Schauffele": {"prior_strength_mult": 0.4, "SG_APP": 1.15},
    "Viktor Hovland": {"prior_strength_mult": 0.4, "SG_APP": 1.10},
    "Collin Morikawa": {"prior_strength_mult": 0.4, "SG_APP": 1.20, "SG_OTT": 0.90},
    "Patrick Cantlay": {"prior_strength_mult": 0.4, "SG_PUTT": 1.15},
    "Ludvig Aberg": {"prior_strength_mult": 0.5, "SG_OTT": 1.15},
    "Wyndham Clark": {"prior_strength_mult": 0.5, "SG_OTT": 1.10},
    "Tony Finau": {"prior_strength_mult": 0.5, "SG_TOTAL": 1.05},
    # Known putting specialists
    "Jordan Spieth": {"prior_strength_mult": 0.4, "SG_PUTT": 1.25, "SG_OTT": 0.85},
    # Big hitters
    "Bryson DeChambeau": {"prior_strength_mult": 0.4, "SG_OTT": 1.30, "SG_PUTT": 0.90},
    "Cameron Champ": {"prior_strength_mult": 0.6, "SG_OTT": 1.35, "SG_APP": 0.85},
}


def get_owgr_tier(ranking: int) -> str:
    """Get tier from OWGR ranking."""
    if ranking <= 10:
        return "TOP10"
    elif ranking <= 30:
        return "TOP30"
    elif ranking <= 75:
        return "TOP75"
    elif ranking <= 150:
        return "TOP150"
    else:
        return "UNRANKED"


def get_golf_prior(
    ranking: int,
    stat: str,
    course_type: Optional[str] = None
) -> Optional[GolfStatPrior]:
    """Get prior for a Golf stat based on ranking and course type."""
    tier = get_owgr_tier(ranking)
    stat_upper = stat.upper().replace(" ", "_")
    
    if tier not in GOLF_PRIORS:
        tier = "UNRANKED"
    
    if stat_upper not in GOLF_PRIORS[tier]:
        return None
    
    prior = GOLF_PRIORS[tier][stat_upper]
    
    # Apply course adjustment
    if course_type and course_type.upper() in COURSE_ADJUSTMENTS:
        adj = COURSE_ADJUSTMENTS[course_type.upper()].get(stat_upper, 1.0)
        return GolfStatPrior(
            mu=prior.mu * adj if stat_upper != "FINISH_POSITION" else prior.mu,
            sigma=prior.sigma * adj,
            min_val=prior.min_val,
            max_val=prior.max_val,
            prior_strength=prior.prior_strength,
            distribution=prior.distribution
        )
    
    return prior


@dataclass
class GolfBayesianProjection:
    """Result of Golf Bayesian projection."""
    player_name: str
    stat: str
    course_type: Optional[str]
    
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


def calculate_golf_bayesian_projection(
    player_name: str,
    owgr_ranking: int,
    stat: str,
    player_mu: float,
    player_sigma: float,
    sample_n: int,
    course_type: Optional[str] = None
) -> GolfBayesianProjection:
    """Calculate Bayesian projection for Golf."""
    stat_upper = stat.upper().replace(" ", "_")
    
    prior = get_golf_prior(owgr_ranking, stat, course_type)
    if prior is None:
        return GolfBayesianProjection(
            player_name=player_name,
            stat=stat_upper,
            course_type=course_type,
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
    
    # Elite adjustments
    prior_mult = 1.0
    stat_mult = 1.0
    if player_name in ELITE_GOLFERS:
        adj = ELITE_GOLFERS[player_name]
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
    
    return GolfBayesianProjection(
        player_name=player_name,
        stat=stat_upper,
        course_type=course_type,
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


def apply_golf_bayesian_shrinkage(
    player_name: str,
    owgr_ranking: int,
    stat: str,
    mu: float,
    sigma: float,
    n: int,
    course_type: Optional[str] = None
) -> Tuple[float, float, float]:
    """Quick function to apply Golf Bayesian shrinkage."""
    result = calculate_golf_bayesian_projection(
        player_name=player_name,
        owgr_ranking=owgr_ranking,
        stat=stat,
        player_mu=mu,
        player_sigma=sigma,
        sample_n=n,
        course_type=course_type
    )
    return (result.posterior_mu, result.posterior_sigma, result.shrinkage_factor)


if __name__ == "__main__":
    print("=" * 60)
    print("GOLF BAYESIAN PRIORS TEST")
    print("=" * 60)
    
    # Test 1: Scheffler SG:Total (Top 10, elite)
    proj = calculate_golf_bayesian_projection(
        player_name="Scottie Scheffler",
        owgr_ranking=1,
        stat="SG_TOTAL",
        player_mu=2.8,
        player_sigma=1.2,
        sample_n=20,
        course_type=None
    )
    print(f"\nScheffler SG:Total (rank 1):")
    print(f"  Player: μ={proj.player_mu}, σ={proj.player_sigma}")
    print(f"  Prior:  μ={proj.prior_mu}, strength={proj.prior_strength}")
    print(f"  Posterior: μ={proj.posterior_mu}, shrinkage={proj.shrinkage_factor:.1%}")
    
    # Test 2: Unranked player (heavy shrinkage)
    proj2 = calculate_golf_bayesian_projection(
        player_name="Random Monday Q",
        owgr_ranking=500,
        stat="SG_APP",
        player_mu=1.5,
        player_sigma=1.8,
        sample_n=5,
        course_type="LONG"
    )
    print(f"\nMonday Q SG:Approach (rank 500, long course):")
    print(f"  Player: μ={proj2.player_mu}, σ={proj2.player_sigma}")
    print(f"  Prior:  μ={proj2.prior_mu}, strength={proj2.prior_strength}")
    print(f"  Posterior: μ={proj2.posterior_mu}, shrinkage={proj2.shrinkage_factor:.1%}")
    
    # Test 3: Spieth putting (known strength)
    proj3 = calculate_golf_bayesian_projection(
        player_name="Jordan Spieth",
        owgr_ranking=12,
        stat="SG_PUTT",
        player_mu=0.8,
        player_sigma=0.6,
        sample_n=25,
        course_type=None
    )
    print(f"\nSpieth SG:Putting (rank 12):")
    print(f"  Player: μ={proj3.player_mu}, σ={proj3.player_sigma}")
    print(f"  Prior:  μ={proj3.prior_mu}, strength={proj3.prior_strength}")
    print(f"  Posterior: μ={proj3.posterior_mu}, shrinkage={proj3.shrinkage_factor:.1%}")
    
    print("\n✅ Golf Bayesian priors test complete")
