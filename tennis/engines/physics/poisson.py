"""Simple Poisson sampler.

We avoid numpy/scipy to keep the repo lightweight and runnable in constrained
execution environments.

This is used for approximate ace / double-fault counts conditioned on match
length (service games).
"""

from __future__ import annotations

import math
import random


def poisson(lam: float, rng: random.Random | None = None) -> int:
    """Sample from Poisson(lam).

    Uses Knuth's algorithm for small/medium lam. For large lam, uses a normal
    approximation to keep runtime bounded.
    """

    r = rng or random
    lam_f = float(lam)
    if lam_f <= 0.0:
        return 0

    # Normal approximation for large means.
    if lam_f >= 50.0:
        x = r.gauss(lam_f, math.sqrt(lam_f))
        return max(0, int(round(x)))

    # Knuth
    L = math.exp(-lam_f)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= r.random()
    return k - 1
