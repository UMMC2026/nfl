"""
Confidence level ordering and capping logic.

Defines the hierarchy of conviction levels and provides deterministic
capping based on tier, ensuring lower-tier users don't leak access to
high-conviction edges while maintaining psychological upgrade pressure.

CONFIDENCE_ORDER (hierarchical):
  WEAK    < LEAN < STRONG < ELITE
  (1)    < (2)  < (3)     < (4)

Capping Rule:
  if actual_confidence > max_allowed:
      return max_allowed
  else:
      return actual_confidence
"""

# Hierarchical ordering of confidence levels
CONFIDENCE_ORDER = {
    "WEAK": 1,
    "LEAN": 2,
    "STRONG": 3,
    "ELITE": 4,
}


def cap_confidence(confidence: str, max_allowed: str) -> str:
    """
    Cap a confidence level to a maximum allowed level.

    Args:
        confidence: Actual confidence level (e.g., "ELITE")
        max_allowed: Maximum allowed level for this tier (e.g., "STRONG")

    Returns:
        Capped confidence level. If actual > max_allowed, returns max_allowed.
        Otherwise returns actual.

    Examples:
        cap_confidence("ELITE", "STRONG") -> "STRONG"
        cap_confidence("WEAK", "STRONG") -> "WEAK"
        cap_confidence("LEAN", "STRONG") -> "LEAN"
    """
    actual_order = CONFIDENCE_ORDER.get(confidence, 0)
    max_order = CONFIDENCE_ORDER.get(max_allowed, 0)

    if actual_order > max_order:
        return max_allowed
    return confidence


def get_max_confidence_for_tier(tier_name: str) -> str:
    """
    Get maximum allowed confidence level for a given tier.

    Args:
        tier_name: Tier identifier (e.g., "FREE", "STARTER", "PRO", "WHALE")

    Returns:
        Maximum confidence level that tier can see.
    """
    tier_caps = {
        "FREE": "STRONG",  # Free tier capped to STRONG; ELITE withheld
        "STARTER": "ELITE",  # STARTER sees all levels
        "PRO": "ELITE",  # PRO sees all levels
        "WHALE": "ELITE",  # WHALE sees all levels
    }
    return tier_caps.get(tier_name, "WEAK")
