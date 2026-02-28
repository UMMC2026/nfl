"""
SPORT-SPECIFIC CONFIDENCE THRESHOLDS
SOP v2.1 Section 2.4 Compliant Configuration

Extends canonical thresholds with sport-specific calibration
while maintaining probability-driven tier assignments.
"""

# ============================================================================
# CANONICAL TIERS (SOP v2.1 Section 5 - Rule C2)
# ============================================================================

TIER_THRESHOLDS = {
    'SLAM': 0.75,      # ≥75% win probability
    'STRONG': 0.65,    # 65-74% win probability
    'LEAN': 0.55,      # 55-64% win probability
    'NO_PLAY': 0.00    # <55% (excluded from recommendations)
}


# ============================================================================
# SPORT-SPECIFIC CONFIDENCE CAPS
# ============================================================================

SPORT_CONFIDENCE_CAPS = {
    
    # -------------------------------------------------------------------------
    # NBA - High-volume props, tight calibration possible
    # -------------------------------------------------------------------------
    'NBA': {
        'core': 0.75,           # Player props with strong historical data
        'volume_micro': 0.65,   # Micro-markets (rebounds, assists)
        'sequence_early': 0.60, # Early season or limited sample
        'event_binary': 0.55,   # Game outcomes, spreads
        
        # Context modifiers
        'home_boost': 0.03,     # Home court advantage adjustment
        'injury_impact': -0.05, # Key player out degradation
        'back_to_back': -0.02   # Fatigue adjustment
    },
    
    # -------------------------------------------------------------------------
    # TENNIS - Match volatility and surface effects
    # -------------------------------------------------------------------------
    'TENNIS': {
        # Primary market types
        'match_outcome': 0.70,     # Match winner (BO3/BO5 variance)
        'set_spread': 0.65,        # Set handicaps (-1.5, +1.5)
        'games_total': 0.60,       # Over/Under total games
        'player_props': 0.58,      # Aces, double faults, service games
        'surface_adjusted': 0.55,  # Minimum edge on any surface
        
        # Surface-specific modifiers
        'clay_boost': {
            'nadal_specialty': 0.05,   # Clay court specialists
            'baseline_grinder': 0.03   # Defensive players
        },
        'grass_boost': {
            'big_serve': 0.04,         # Serve-heavy players
            'net_rusher': 0.02         # Attacking styles
        },
        'hard_neutral': 0.00,          # No surface bias
        
        # Tournament stage modifiers
        'grand_slam': -0.03,           # Higher variance in majors
        'masters_1000': -0.02,         # Premier events
        'atp_250': 0.02,               # Smaller tournaments more predictable
        
        # Match format
        'best_of_5': -0.05,            # Grand Slam men's matches
        'best_of_3': 0.00              # Standard format
    },
    
    # -------------------------------------------------------------------------
    # NFL - Drive-level EPA and situational modeling
    # -------------------------------------------------------------------------
    'NFL': {
        'drive_epa': 0.72,        # EPA-based drive models
        'game_total': 0.68,       # Over/Under totals
        'spread': 0.65,           # Point spreads
        'player_props': 0.62,     # Player performance props
        'situational': 0.58,      # Red zone, third down specific
        
        # Weather modifiers
        'wind_high': -0.08,       # Wind >20mph
        'wind_moderate': -0.04,   # Wind 10-20mph
        'rain_heavy': -0.06,      # Heavy precipitation
        'cold_extreme': -0.05,    # Temp <20°F
        
        # Game context
        'playoff_variance': -0.04,  # Single elimination uncertainty
        'division_game': -0.02,     # Rivalry intensity
        'primetime': -0.01          # National TV pressure
    },
    
    # -------------------------------------------------------------------------
    # CFB - College Football (higher variance than NFL)
    # -------------------------------------------------------------------------
    'CFB': {
        'spread': 0.62,           # Point spreads (more volatile)
        'total': 0.60,            # Game totals
        'player_props': 0.58,     # Limited historical data
        'conference': 0.55,       # Conference game baseline
        
        # Modifiers
        'fcs_opponent': 0.08,     # FCS vs FBS mismatch
        'rivalry': -0.03,         # Rivalry game variance
        'bowl_game': -0.04        # Bowl season uncertainty
    },
    
    # -------------------------------------------------------------------------
    # CBB - College Basketball (even more variance)
    # -------------------------------------------------------------------------
    'CBB': {
        'spread': 0.60,           # Lower confidence than NBA
        'total': 0.58,            # Scoring variance
        'player_props': 0.56,     # Limited minutes data
        'conference': 0.55,       # Conference baseline
        
        # Tournament effects
        'march_madness': -0.08,   # NCAA Tournament chaos
        'conference_tourney': -0.05
    }
}


# ============================================================================
# TENNIS LEGACY CONFIDENCE MAPPING
# ============================================================================

TENNIS_LEGACY_MAP = {
    'HIGH': 'match_outcome',    # Highest confidence tennis picks
    'MEDIUM': 'set_spread',     # Medium confidence
    'LOW': 'games_total'        # Lower confidence, more variance
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_sport_threshold(sport: str, market_type: str) -> float:
    """
    Get threshold for specific sport and market type
    
    Args:
        sport: Sport code ('NBA', 'TENNIS', 'NFL', etc.)
        market_type: Market type key (e.g., 'match_outcome', 'spread')
        
    Returns:
        Threshold probability (0.0-1.0)
        
    Example:
        >>> get_sport_threshold('TENNIS', 'match_outcome')
        0.70
        >>> get_sport_threshold('NFL', 'spread')
        0.65
    """
    caps = SPORT_CONFIDENCE_CAPS.get(sport, {})
    return caps.get(market_type, 0.55)  # Default to minimum edge


def apply_sport_modifier(base_prob: float, sport: str, modifier_key: str) -> float:
    """
    Apply sport-specific modifier to base probability
    
    Args:
        base_prob: Base calculated probability
        sport: Sport code
        modifier_key: Modifier to apply (e.g., 'home_boost', 'wind_high')
        
    Returns:
        Adjusted probability
        
    Example:
        >>> apply_sport_modifier(0.70, 'NBA', 'home_boost')
        0.73
    """
    caps = SPORT_CONFIDENCE_CAPS.get(sport, {})
    modifier = caps.get(modifier_key, 0.0)
    
    # Clamp adjusted probability to [0.0, 1.0]
    adjusted = max(0.0, min(1.0, base_prob + modifier))
    return adjusted


def validate_sport_config(sport: str) -> bool:
    """
    Validate that sport has proper threshold configuration
    
    Args:
        sport: Sport code to validate
        
    Returns:
        True if sport has valid configuration
        
    Raises:
        ValueError: If sport configuration is invalid
    """
    if sport not in SPORT_CONFIDENCE_CAPS:
        raise ValueError(f"Sport '{sport}' not configured in SPORT_CONFIDENCE_CAPS")
    
    caps = SPORT_CONFIDENCE_CAPS[sport]
    
    # Check that at least one threshold is defined
    thresholds = [v for v in caps.values() if isinstance(v, (int, float))]
    if not thresholds:
        raise ValueError(f"Sport '{sport}' has no numeric thresholds")
    
    # Check that all thresholds are in valid range
    for key, value in caps.items():
        if isinstance(value, (int, float)):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"Threshold '{key}' for '{sport}' out of range: {value}")
    
    return True


# ============================================================================
# TENNIS-SPECIFIC HELPERS
# ============================================================================

def get_tennis_threshold(confidence: str = None, market_type: str = None) -> float:
    """
    Get tennis threshold with backward compatibility for legacy confidence
    
    Args:
        confidence: Legacy confidence string ('HIGH', 'MEDIUM', 'LOW')
        market_type: Modern market type ('match_outcome', 'set_spread', etc.)
        
    Returns:
        Threshold probability
        
    Example:
        >>> get_tennis_threshold(confidence='HIGH')
        0.70
        >>> get_tennis_threshold(market_type='player_props')
        0.58
    """
    if confidence and confidence in TENNIS_LEGACY_MAP:
        market_type = TENNIS_LEGACY_MAP[confidence]
    
    if not market_type:
        market_type = 'surface_adjusted'  # Default to minimum edge
    
    return get_sport_threshold('TENNIS', market_type)


def adjust_tennis_surface(base_prob: float, surface: str, player_style: str = None) -> float:
    """
    Adjust tennis probability for surface and player style
    
    Args:
        base_prob: Base calculated probability
        surface: Court surface ('clay', 'grass', 'hard')
        player_style: Optional player style indicator
        
    Returns:
        Surface-adjusted probability
        
    Example:
        >>> adjust_tennis_surface(0.68, 'clay', 'nadal_specialty')
        0.73
    """
    surface_lower = surface.lower()
    
    caps = SPORT_CONFIDENCE_CAPS['TENNIS']
    
    # Apply surface-specific boost if player style matches
    if surface_lower == 'clay' and player_style:
        boost_dict = caps.get('clay_boost', {})
        modifier = boost_dict.get(player_style, 0.0)
    elif surface_lower == 'grass' and player_style:
        boost_dict = caps.get('grass_boost', {})
        modifier = boost_dict.get(player_style, 0.0)
    else:
        modifier = caps.get('hard_neutral', 0.0)
    
    adjusted = max(0.0, min(1.0, base_prob + modifier))
    return adjusted


# ============================================================================
# VALIDATION TESTS
# ============================================================================

if __name__ == "__main__":
    # Validate all sport configurations
    for sport in SPORT_CONFIDENCE_CAPS.keys():
        try:
            validate_sport_config(sport)
            print(f"✅ {sport} configuration valid")
        except ValueError as e:
            print(f"❌ {sport} configuration invalid: {e}")
    
    # Test tennis helpers
    print("\n--- Tennis Threshold Tests ---")
    print(f"HIGH confidence: {get_tennis_threshold(confidence='HIGH')}")
    print(f"MEDIUM confidence: {get_tennis_threshold(confidence='MEDIUM')}")
    print(f"LOW confidence: {get_tennis_threshold(confidence='LOW')}")
    print(f"Player props: {get_tennis_threshold(market_type='player_props')}")
    
    # Test surface adjustment
    print("\n--- Tennis Surface Adjustment Tests ---")
    base = 0.68
    print(f"Base probability: {base}")
    print(f"Clay specialist: {adjust_tennis_surface(base, 'clay', 'nadal_specialty')}")
    print(f"Grass big serve: {adjust_tennis_surface(base, 'grass', 'big_serve')}")
    print(f"Hard court: {adjust_tennis_surface(base, 'hard')}")
