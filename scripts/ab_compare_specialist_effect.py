"""
A/B comparison of pipeline outputs to see specialist feature impact.

Loads two edge files (JSON lists of props) and matches entries by a composite key:
  (player, stat, line, direction)

Reports:
  - Count of matched edges
  - Confidence deltas (mean/median/pctiles)
  - Breakdown by stat
  - Top N increases/decreases

Usage:
  python scripts/ab_compare_specialist_effect.py --baseline outputs/EDGES_BASELINE.json --enriched outputs/EDGES_ENRICHED.json
"""

from __future__ import annotations

import argparse
import json
import statistics as stats
from collections import defaultdict
from typing import Dict, Any, List, Tuple


Key = Tuple[str, str, float, str]


def _load_list(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _key_of(p: Dict[str, Any]) -> Key:
    return (
        str(p.get("player", "")),
        str(p.get("stat", "")),
        float(p.get("line", 0.0)),
        str(p.get("direction", "")),
    )


def _confidence(p: Dict[str, Any]) -> float:
    # Prefer effective_confidence; fallback to model_confidence
    if isinstance(p.get("effective_confidence"), (int, float)):
        return float(p["effective_confidence"])
    if isinstance(p.get("model_confidence"), (int, float)):
        return float(p["model_confidence"])
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--enriched", required=True)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    A = _load_list(args.baseline)
    B = _load_list(args.enriched)

    mapA: Dict[Key, Dict[str, Any]] = { _key_of(p): p for p in A }
    mapB: Dict[Key, Dict[str, Any]] = { _key_of(p): p for p in B }

    keys = sorted(set(mapA) & set(mapB))
    print(f"Matched edges: {len(keys)}")

    deltas: List[Tuple[Key, float]] = []
    by_stat: Dict[str, List[float]] = defaultdict(list)
    for k in keys:
        ca = _confidence(mapA[k])
        cb = _confidence(mapB[k])
        d = cb - ca
        deltas.append((k, d))
        by_stat[k[1]].append(d)

    if not deltas:
        print("No matches; check inputs.")
        return

    values = [d for _, d in deltas]
    print(f"Δ confidence: mean={stats.mean(values):.2f}  median={stats.median(values):.2f}  min={min(values):.2f}  max={max(values):.2f}")

    print("\nBreakdown by stat:")
    for s, arr in sorted(by_stat.items()):
        print(f"  {s:6}  n={len(arr):4d}  mean={stats.mean(arr):.2f}  median={stats.median(arr):.2f}")

    deltas_sorted = sorted(deltas, key=lambda x: x[1], reverse=True)
    print("\nTop increases:")
    for (player, stat, line, direction), d in deltas_sorted[:args.top]:
        print(f"  +{d:.1f}  {player} {stat} {direction} {line}")

    print("\nTop decreases:")
    for (player, stat, line, direction), d in list(reversed(deltas_sorted))[:args.top]:
        print(f"  {d:.1f}  {player} {stat} {direction} {line}")


if __name__ == "__main__":
    main()
