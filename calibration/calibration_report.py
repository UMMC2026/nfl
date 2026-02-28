"""
Monthly Calibration Report for CBB — Computes Brier score and reliability for all picks.
"""
import csv
from pathlib import Path
from collections import defaultdict

LOG_PATH = Path(__file__).parent / "picks.csv"


def compute_brier_score(probabilities, outcomes):
    return sum((p - o) ** 2 for p, o in zip(probabilities, outcomes)) / len(probabilities)


def generate_monthly_report(month: str):
    """
    Generate calibration report for a given month (YYYY-MM).
    """
    probabilities = []
    outcomes = []
    with open(LOG_PATH, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not row["timestamp"].startswith(month):
                continue
            if row["result"] not in ("WIN", "LOSS"):
                continue
            probabilities.append(float(row["probability"]))
            outcomes.append(1.0 if row["result"] == "WIN" else 0.0)
    if not probabilities:
        print(f"No picks found for {month}.")
        return
    brier = compute_brier_score(probabilities, outcomes)
    print(f"Calibration Report for {month}")
    print(f"Total Picks: {len(probabilities)}")
    print(f"Brier Score: {brier:.4f}")
    # Reliability: bin by decile
    bins = defaultdict(lambda: [0, 0])
    for p, o in zip(probabilities, outcomes):
        bin_idx = int(p * 10)
        bins[bin_idx][0] += 1
        bins[bin_idx][1] += o
    print("Reliability by decile:")
    for i in range(10, -1, -1):
        n, wins = bins[i]
        if n:
            print(f"{i*10:2d}-{i*10+9:2d}%: {wins/n:.2%} win rate over {n} picks")
        else:
            print(f"{i*10:2d}-{i*10+9:2d}%: No picks")
