"""
CBB Live Foul-Out Probability Engine
-------------------------------------
Foul-outs destroy overs and rotations. We compute player-level foul-out 
probability and auto-lock unders when risk spikes.

This is a DEFENSIVE mechanism — it protects capital, not generates edges.
"""

import math
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PlayerFoulState:
    """Current foul state for a player."""
    player_id: str
    player_name: str
    personal_fouls: int
    minutes_played: float
    fouls_per_min_baseline: float  # Historical average


@dataclass
class FoulOutRisk:
    """Foul-out probability assessment."""
    player_id: str
    player_name: str
    probability: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    action: str  # NONE, WATCH, LOCK_UNDERS


# Risk thresholds
FOULOUT_RISK_LEVELS = {
    "LOW": (0.0, 0.15),
    "MEDIUM": (0.15, 0.25),
    "HIGH": (0.25, 0.35),
    "CRITICAL": (0.35, 1.0)
}

# Auto-lock threshold
FOULOUT_LOCK_THRESHOLD = 0.35


def foulout_probability(
    personal_fouls: int,
    minutes_played: float,
    fouls_per_min_baseline: float
) -> float:
    """
    Compute probability of fouling out (5 fouls in CBB).
    
    Uses a Poisson hazard-style estimate:
    - Calculate expected future fouls based on baseline rate
    - Compute probability of reaching 5 total
    
    Args:
        personal_fouls: Current personal fouls (0-4)
        minutes_played: Minutes played so far
        fouls_per_min_baseline: Historical fouls per minute rate
    
    Returns:
        Probability of fouling out (0.0 to 1.0)
    """
    # Already fouled out
    if personal_fouls >= 5:
        return 1.0
    
    # Ensure valid rate
    rate = max(fouls_per_min_baseline, 0.001)
    
    # Remaining minutes in regulation
    remaining_minutes = max(40 - minutes_played, 0)
    
    # If no time left, can't foul out
    if remaining_minutes <= 0:
        return 0.0
    
    # Expected future fouls
    expected_future_fouls = rate * remaining_minutes
    
    # Fouls needed to reach 5
    needed = max(5 - personal_fouls, 0)
    
    if needed == 0:
        return 1.0  # Already at 5
    
    # Poisson CDF complement: P(X >= needed) = 1 - P(X < needed)
    # P(X < needed) = sum of P(X=k) for k in 0..needed-1
    cumulative = 0.0
    lambda_val = expected_future_fouls
    
    for k in range(needed):
        # P(X=k) = (lambda^k * e^-lambda) / k!
        poisson_pmf = (lambda_val ** k) * math.exp(-lambda_val) / math.factorial(k)
        cumulative += poisson_pmf
    
    prob = 1.0 - cumulative
    return min(max(prob, 0.0), 1.0)


def classify_foulout_risk(prob: float) -> str:
    """Classify foul-out probability into risk level."""
    for level, (low, high) in FOULOUT_RISK_LEVELS.items():
        if low <= prob < high:
            return level
    return "CRITICAL"


def determine_action(prob: float) -> str:
    """Determine action based on foul-out probability."""
    if prob >= FOULOUT_LOCK_THRESHOLD:
        return "LOCK_UNDERS"
    elif prob >= 0.25:
        return "WATCH"
    else:
        return "NONE"


def assess_player_foulout(state: PlayerFoulState) -> FoulOutRisk:
    """
    Assess foul-out risk for a single player.
    
    Args:
        state: Current foul state for player
    
    Returns:
        FoulOutRisk assessment
    """
    prob = foulout_probability(
        personal_fouls=state.personal_fouls,
        minutes_played=state.minutes_played,
        fouls_per_min_baseline=state.fouls_per_min_baseline
    )
    
    return FoulOutRisk(
        player_id=state.player_id,
        player_name=state.player_name,
        probability=prob,
        risk_level=classify_foulout_risk(prob),
        action=determine_action(prob)
    )


def assess_team_foulout(players: List[PlayerFoulState]) -> Dict:
    """
    Assess foul-out risk for all players and determine team action.
    
    Args:
        players: List of player foul states
    
    Returns:
        Dict with individual assessments and team recommendation
    """
    assessments = [assess_player_foulout(p) for p in players]
    
    # Sort by probability descending
    assessments.sort(key=lambda x: x.probability, reverse=True)
    
    # Get top 2 risks
    top_risks = assessments[:2]
    top_probs = [a.probability for a in top_risks]
    
    # Team action: if any key player (top 2) has critical risk, lock unders
    team_action = "NONE"
    if any(a.action == "LOCK_UNDERS" for a in top_risks):
        team_action = "LOCK_UNDERS"
    elif any(a.action == "WATCH" for a in top_risks):
        team_action = "WATCH"
    
    return {
        "assessments": assessments,
        "top_2_probs": top_probs,
        "team_action": team_action,
        "lock_unders": team_action == "LOCK_UNDERS",
        "timestamp": datetime.now().isoformat()
    }


def should_lock_unders_foulout(foul_probs: List[float]) -> bool:
    """
    Check if foul-out risk warrants locking unders.
    
    Args:
        foul_probs: List of foul-out probabilities for key players
    
    Returns:
        True if unders should be locked
    """
    if not foul_probs:
        return False
    
    # Lock if any key player exceeds threshold
    return max(foul_probs) >= FOULOUT_LOCK_THRESHOLD


# Example usage
def example():
    """Example foul-out assessment."""
    players = [
        PlayerFoulState("p1", "Star Guard", 3, 18.5, 0.08),
        PlayerFoulState("p2", "Big Man", 4, 22.0, 0.12),
        PlayerFoulState("p3", "Point Guard", 2, 20.0, 0.06),
    ]
    
    result = assess_team_foulout(players)
    
    print(f"Team Action: {result['team_action']}")
    print(f"Lock Unders: {result['lock_unders']}")
    for a in result['assessments']:
        print(f"  {a.player_name}: {a.probability:.1%} ({a.risk_level}) -> {a.action}")


if __name__ == "__main__":
    example()
