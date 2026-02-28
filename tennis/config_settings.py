"""
TENNIS CONFIGURATION — Rolling Windows & Market Alignment
Tennis already has L10 implementation (TIER1_UPGRADE_COMPLETE.md confirms this).
This config documents the settings for consistency with NBA/CBB.
"""

# =============================================================================
# ROLLING WINDOW CONFIGURATION
# =============================================================================
# Tennis uses L10 stats for all probability calculations
# Implemented in: tennis/ingest/ingest_tennis.py
L10_FIELDS = [
    "ace_pct_L10",
    "first_serve_pct_L10",
    "hold_pct_L10",
    "win_pct_L10",
    "df_pct_L10",
    "break_pct_L10",
]

# No L5/L10 blend needed - Tennis uses pure L10
L10_BLEND_WEIGHT = 1.0  # 100% L10 (no short-term window due to match-to-match variance)

# =============================================================================
# MARKET ALIGNMENT GATE
# =============================================================================
# Tennis market alignment threshold (looser than NBA due to match variance)
MARKET_ALIGNMENT_THRESHOLD = 12.0  # 12% divergence allowed (vs NBA 10%, CBB 15%)

# Market types for tennis
MARKET_TYPES = {
    "TOTALS": "totals",      # Total games, total sets, player aces
    "WINNER": "winner",      # Match winner (moneyline)
}

# Surface-specific adjustments
SURFACE_VOLATILITY = {
    "HARD": 1.0,    # Baseline
    "CLAY": 0.9,    # More predictable (serve advantage reduced)
    "GRASS": 1.2,   # Higher variance (serve dominance)
    "INDOOR": 1.1,  # Slightly elevated (controlled conditions but faster)
}

# =============================================================================
# TIER THRESHOLDS (Tennis-Specific)
# =============================================================================
# Tennis uses STRONG/LEAN only (no SLAM tier due to match variance)
TIER_THRESHOLDS = {
    "STRONG": 0.70,
    "LEAN": 0.60,
    "NO_PLAY": 0.0,
}

# =============================================================================
# NOTES
# =============================================================================
"""
Tennis L10 Success Story:
- Already implemented (see tennis/TIER1_UPGRADE_COMPLETE.md)
- Proven +15-25% accuracy improvement
- Used as blueprint for NBA L10 implementation

Market Alignment for Tennis:
- 12% threshold balances match variance with market efficiency
- Tennis markets are efficient for top players, softer for qualifiers/wildcards
- Surface-specific adjustments account for serve dominance variations
"""
