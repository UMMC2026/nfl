import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from engine.governance_gate import final_governance_check

# Example projection dictionary
projection = {
    'hist_min': [34.5, 36.0, 35.0, 33.5, 34.0],
    'rot_rank': 1,
    'is_starter': True,
    'active_teammates': 10,
    'spread': -13.5,
    'total': 225.0,
    'player_tier': 'STAR',
    'sim_mean': 28.5,
    'sim_std': 4.2,
    'line': 28.5,
    'role_entropy': 0.12,
    'left_tail_prob': 0.18,
    'right_tail_prob': 0.09,
    'side': 'OVER'
}


examples = [
    # High blowout risk, star player, OVER
    {
        'hist_min': [34.5, 36.0, 35.0, 33.5, 34.0],
        'rot_rank': 1,
        'is_starter': True,
        'active_teammates': 10,
        'spread': -18.0,
        'total': 220.0,
        'player_tier': 'STAR',
        'sim_mean': 29.0,
        'sim_std': 5.0,
        'line': 28.5,
        'role_entropy': 0.10,
        'left_tail_prob': 0.22,
        'right_tail_prob': 0.08,
        'side': 'OVER'
    },
    # Low blowout risk, bench player, OVER
    {
        'hist_min': [18.0, 19.5, 17.0, 20.0, 18.5],
        'rot_rank': 8,
        'is_starter': False,
        'active_teammates': 11,
        'spread': -2.5,
        'total': 228.0,
        'player_tier': 'BENCH',
        'sim_mean': 13.5,
        'sim_std': 2.8,
        'line': 12.5,
        'role_entropy': 0.18,
        'left_tail_prob': 0.12,
        'right_tail_prob': 0.15,
        'side': 'OVER'
    },
    # High volatility, low minute stability, UNDER
    {
        'hist_min': [22.0, 30.0, 15.0, 28.0, 10.0],
        'rot_rank': 6,
        'is_starter': False,
        'active_teammates': 12,
        'spread': 7.0,
        'total': 215.0,
        'player_tier': 'BENCH',
        'sim_mean': 16.0,
        'sim_std': 6.5,
        'line': 17.5,
        'role_entropy': 0.35,
        'left_tail_prob': 0.25,
        'right_tail_prob': 0.30,
        'side': 'UNDER'
    },
    # Strong starter, low blowout risk, OVER
    {
        'hist_min': [36.0, 37.0, 35.5, 36.5, 37.0],
        'rot_rank': 2,
        'is_starter': True,
        'active_teammates': 9,
        'spread': 1.5,
        'total': 230.0,
        'player_tier': 'STAR',
        'sim_mean': 27.0,
        'sim_std': 3.2,
        'line': 25.5,
        'role_entropy': 0.09,
        'left_tail_prob': 0.10,
        'right_tail_prob': 0.07,
        'side': 'OVER'
    }
]

for i, proj in enumerate(examples, 1):
    print(f"\n--- Example {i} ---")
    result = final_governance_check(proj)
    print(f"ESS Score: {result['ess_score']}")
    print(f"Tier: {result['tier']}")
    print(f"Adjusted Mean: {result['adj_mean']}")
    print(f"Blowout Probability: {result['blowout_prob']}")
    if result['tier'] == 'SKIP':
        print("Pick is gated: SKIP due to low ESS or high blowout risk.")
    else:
        print(f"Pick is eligible: {result['tier']} tier.")
