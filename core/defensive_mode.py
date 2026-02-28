"""
Defensive Mode — Automatic Truth Communication Layer
SOP v2.2: Low-quality slates trigger DEFENSIVE MODE which:
    - Caps maximum tier
    - Injects banner into reports
    - Minimizes capital deployment
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DefensiveModeResult:
    """Machine-readable defensive mode state."""
    defensive_mode: bool
    max_allowed_tier: str  # SLAM, STRONG, LEAN
    reasons: List[str]
    capital_multiplier: float  # 0.0-1.0 for bet sizing
    banner_text: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "defensive_mode": self.defensive_mode,
            "max_allowed_tier": self.max_allowed_tier,
            "defensive_reasons": self.reasons,
            "capital_multiplier": round(self.capital_multiplier, 2),
            "defensive_banner": self.banner_text
        }


def evaluate_defensive_mode(
    slate_quality: int,
    api_health: float,
    injury_density: float,
    no_play_ratio: float = 0.0
) -> DefensiveModeResult:
    """
    Evaluate whether DEFENSIVE MODE should be activated.
    
    Auto-trigger conditions (ANY of these):
        - slate_quality < 50
        - api_health < 0.85
        - injury_density > 0.30
        - no_play_ratio > 0.80
    
    Args:
        slate_quality: Slate quality score (0-100)
        api_health: API health score (0-1)
        injury_density: Percentage of props with injury uncertainty (0-1)
        no_play_ratio: Percentage of props that are NO PLAY (0-1)
    
    Returns:
        DefensiveModeResult with enforcement flags
    """
    reasons = []
    
    # Check trigger conditions
    if slate_quality < 50:
        reasons.append(f"Low slate quality ({slate_quality}/100)")
    
    if api_health < 0.85:
        reasons.append(f"API degraded ({api_health:.0%})")
    
    if injury_density > 0.30:
        reasons.append(f"High injury uncertainty ({injury_density:.0%})")
    
    if no_play_ratio > 0.80:
        reasons.append(f"NO PLAY dominance ({no_play_ratio:.0%})")
    
    defensive_mode = len(reasons) > 0
    
    # Determine max tier
    if not defensive_mode:
        max_allowed_tier = "SLAM"
        capital_multiplier = 1.0
    elif slate_quality < 35 or api_health < 0.7:
        max_allowed_tier = "LEAN"
        capital_multiplier = 0.25
    elif slate_quality < 50:
        max_allowed_tier = "STRONG"
        capital_multiplier = 0.5
    else:
        max_allowed_tier = "STRONG"
        capital_multiplier = 0.75
    
    # Generate banner text
    if defensive_mode:
        banner_lines = [
            "⚠️ DEFENSIVE MODE ACTIVE",
            "",
            "Reason:",
        ]
        for reason in reasons:
            banner_lines.append(f"  - {reason}")
        banner_lines.extend([
            "",
            "Action:",
            "  - Capital deployment minimized",
            "  - NO PLAY dominance expected",
            f"  - Max tier: {max_allowed_tier}",
        ])
        banner_text = "\n".join(banner_lines)
    else:
        banner_text = ""
    
    result = DefensiveModeResult(
        defensive_mode=defensive_mode,
        max_allowed_tier=max_allowed_tier,
        reasons=reasons,
        capital_multiplier=capital_multiplier,
        banner_text=banner_text
    )
    
    if defensive_mode:
        logger.warning(f"DEFENSIVE MODE: {reasons}")
    
    return result


def enforce_tier_cap(decision: str, max_allowed_tier: str) -> str:
    """
    Enforce tier cap based on defensive mode.
    
    Args:
        decision: Current decision (SLAM, PLAY, STRONG, LEAN, NO_PLAY, etc.)
        max_allowed_tier: Maximum allowed tier from defensive mode
    
    Returns:
        Capped decision
    """
    tier_hierarchy = ["SLAM", "PLAY", "STRONG", "LEAN", "NO_PLAY", "PASS", "BLOCKED", "SKIP"]
    
    # Normalize decision
    decision_upper = decision.upper().replace(" ", "_")
    
    # Find positions
    try:
        decision_pos = tier_hierarchy.index(decision_upper)
    except ValueError:
        return decision  # Unknown tier, pass through
    
    try:
        max_pos = tier_hierarchy.index(max_allowed_tier)
    except ValueError:
        return decision  # Unknown cap, pass through
    
    # If decision is higher (lower index) than max, downgrade
    if decision_pos < max_pos:
        logger.info(f"Tier cap enforced: {decision} → {max_allowed_tier}")
        return max_allowed_tier
    
    return decision
