"""
Calibration Penalty Rules — Derived from real-money Sleeper ticket analysis

PURPOSE: These rules are PROVEN by empirical failure data from user tickets.
         They override model confidence when structural risk is detected.

AUTHORITY: This file has GOVERNANCE authority over Monte Carlo optimization.
           If a pick violates these rules, it MUST be penalized or rejected.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

# --- PENALTY CATEGORIES ---

class PenaltyType(Enum):
    """Types of calibration penalties"""
    HARD_BAN = "HARD_BAN"        # Pick REJECTED outright
    SEVERE = "SEVERE"            # -15% to -20% confidence
    MODERATE = "MODERATE"        # -8% to -12% confidence  
    CAUTION = "CAUTION"          # -3% to -5% confidence
    NONE = "NONE"                # No penalty


@dataclass
class PenaltyRule:
    """Single penalty rule"""
    name: str
    description: str
    penalty_type: PenaltyType
    penalty_pct: float  # Negative value (e.g., -0.15 = -15%)
    conditions: Dict[str, any]
    override_allowed: bool = False
    
    def matches(self, pick: dict) -> bool:
        """Check if pick matches this rule's conditions"""
        for key, value in self.conditions.items():
            if callable(value):
                if not value(pick.get(key)):
                    return False
            elif isinstance(value, (list, set)):
                if pick.get(key) not in value:
                    return False
            else:
                if pick.get(key) != value:
                    return False
        return True


# --- HARD BANS (PROVEN FAILURES) ---

HARD_BAN_RULES = [
    PenaltyRule(
        name="BIG_REB_UNDER",
        description="Rebound UNDERS on starting big men — proven tail blowup risk",
        penalty_type=PenaltyType.HARD_BAN,
        penalty_pct=-1.0,  # Complete rejection
        conditions={
            "stat": {"REB", "rebounds"},
            "direction": {"Lower", "UNDER", "lower"},
            "position": {"C", "PF"},
        },
    ),
    PenaltyRule(
        name="COMBO_UNDER_HIGH_USAGE",
        description="Combo UNDERS on ≥22% usage players — variance trap",
        penalty_type=PenaltyType.HARD_BAN,
        penalty_pct=-1.0,
        conditions={
            "stat": {"PRA", "PTS+AST", "pts+reb+ast", "pts+ast"},
            "direction": {"Lower", "UNDER", "lower"},
            "usage_rate": lambda x: x is not None and x >= 22.0,
        },
    ),
    PenaltyRule(
        name="3PM_NO_VOLUME",
        description="3PM OVERS without attempt volume — low sample trap",
        penalty_type=PenaltyType.HARD_BAN,
        penalty_pct=-1.0,
        conditions={
            "stat": {"3PM", "3pm"},
            "direction": {"Higher", "OVER", "higher"},
            "projected_3pa": lambda x: x is not None and x < 4.0,
            "line": lambda x: x >= 2.0,
        },
    ),
    PenaltyRule(
        name="PARLAY_OVEREXPOSED",
        description="Parlays >2 legs — geometric EV destruction",
        penalty_type=PenaltyType.HARD_BAN,
        penalty_pct=-1.0,
        conditions={
            "ticket_legs": lambda x: x is not None and x > 2,
        },
    ),
]

# --- SEVERE PENALTIES (-15% to -20%) ---

SEVERE_PENALTY_RULES = [
    PenaltyRule(
        name="BENCH_MICROWAVE_PTS",
        description="Bench players on PTS/AST props — usage volatility",
        penalty_type=PenaltyType.SEVERE,
        penalty_pct=-0.15,
        conditions={
            "role": {"bench_scorer", "role_player", "BENCH_MICROWAVE"},
            "stat": {"PTS", "AST", "PTS+AST", "points", "assists", "pts+ast"},
        },
    ),
    PenaltyRule(
        name="COMBO_STAT_GENERAL",
        description="All combo stats carry inherent variance",
        penalty_type=PenaltyType.SEVERE,
        penalty_pct=-0.12,
        conditions={
            "stat": {"PRA", "PTS+AST", "AST+REB", "REB+AST", "pts+reb+ast", "pts+ast", "ast+reb"},
        },
    ),
    PenaltyRule(
        name="UNDER_BLOWOUT_RISK",
        description="UNDER bets in high-spread games — garbage time ceiling",
        penalty_type=PenaltyType.SEVERE,
        penalty_pct=-0.15,
        conditions={
            "direction": {"Lower", "UNDER", "lower"},
            "spread": lambda x: x is not None and abs(x) >= 10,
        },
    ),
]

# --- MODERATE PENALTIES (-8% to -12%) ---

MODERATE_PENALTY_RULES = [
    PenaltyRule(
        name="HIGH_LINE_3PM",
        description="3PM lines ≥2.5 carry shooter variance",
        penalty_type=PenaltyType.MODERATE,
        penalty_pct=-0.08,
        conditions={
            "stat": {"3PM", "3pm"},
            "line": lambda x: x >= 2.5,
        },
    ),
    PenaltyRule(
        name="SMALL_SAMPLE_MATCHUP",
        description="Matchup sample <3 games — confidence compression",
        penalty_type=PenaltyType.MODERATE,
        penalty_pct=-0.10,
        conditions={
            "matchup_games": lambda x: x is not None and x < 3,
        },
    ),
    PenaltyRule(
        name="B2B_FATIGUE",
        description="Back-to-back games — minutes cut risk",
        penalty_type=PenaltyType.MODERATE,
        penalty_pct=-0.08,
        conditions={
            "rest_days": lambda x: x is not None and x == 0,
        },
    ),
]

# --- CAUTION PENALTIES (-3% to -5%) ---

CAUTION_PENALTY_RULES = [
    PenaltyRule(
        name="ROAD_GAME_OVER",
        description="OVER props in road games — slight travel penalty",
        penalty_type=PenaltyType.CAUTION,
        penalty_pct=-0.03,
        conditions={
            "direction": {"Higher", "OVER", "higher"},
            "is_home": False,
        },
    ),
    PenaltyRule(
        name="USAGE_DECLINING",
        description="Player with declining usage trend",
        penalty_type=PenaltyType.CAUTION,
        penalty_pct=-0.05,
        conditions={
            "usage_trend": {"DOWN", "declining"},
        },
    ),
]

# --- COMBINE ALL RULES ---

ALL_RULES = (
    HARD_BAN_RULES + 
    SEVERE_PENALTY_RULES + 
    MODERATE_PENALTY_RULES + 
    CAUTION_PENALTY_RULES
)


# --- PENALTY ENGINE ---

@dataclass
class PenaltyResult:
    """Result of penalty evaluation"""
    original_probability: float
    final_probability: float
    total_penalty: float
    applied_rules: List[str]
    is_banned: bool
    ban_reason: Optional[str]


def evaluate_penalties(pick: dict, probability: float) -> PenaltyResult:
    """
    Evaluate all penalty rules against a pick.
    
    Args:
        pick: Dictionary with pick attributes
        probability: Original predicted probability (0-100 scale)
    
    Returns:
        PenaltyResult with adjusted probability and applied rules
    """
    applied_rules = []
    total_penalty = 0.0
    is_banned = False
    ban_reason = None
    
    for rule in ALL_RULES:
        if rule.matches(pick):
            applied_rules.append(rule.name)
            
            if rule.penalty_type == PenaltyType.HARD_BAN:
                is_banned = True
                ban_reason = rule.description
                break  # No need to check further
            else:
                total_penalty += rule.penalty_pct
    
    # Cap total penalty at -40%
    total_penalty = max(total_penalty, -0.40)
    
    # Apply penalty to probability
    final_probability = probability * (1.0 + total_penalty)
    final_probability = max(0.0, min(100.0, final_probability))  # Clamp to 0-100
    
    return PenaltyResult(
        original_probability=probability,
        final_probability=final_probability,
        total_penalty=total_penalty,
        applied_rules=applied_rules,
        is_banned=is_banned,
        ban_reason=ban_reason,
    )


def get_confidence_cap(risk_tags: List[str]) -> float:
    """
    Get confidence cap based on risk tags.
    
    MANDATORY RULE: If margin distribution shows heavy tails,
    confidence MUST be capped at 65%.
    """
    TAIL_RISK_TAGS = {
        "BIG_REB_TAIL_RISK",
        "COMBO_HIGH_VARIANCE", 
        "TAIL_BLOWUP",
        "HIGH_USAGE_UNDER_RISK",
    }
    
    if any(tag in TAIL_RISK_TAGS for tag in risk_tags):
        return 0.65  # 65% max confidence
    
    return 1.0  # No cap


def apply_confidence_compression(
    probability: float, 
    risk_tags: List[str],
    margin_mean: Optional[float] = None,
    margin_std: Optional[float] = None,
) -> float:
    """
    Apply confidence compression rule from calibration spec.
    
    MANDATORY: if abs(margin_mean) > 2.5 * std_dev:
               confidence_cap = min(confidence, 0.65)
    """
    cap = get_confidence_cap(risk_tags)
    
    # Margin distribution check
    if margin_mean is not None and margin_std is not None and margin_std > 0:
        if abs(margin_mean) > 2.5 * margin_std:
            cap = min(cap, 0.65)
    
    return min(probability, cap * 100)


# --- GOVERNANCE INTEGRATION ---

def enforce_governance(pick: dict, probability: float) -> Tuple[str, float, str]:
    """
    Enforce governance rules on a pick.
    
    Returns:
        Tuple of (state, adjusted_probability, reason)
        State is one of: OPTIMIZABLE, VETTED, REJECTED
    """
    result = evaluate_penalties(pick, probability)
    
    if result.is_banned:
        return ("REJECTED", 0.0, result.ban_reason)
    
    # Check probability threshold after penalties
    if result.final_probability < 55.0:
        return ("REJECTED", result.final_probability, "Below 55% after penalties")
    
    # Check for FRAGILE state (visible but not optimizable)
    fragile_tags = {"HIGH_USAGE_UNDER_RISK", "COMBO_HIGH_VARIANCE", "BENCH_MICROWAVE_RISK"}
    risk_tags = pick.get("risk_tags", [])
    
    if any(tag in fragile_tags for tag in risk_tags):
        return ("VETTED", result.final_probability, "FRAGILE: Context only, not optimizable")
    
    return ("OPTIMIZABLE", result.final_probability, "Cleared governance")


# --- REPORT GENERATION ---

def generate_rules_report() -> str:
    """Generate human-readable rules report"""
    lines = []
    lines.append("=" * 80)
    lines.append("CALIBRATION PENALTY RULES REFERENCE")
    lines.append("=" * 80)
    
    lines.append("\n🚫 HARD BANS (Automatic REJECT):")
    for rule in HARD_BAN_RULES:
        lines.append(f"  • {rule.name}: {rule.description}")
    
    lines.append("\n⚠️ SEVERE PENALTIES (-12% to -15%):")
    for rule in SEVERE_PENALTY_RULES:
        lines.append(f"  • {rule.name}: {rule.description} [{rule.penalty_pct:+.0%}]")
    
    lines.append("\n⚡ MODERATE PENALTIES (-8% to -10%):")
    for rule in MODERATE_PENALTY_RULES:
        lines.append(f"  • {rule.name}: {rule.description} [{rule.penalty_pct:+.0%}]")
    
    lines.append("\n💡 CAUTION PENALTIES (-3% to -5%):")
    for rule in CAUTION_PENALTY_RULES:
        lines.append(f"  • {rule.name}: {rule.description} [{rule.penalty_pct:+.0%}]")
    
    lines.append("\n" + "=" * 80)
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_rules_report())
