import itertools
from typing import List
from ufa.analysis.payouts import PayoutTable

def entry_ev(p_list: List[float], table: PayoutTable, legs: int) -> float:
    """
    EV in stake units: EV = E[payout] - 1
    Independence assumption (MVP). Add correlation model later.
    """
    if legs != len(p_list):
        raise ValueError("legs must equal len(p_list)")

    payout_map = table.payout_units.get(legs)
    if not payout_map:
        raise ValueError(f"No payout configured for legs={legs}")

    ev_payout = 0.0
    for outcomes in itertools.product([0, 1], repeat=legs):
        k = sum(outcomes)
        prob = 1.0
        for hit, p in zip(outcomes, p_list):
            prob *= (p if hit else (1.0 - p))
        ev_payout += prob * float(payout_map.get(k, 0.0))

    return float(ev_payout - 1.0)

def monte_carlo_ev(p_list: List[float], table: PayoutTable, legs: int, trials: int = 10000):
    """
    Monte Carlo simulation of entry EV and payout distribution.

    Returns a dict with:
      - ev_mean: estimated EV in stake units
      - hits_prob: mapping of k_hits -> empirical probability
      - payout_mean: mean payout multiplier
      - payout_std: stddev of payout multiplier
    """
    import random
    if legs != len(p_list):
        raise ValueError("legs must equal len(p_list)")

    payout_map = table.payout_units.get(legs)
    if not payout_map:
        raise ValueError(f"No payout configured for legs={legs}")

    hit_counts = {k: 0 for k in range(legs + 1)}
    payouts = []

    for _ in range(int(trials)):
        k = 0
        for p in p_list:
            if random.random() < float(p):
                k += 1
        hit_counts[k] += 1
        payouts.append(float(payout_map.get(k, 0.0)))

    hits_prob = {k: c / float(trials) for k, c in hit_counts.items()}
    payout_mean = sum(payouts) / float(trials)
    # Welford or simple variance
    mean = payout_mean
    var = sum((x - mean) ** 2 for x in payouts) / max(1, (trials - 1))
    payout_std = var ** 0.5

    return {
        "ev_mean": float(payout_mean - 1.0),
        "hits_prob": hits_prob,
        "payout_mean": float(payout_mean),
        "payout_std": float(payout_std),
    }
