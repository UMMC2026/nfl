from __future__ import annotations

import random

from tennis.engines.physics.hold_math import hold_probability, infer_point_prob_from_hold
from tennis.engines.physics.match_simulator import simulate_match_best_of_3


def test_hold_probability_bounds_and_monotone():
    ps = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    holds = [hold_probability(p) for p in ps]

    assert all(0.0 <= h <= 1.0 for h in holds)
    # monotone increasing
    assert all(holds[i] <= holds[i + 1] for i in range(len(holds) - 1))


def test_infer_point_prob_from_hold_roundtrip():
    # pick a plausible hold rate
    target_hold = 0.78
    res = infer_point_prob_from_hold(target_hold)
    assert 0.0 <= res.p_point <= 1.0
    assert abs(res.p_hold - target_hold) < 1e-3


def test_simulate_match_best_of_3_reasonable_ranges():
    rng = random.Random(123)
    sample = simulate_match_best_of_3(0.63, 0.62, rng=rng)

    assert sample.sets_a in (0, 1, 2)
    assert sample.sets_b in (0, 1, 2)
    assert sample.sets_a == 2 or sample.sets_b == 2

    assert sample.total_games == sample.games_a + sample.games_b
    assert sample.total_games >= 12

    assert 6 <= sample.first_set_games_a + sample.first_set_games_b <= 13
    assert sample.first_set_total_games == sample.first_set_games_a + sample.first_set_games_b

    assert sample.service_games_a > 0
    assert sample.service_games_b > 0
