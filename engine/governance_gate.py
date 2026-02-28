import numpy as np
from engine.edge_stability_engine import EdgeStabilityEngine
from engine.minute_stability import calculate_minute_stability
from engine.blowout_risk import blowout_risk_analysis

def final_governance_check(projection: dict):
    """
    The final bridge.
    """
    m_stab = calculate_minute_stability(
        projection['hist_min'], 
        projection['rot_rank'], 
        projection['is_starter'],
        projection['active_teammates']
    )
    b_analysis = blowout_risk_analysis(
        projection['spread'], 
        projection['total'], 
        projection['player_tier']
    )
    adj_mean = projection['sim_mean'] * b_analysis['impact_multiplier']
    ess_engine = EdgeStabilityEngine()
    ess_score = ess_engine.calculate_ess(
        mean = adj_mean,
        line = projection['line'],
        sigma = projection['sim_std'],
        min_stability = m_stab,
        role_entropy = projection['role_entropy'],
        tail_risk = projection['left_tail_prob'] if projection['side'] == 'OVER' else projection['right_tail_prob']
    )
    if projection['side'] == 'OVER' and b_analysis['is_high_risk']:
        ess_score *= 0.7
    return {
        "ess_score": ess_score,
        "tier": ess_engine.get_tier(ess_score),
        "adj_mean": adj_mean,
        "blowout_prob": b_analysis['blowout_prob']
    }
