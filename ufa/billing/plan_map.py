"""
Stripe plan ID to tier mapping — single source of truth for entitlements.
"""
from ufa.models.user import PlanTier
import os

# Map Stripe price IDs to tiers
PLAN_TO_TIER = {
    os.getenv("STRIPE_PRICE_STARTER", "price_1Sk9MJAmdkLb1k5vCHpMiiPj"): PlanTier.STARTER,
    os.getenv("STRIPE_PRICE_PRO", "price_1Sk9LlAmdkLb1k5vQgCjNglj"): PlanTier.PRO,
    os.getenv("STRIPE_PRICE_WHALE", "price_1Sk9LCAmdkLb1k5viXrT4NfB"): PlanTier.WHALE,
}


def tier_for_price(price_id: str) -> PlanTier:
    """Get tier for a Stripe price ID. Defaults to FREE if not found."""
    return PLAN_TO_TIER.get(price_id, PlanTier.FREE)
