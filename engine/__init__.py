"""
Engine module - core signal processing components.
"""

from .stability import stability_score, stability_class
from .correlation import block_correlated, block_same_player_max, market_family
from .tiers import assign_tier, tier_emoji, tier_description
from .filters import qualify_signal, filter_signals, build_signal_from_mc_result
from .exposure import ExposureGovernor, ExposureConfig, build_safe_parlay

__all__ = [
    "stability_score",
    "stability_class", 
    "block_correlated",
    "block_same_player_max",
    "market_family",
    "assign_tier",
    "tier_emoji",
    "tier_description",
    "qualify_signal",
    "filter_signals",
    "build_signal_from_mc_result",
    "ExposureGovernor",
    "ExposureConfig",
    "build_safe_parlay",
]
