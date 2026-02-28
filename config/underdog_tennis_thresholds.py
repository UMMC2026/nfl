"""
UNDERDOG FANTASY TENNIS-SPECIFIC THRESHOLDS
Based on actual Underdog market analysis - January 29, 2026

This configuration is calibrated specifically for Underdog Fantasy
tennis props markets shown in user screenshots.
"""

# ============================================================================
# UNDERDOG TENNIS MARKET CONFIDENCE CAPS
# ============================================================================

UNDERDOG_TENNIS_CAPS = {
    # -------------------------------------------------------------------------
    # HIGH CONFIDENCE MARKETS (0.65-0.70)
    # These markets have lower variance and more predictable outcomes
    # -------------------------------------------------------------------------
    'games_won': {
        'base_threshold': 0.70,
        'description': 'Total games won in match',
        'variance': 'LOW',
        'sample_lines': [9.5, 11.5, 12.5, 16.5, 19.5],
        'features': [
            'player_avg_games_per_match',
            'opponent_avg_games_allowed',
            'surface_games_adjustment',
            'h2h_games_history'
        ],
        'notes': 'Most stable prop - accumulates over entire match'
    },
    
    'first_set_games_won': {
        'base_threshold': 0.68,
        'description': '1st set games won',
        'variance': 'LOW-MEDIUM',
        'sample_lines': [3.5, 4.5, 5.5],
        'features': [
            'first_set_strength',
            'opponent_first_set_weakness',
            'serve_hold_percentage',
            'break_point_conversion'
        ],
        'notes': 'Good market for strong starters'
    },
    
    'aces': {
        'base_threshold': 0.65,
        'description': 'Total aces served',
        'variance': 'MEDIUM',
        'sample_lines': [2.5, 4.5, 5.5, 7.5, 10.5],
        'player_dependent': True,
        'features': [
            'player_ace_per_match_avg',
            'surface_ace_boost',  # Grass > Hard > Clay
            'opponent_return_quality',
            'indoor_outdoor_factor'
        ],
        'notes': 'Highly player-dependent - big servers crush this',
        'surface_modifiers': {
            'grass': +0.05,   # Fastest surface, more aces
            'hard': 0.00,     # Neutral
            'clay': -0.08     # Slowest, fewer aces
        }
    },
    
    # -------------------------------------------------------------------------
    # MEDIUM CONFIDENCE MARKETS (0.58-0.64)
    # These have moderate variance and require careful analysis
    # -------------------------------------------------------------------------
    'sets_won': {
        'base_threshold': 0.62,
        'description': 'Total sets won',
        'variance': 'MEDIUM',
        'sample_lines': [0.5, 2.5],  # Usually binary (0/1 or 2/3)
        'features': [
            'match_win_probability',
            'set_win_consistency',
            'opponent_set_loss_rate'
        ],
        'notes': 'Correlated with match outcome - use carefully'
    },
    
    'breakpoints_won': {
        'base_threshold': 0.60,
        'description': 'Breakpoints converted',
        'variance': 'MEDIUM-HIGH',
        'sample_lines': [1.5, 2.5, 4.5],
        'features': [
            'break_point_conversion_rate',
            'opponent_break_point_save_rate',
            'return_game_strength',
            'pressure_situation_performance'
        ],
        'notes': 'Depends heavily on opponent serve quality'
    },
    
    'sets_played': {
        'base_threshold': 0.58,
        'description': 'Total sets in match',
        'variance': 'HIGH',
        'sample_lines': [2.5],  # Usually 2 vs 3 sets in BO3
        'features': [
            'competitiveness_metric',
            'h2h_set_outcomes',
            'rank_differential',
            'recent_match_competitiveness'
        ],
        'notes': 'Hard to predict - binary outcome with high variance',
        'format_dependent': {
            'best_of_3': 0.58,   # More variance
            'best_of_5': 0.55    # Even more variance (Grand Slams)
        }
    },
    
    # -------------------------------------------------------------------------
    # LOWER CONFIDENCE MARKETS (0.55-0.57)
    # High variance, use with extreme caution
    # -------------------------------------------------------------------------
    'double_faults': {
        'base_threshold': 0.56,
        'description': 'Double faults committed',
        'variance': 'VERY HIGH',
        'sample_lines': [1.5, 2.5],
        'features': [
            'player_df_per_match_avg',
            'recent_form_df_trend',
            'pressure_situation_df_rate',
            'surface_df_correlation'
        ],
        'notes': 'Extremely volatile - avoid unless strong edge',
        'risk_factors': [
            'Can spike in pressure moments',
            'Weather affects serve accuracy',
            'Fatigue increases DFs late in tournament'
        ]
    },
    
    'tiebreakers_played': {
        'base_threshold': 0.55,
        'description': 'Tiebreakers in match',
        'variance': 'VERY HIGH',
        'sample_lines': [0.5],  # Binary: 0 or 1+
        'features': [
            'serve_dominance_both_players',
            'h2h_tiebreak_frequency',
            'set_score_competitiveness'
        ],
        'notes': 'Rare event - extremely hard to predict',
        'avoid_unless': 'Both players have elite serve stats'
    },
    
    'first_set_games_played': {
        'base_threshold': 0.55,
        'description': 'Total games in first set',
        'variance': 'HIGH',
        'sample_lines': [8.5, 10.5],
        'features': [
            'first_set_competitiveness',
            'serve_hold_rates_both_players',
            'break_point_opportunities'
        ],
        'notes': 'Similar to tiebreakers - depends on competitiveness'
    }
}


# ============================================================================
# PLAYER-SPECIFIC ADJUSTMENTS
# ============================================================================

PLAYER_STYLE_MODIFIERS = {
    # Big servers (e.g., Isner, Karlovic, Kyrgios)
    'big_server': {
        'aces': +0.08,
        'tiebreakers_played': +0.05,
        'breakpoints_won': -0.03,  # Less break opportunities
        'double_faults': +0.02     # Slight increase in risk
    },
    
    # Baseline grinders (e.g., Nadal on clay, Medvedev)
    'baseline_grinder': {
        'games_won': +0.05,
        'sets_played': +0.03,      # More competitive sets
        'aces': -0.05,
        'tiebreakers_played': +0.02
    },
    
    # Aggressive returners (e.g., Djokovic, Agassi)
    'aggressive_returner': {
        'breakpoints_won': +0.08,
        'games_won': +0.04,
        'opponent_aces': -0.03     # Negates opponent's ace prop
    },
    
    # All-court players (e.g., Federer, Alcaraz)
    'all_court': {
        # Neutral adjustments - versatile style
        'surface_adjustment_required': True
    }
}


# ============================================================================
# TOURNAMENT STAGE ADJUSTMENTS
# ============================================================================

TOURNAMENT_STAGE_MODIFIERS = {
    'early_rounds': {
        'confidence_boost': +0.03,  # More predictable with rank gaps
        'upset_risk': 0.15           # 15% upset probability
    },
    
    'quarterfinals': {
        'confidence_boost': 0.00,
        'upset_risk': 0.25
    },
    
    'semifinals': {
        'confidence_boost': -0.02,   # Elite players, more competitive
        'upset_risk': 0.30
    },
    
    'finals': {
        'confidence_boost': -0.05,   # Highest variance, best players
        'upset_risk': 0.35
    }
}


# ============================================================================
# HELPER FUNCTIONS FOR UNDERDOG MARKETS
# ============================================================================

def get_underdog_threshold(market_type: str, 
                          player_style: str = None,
                          tournament_stage: str = 'early_rounds',
                          surface: str = 'hard') -> float:
    """
    Get calibrated threshold for specific Underdog tennis market
    
    Args:
        market_type: Type of prop (e.g., 'aces', 'games_won')
        player_style: Player style modifier (optional)
        tournament_stage: Current tournament stage
        surface: Court surface (grass, hard, clay)
        
    Returns:
        Calibrated confidence threshold
        
    Example:
        >>> get_underdog_threshold('aces', player_style='big_server', 
        ...                        tournament_stage='early_rounds', 
        ...                        surface='grass')
        0.78  # 0.65 base + 0.08 big_server + 0.05 grass
    """
    # Get base threshold
    market_config = UNDERDOG_TENNIS_CAPS.get(market_type, {})
    base_threshold = market_config.get('base_threshold', 0.55)
    
    # Apply player style modifier
    if player_style and player_style in PLAYER_STYLE_MODIFIERS:
        style_mod = PLAYER_STYLE_MODIFIERS[player_style].get(market_type, 0.0)
        base_threshold += style_mod
    
    # Apply tournament stage modifier
    stage_config = TOURNAMENT_STAGE_MODIFIERS.get(tournament_stage, {})
    base_threshold += stage_config.get('confidence_boost', 0.0)
    
    # Apply surface modifier (if market-specific)
    if 'surface_modifiers' in market_config and surface:
        surface_mod = market_config['surface_modifiers'].get(surface, 0.0)
        base_threshold += surface_mod
    
    # Clamp to valid range [0.50, 0.85]
    return max(0.50, min(0.85, base_threshold))


def validate_underdog_market(market_type: str, line: float) -> dict:
    """
    Validate that a prop line matches expected Underdog ranges
    
    Args:
        market_type: Type of market
        line: Proposed line value
        
    Returns:
        Validation result with warnings/errors
    """
    market_config = UNDERDOG_TENNIS_CAPS.get(market_type)
    
    if not market_config:
        return {
            'valid': False,
            'error': f"Unknown market type: {market_type}"
        }
    
    sample_lines = market_config.get('sample_lines', [])
    
    # Check if line is within reasonable range
    if sample_lines:
        min_line = min(sample_lines)
        max_line = max(sample_lines)
        
        if line < min_line * 0.5 or line > max_line * 2:
            return {
                'valid': False,
                'warning': f"Line {line} outside expected range {sample_lines}",
                'expected_range': f"{min_line} to {max_line}"
            }
    
    return {
        'valid': True,
        'variance': market_config.get('variance', 'UNKNOWN'),
        'base_threshold': market_config.get('base_threshold')
    }


def get_market_priority(market_type: str) -> str:
    """
    Get priority level for different Underdog markets
    
    Returns:
        'HIGH', 'MEDIUM', or 'LOW' priority
    """
    market_config = UNDERDOG_TENNIS_CAPS.get(market_type, {})
    base_threshold = market_config.get('base_threshold', 0.55)
    
    if base_threshold >= 0.68:
        return 'HIGH'
    elif base_threshold >= 0.60:
        return 'MEDIUM'
    else:
        return 'LOW'


# ============================================================================
# UNDERDOG PARLAY CORRELATION RULES
# ============================================================================

CORRELATED_MARKETS = {
    # These markets should NOT be parlayed together
    'avoid_parlay': [
        ('games_won', 'sets_won'),        # Directly correlated
        ('aces', 'double_faults'),        # Both measure serve
        ('sets_won', 'sets_played'),      # Directly correlated
        ('first_set_games_won', 'games_won')  # Correlated
    ],
    
    # These markets CAN be parlayed (independent or negatively correlated)
    'safe_parlay': [
        ('player_a_aces', 'player_b_breakpoints'),  # Different players
        ('games_won', 'double_faults'),             # Somewhat independent
        ('aces', 'breakpoints_won')                 # Different skill sets
    ]
}


# ============================================================================
# TESTING & VALIDATION
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("UNDERDOG TENNIS MARKET ANALYSIS")
    print("="*70 + "\n")
    
    # Test all markets
    print("Market Priority Analysis:")
    print("-" * 70)
    
    for market, config in UNDERDOG_TENNIS_CAPS.items():
        priority = get_market_priority(market)
        threshold = config['base_threshold']
        variance = config['variance']
        
        print(f"{market:25} | Priority: {priority:6} | "
              f"Threshold: {threshold:.2f} | Variance: {variance}")
    
    # Test threshold adjustments
    print("\n" + "="*70)
    print("EXAMPLE THRESHOLD CALCULATIONS")
    print("="*70 + "\n")
    
    examples = [
        ('aces', 'big_server', 'early_rounds', 'grass'),
        ('games_won', 'baseline_grinder', 'semifinals', 'clay'),
        ('double_faults', None, 'finals', 'hard')
    ]
    
    for market, style, stage, surface in examples:
        threshold = get_underdog_threshold(market, style, stage, surface)
        print(f"{market} ({style or 'neutral'}, {stage}, {surface}): {threshold:.3f}")
    
    # Test line validation
    print("\n" + "="*70)
    print("LINE VALIDATION TESTS")
    print("="*70 + "\n")
    
    test_lines = [
        ('aces', 10.5),
        ('games_won', 15.5),
        ('double_faults', 2.5),
        ('sets_won', 2.5)
    ]
    
    for market, line in test_lines:
        result = validate_underdog_market(market, line)
        status = "✅" if result['valid'] else "⚠️"
        print(f"{status} {market} line {line}: {result}")
