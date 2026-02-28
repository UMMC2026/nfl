from scipy.stats import norm

def blowout_risk_analysis(spread: float, total: float, player_tier: str):
    """
    Calculates the probability of a blowout and its impact on the player.
    Tier: 'STAR' (benched in blowout) | 'BENCH' (gains minutes in blowout)
    """
    blowout_threshold = 14.5 
    prob_blowout = 1 - (norm.cdf(blowout_threshold, loc=abs(spread), scale=12.0) - 
                        norm.cdf(-blowout_threshold, loc=abs(spread), scale=12.0))
    if player_tier == 'STAR':
        impact_multiplier = 1 - (prob_blowout * 0.25)
    elif player_tier == 'BENCH':
        impact_multiplier = 1 + (prob_blowout * 0.15)
    else:
        impact_multiplier = 1.0
    return {
        "blowout_prob": round(prob_blowout, 3),
        "impact_multiplier": round(impact_multiplier, 3),
        "is_high_risk": prob_blowout > 0.35
    }
