"""
Dual-Domain Accuracy Validator
Validates statistical value (μ vs line) and regime probability independently.
Classifies picks as CONVICTION, VALUE, HYBRID, or REJECT.
"""

from dataclasses import dataclass
from typing import Literal

# NBA statistical ranges (per-game, valid bounds)
STAT_RANGES = {
    "points": (5, 35),
    "rebounds": (2, 16),
    "assists": (1, 12),
    "3pm": (0, 10),
    "steals": (0, 5),
    "blocks": (0, 6),
    "turnovers": (0, 8),
    # Combo stats (sum of individual components)
    "pts_reb_ast": (10, 60),  # Sum of three major stats
    "pts_reb": (8, 50),
    "pts_ast": (8, 45),
    "reb_ast": (3, 28),
}

PlayType = Literal["CONVICTION", "VALUE", "HYBRID", "REJECT"]

@dataclass
class DomainValidation:
    """Result of dual-domain validation"""
    player: str
    stat: str
    line: float
    mu: float | None
    sigma: float | None
    
    # Domain 1: Statistical Value (μ vs line)
    mu_valid: bool  # Does μ pass sanity check?
    mu_gap: float | None  # Line - μ (positive = underpriced)
    value_edge: bool  # Is gap >= 3 points?
    
    # Domain 2: Regime Probability
    confidence_pct: float  # Our regime hit rate (50-85%)
    conviction: bool  # Is confidence >= 60%?
    
    # Classification
    play_type: PlayType
    reasoning: str
    
    def __str__(self) -> str:
        icon = "[CONVICTION]" if self.play_type == "CONVICTION" else \
               "[VALUE]" if self.play_type == "VALUE" else \
               "[HYBRID]" if self.play_type == "HYBRID" else "[REJECT]"
        return f"{icon} {self.player:20s} {self.stat:15s} O{self.line}"


def validate_mu(stat: str, mu: float | None, line: float) -> tuple[bool, str]:
    """
    Validate μ against NBA statistical ranges.
    Returns: (is_valid, error_message)
    """
    if mu is None:
        return False, "No μ provided"
    
    # Determine which stat category we're validating
    base_stat = stat.split()[0].lower()  # "points" from "points O 25.5"
    
    # Find matching range
    range_key = None
    for key in STAT_RANGES:
        if key in stat.lower():
            range_key = key
            break
    
    if not range_key:
        return False, f"Unknown stat category: {stat}"
    
    min_val, max_val = STAT_RANGES[range_key]
    
    # Check bounds
    if mu < min_val or mu > max_val:
        return False, f"μ={mu:.1f} outside valid range ({min_val}-{max_val})"
    
    # Check for obviously wrong values (>1000 indicates aggregation error)
    if mu > 1000:
        return False, f"μ={mu} appears to be sum, not average (data corruption)"
    
    return True, "Valid"


def classify_pick(
    player: str,
    stat: str,
    line: float,
    mu: float | None,
    sigma: float | None,
    confidence_pct: float,
) -> DomainValidation:
    """
    Classify a pick into one of four categories using dual-domain logic.
    
    SOP Decision Tree:
    1. If μ invalid AND confidence >= 60% → CONVICTION (regime strong, data weak)
    2. If μ valid AND gap >= 3pt AND confidence >= 60% → HYBRID (both strong)
    3. If μ valid AND gap >= 3pt AND confidence < 60% → VALUE (edge strong, conviction weak)
    4. Otherwise → REJECT (insufficient on both domains)
    
    Args:
        player: Player name
        stat: Stat with direction (e.g., "points O 25.5")
        line: The offered line
        mu: Player's expected production (per-game average)
        sigma: Standard deviation
        confidence_pct: Our regime-based hit rate (50-85%)
    
    Returns:
        DomainValidation object with classification and reasoning
    """
    
    # Validate μ (Domain 1 gate)
    mu_valid, mu_error = validate_mu(stat, mu, line)
    mu_gap = None
    value_edge = False
    
    if mu_valid:
        mu_gap = mu - line  # Positive = line too low (underpriced)
        value_edge = mu_gap >= 3.0  # At least 3-point cushion
    
    # Validate confidence (Domain 2 gate)
    conviction = confidence_pct >= 60.0
    
    # SOP Decision Tree (strict order)
    if not mu_valid and conviction:
        # Step 1: Regime strong, data weak
        play_type = "CONVICTION"
        reasoning = f"{confidence_pct:.0f}% regime strength (data corrupt: {mu_error})"
    elif mu_valid and value_edge and conviction:
        # Step 2: Both domains strong
        play_type = "HYBRID"
        reasoning = f"μ={mu:.1f} vs {line} (+{mu_gap:.1f}pt edge) + {confidence_pct:.0f}% conviction"
    elif mu_valid and value_edge and not conviction:
        # Step 3: Edge strong, conviction weak
        play_type = "VALUE"
        reasoning = f"+{mu_gap:.1f}pt edge (μ={mu:.1f}), but only {confidence_pct:.0f}% conviction"
    else:
        # Step 4: Insufficient on both (default reject)
        play_type = "REJECT"
        if not mu_valid and not conviction:
            reasoning = f"Weak on both: bad data ({mu_error}) + {confidence_pct:.0f}% conviction"
        elif not value_edge and not conviction:
            reasoning = f"Weak on both: only {mu_gap:.1f}pt gap + {confidence_pct:.0f}% conviction"
        else:
            reasoning = "Insufficient on both domains"
    
    return DomainValidation(
        player=player,
        stat=stat,
        line=line,
        mu=mu,
        sigma=sigma,
        mu_valid=mu_valid,
        mu_gap=mu_gap,
        value_edge=value_edge,
        confidence_pct=confidence_pct,
        conviction=conviction,
        play_type=play_type,
        reasoning=reasoning,
    )


def batch_classify(picks: list[dict]) -> list[DomainValidation]:
    """
    Classify multiple picks at once.
    
    Expected dict format:
    {
        "player": str,
        "stat": str,
        "line": float,
        "mu": float | None,
        "sigma": float | None,
        "confidence": float (0-100),
    }
    """
    results = []
    for pick in picks:
        result = classify_pick(
            player=pick["player"],
            stat=pick["stat"],
            line=pick["line"],
            mu=pick.get("mu"),
            sigma=pick.get("sigma"),
            confidence_pct=pick["confidence"],
        )
        results.append(result)
    return results


def print_validation_report(validations: list[DomainValidation]) -> None:
    """Pretty-print validation results grouped by play type"""
    print("\n" + "="*100)
    print("DUAL-DOMAIN PICK CLASSIFICATION")
    print("="*100)
    
    by_type = {}
    for v in validations:
        if v.play_type not in by_type:
            by_type[v.play_type] = []
        by_type[v.play_type].append(v)
    
    # Print in priority order
    for play_type in ["HYBRID", "CONVICTION", "VALUE", "REJECT"]:
        if play_type in by_type:
            picks = by_type[play_type]
            icon = "[HYBRID]" if play_type == "HYBRID" else \
                   "[CONVICTION]" if play_type == "CONVICTION" else \
                   "[VALUE]" if play_type == "VALUE" else "[REJECT]"
            
            print(f"\n{icon} {play_type} ({len(picks)} picks)")
            print("-" * 100)
            for v in picks:
                print(f"  {v.player:20s} {v.stat:20s} @ {v.line:6.1f}")
                print(f"    => {v.reasoning}")
    
    print("\n" + "="*100)
