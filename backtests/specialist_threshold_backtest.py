"""
Specialist threshold backtest harness.

Safely tunes classifier thresholds via grid search without changing classifier structure.
Groups by (stat, specialist_type, line_bucket) and reports metrics:
  - hit rate
  - brier score
  - calibration curve (by deciles)
  - false confidence rate (conf > 65% but miss)

Constraints:
  - >= 300 samples overall
  - >= 30 per line bucket
  - Reject any config with confidence inflation (avg_confidence - hit_rate > 0.05)

Usage:
  python backtests/specialist_threshold_backtest.py --input data/specialist_history.json \
      --stat 3PM --specialist CATCH_AND_SHOOT_3PM --grid "assisted_3pa_rate=0.60,0.65,0.70;pullup_3pa_rate=0.25,0.30,0.35;dribbles_per_shot=1.0,1.2,1.4"

Input JSON schema (list of records):
  {
    "player": str,
    "stat": str,
    "specialist_type": str,
    "line": float,
    "confidence": float,  # 0-100
    "hit": bool,          # outcome
    "features": {         # tracking features used by classifier
        "assisted_3pa_rate": float,
        "pullup_3pa_rate": float,
        "dribbles_per_shot": float,
        ...
    }
  }
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Any


def _bucket_line(line: float) -> str:
    """Bucket lines for grouping. Uses half-point buckets (e.g., 2.5, 3.5)."""
    try:
        # Round to nearest 0.5
        return f"{round(line * 2) / 2:.1f}"
    except Exception:
        return str(line)


def _brier_score(probs: List[float], outcomes: List[int]) -> float:
    if not probs or not outcomes or len(probs) != len(outcomes):
        return float("nan")
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def _calibration_curve(probs: List[float], outcomes: List[int], bins: int = 10) -> List[Tuple[float, float]]:
    """Return list of (avg_prob, hit_rate) for decile bins."""
    if not probs:
        return []
    pairs = sorted(zip(probs, outcomes), key=lambda x: x[0])
    n = len(pairs)
    bin_size = max(1, n // bins)
    curve = []
    for i in range(0, n, bin_size):
        chunk = pairs[i : i + bin_size]
        avg_p = sum(p for p, _ in chunk) / len(chunk)
        hr = sum(o for _, o in chunk) / len(chunk)
        curve.append((avg_p, hr))
    return curve


def _parse_grid(grid_str: str) -> Dict[str, List[float]]:
    grid: Dict[str, List[float]] = {}
    for part in grid_str.split(";"):
        part = part.strip()
        if not part:
            continue
        key, vals = part.split("=")
        grid[key.strip()] = [float(v) for v in vals.split(",")]
    return grid


def _apply_cns_3pm_thresholds(features: Dict[str, Any], thr: Dict[str, float]) -> bool:
    """Return True if record passes CATCH_AND_SHOOT_3PM thresholds."""
    return (
        (features.get("assisted_3pa_rate", 0.0) >= thr.get("assisted_3pa_rate", 0.0))
        and (features.get("pullup_3pa_rate", 1.0) < thr.get("pullup_3pa_rate", 1.0))
        and (features.get("dribbles_per_shot", 99.0) <= thr.get("dribbles_per_shot", 99.0))
    )


def backtest(input_path: str, stat: str, specialist: str, grid: Dict[str, List[float]]) -> Dict[str, Any]:
    with open(input_path, "r", encoding="utf-8") as f:
        data: List[Dict[str, Any]] = json.load(f)

    # Filter requested stat/specialist
    rows = [r for r in data if str(r.get("stat")).upper() == str(stat).upper() and str(r.get("specialist_type")) == specialist]

    # Group by line bucket
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        lb = _bucket_line(float(r.get("line", 0.0)))
        groups[lb].append(r)

    total_samples = sum(len(v) for v in groups.values())
    if total_samples < 300:
        return {"error": f"Insufficient samples: {total_samples} < 300"}

    if any(len(v) < 30 for v in groups.values()):
        return {"error": "Insufficient per-bucket samples (<30)"}

    # Grid search
    best: Dict[str, Any] = {"brier": math.inf}
    tried = 0
    for a in grid.get("assisted_3pa_rate", [0.65]):
        for p in grid.get("pullup_3pa_rate", [0.30]):
            for d in grid.get("dribbles_per_shot", [1.2]):
                thr = {"assisted_3pa_rate": a, "pullup_3pa_rate": p, "dribbles_per_shot": d}
                tried += 1

                probs: List[float] = []
                outcomes: List[int] = []
                misses_high_conf = 0
                for bucket, recs in groups.items():
                    for r in recs:
                        feats = r.get("features") or {}
                        if _apply_cns_3pm_thresholds(feats, thr):
                            conf = float(r.get("confidence", 50.0)) / 100.0
                            hit = 1 if bool(r.get("hit")) else 0
                            probs.append(conf)
                            outcomes.append(hit)
                            if conf > 0.65 and hit == 0:
                                misses_high_conf += 1

                if not probs:
                    continue

                hr = sum(outcomes) / len(outcomes)
                avg_conf = sum(probs) / len(probs)
                brier = _brier_score(probs, outcomes)
                curve = _calibration_curve(probs, outcomes)
                false_conf_rate = misses_high_conf / len(outcomes)

                # Reject inflation
                if avg_conf - hr > 0.05:
                    continue

                if brier < best["brier"]:
                    best = {
                        "thresholds": thr,
                        "brier": brier,
                        "hit_rate": hr,
                        "avg_confidence": avg_conf,
                        "false_confidence_rate": false_conf_rate,
                        "calibration_curve": curve,
                        "samples": len(outcomes),
                        "groups": {k: len(v) for k, v in groups.items()},
                        "tried": tried,
                    }

    if math.isinf(best["brier"]):
        return {"error": "No valid configuration (inflation or empty)."}

    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to JSON dataset")
    ap.add_argument("--stat", required=True, help="Stat key, e.g., 3PM")
    ap.add_argument("--specialist", required=True, help="Specialist type, e.g., CATCH_AND_SHOOT_3PM")
    ap.add_argument("--grid", required=False, default="assisted_3pa_rate=0.60,0.65,0.70;pullup_3pa_rate=0.25,0.30,0.35;dribbles_per_shot=1.0,1.2,1.4")
    ap.add_argument("--output", required=False, default="outputs/specialist_backtest_result.json")
    args = ap.parse_args()

    grid = _parse_grid(args.grid)
    res = backtest(args.input, args.stat, args.specialist, grid)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[OK] Saved backtest result: {args.output}")
    if "error" in res:
        print(f"[!] Error: {res['error']}")


if __name__ == "__main__":
    main()
