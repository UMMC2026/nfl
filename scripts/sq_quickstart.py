import os
import sys

# Ensure project root is on path when running from scripts/
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sports_quant.simulation.monte_carlo import run_monte_carlo
from sports_quant.pick_engine.select import select_picks
from sports_quant.pick_engine.scoring import score

if __name__ == "__main__":
    # Demo: simulate an NFL receiving yards prop
    line = 44.5
    mean = 52.0
    variance = 120.0
    result = run_monte_carlo(line=line, mean=mean, variance=variance, dist="normal", n_sims=10000, clip_min=0.0)
    result.update({"stat": "WR_rec_yards"})

    picks = select_picks([result], min_conf=0.60)
    for p in picks:
        s = score(edge=p["expected_value"], confidence=p["confidence"], corr_penalty=1.0)
        direction = "HIGHER" if p["p_over"] >= 0.5 else "LOWER"
        print(f"Stat: {p['stat']} | Line: {p['line']} | Dir: {direction} | Conf: {p['confidence']:.2f} | Score: {s:.2f}")
