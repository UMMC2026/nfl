# Template for integrating a new stat type into the simulation and governance pipeline
from engine.stat_sim_starters import simulate_1q_points, simulate_double_double
from engine.governance_gate import final_governance_check

def process_new_stat(player, player_game_logs, context, stat_type, market_line, side):
    if stat_type == "1Q_POINTS":
        sim_result = simulate_1q_points(player_game_logs, context)
    elif stat_type == "DOUBLE_DOUBLE":
        sim_result = simulate_double_double(player_game_logs, context)
    else:
        raise ValueError(f"Unknown stat_type: {stat_type}")
    projection = {
        'hist_min': sim_result['hist_min'],
        'rot_rank': player.rotation_rank,
        'is_starter': player.is_starter,
        'active_teammates': context['active_teammates'],
        'spread': context['spread'],
        'total': context['total'],
        'player_tier': player.tier,
        'sim_mean': sim_result['mean'],
        'sim_std': sim_result['std'],
        'line': market_line,
        'role_entropy': sim_result.get('role_entropy', 0.1),
        'left_tail_prob': sim_result.get('left_tail_prob', 0.15),
        'right_tail_prob': sim_result.get('right_tail_prob', 0.15),
        'side': side
    }
    result = final_governance_check(projection)
    if result['tier'] != 'SKIP':
        print(f"SURFACE: {player.name} {stat_type} {side} {market_line} | Tier: {result['tier']} | ESS: {result['ess_score']}")
    else:
        print(f"SKIP: {player.name} {stat_type} {side} {market_line} | Reason: ESS too low or high risk")
