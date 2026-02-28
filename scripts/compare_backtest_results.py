"""
Compare two specialist backtest result JSON files and print metric deltas.

Usage:
  python scripts/compare_backtest_results.py \
    --a outputs/specialist_backtest_result_baseline.json \
    --b outputs/specialist_backtest_result.json
"""

import argparse
import json


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_pct(x: float) -> str:
    return f"{x*100:.2f}%" if x <= 1.0 else f"{x:.2f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    args = ap.parse_args()

    A = _load(args.a)
    B = _load(args.b)

    def get(d, k, default=0.0):
        v = d.get(k, default)
        try:
            return float(v)
        except Exception:
            return default

    metrics = [
        ("brier", False),
        ("hit_rate", True),
        ("avg_confidence", True),
        ("false_confidence_rate", True),
        ("samples", False),
    ]

    print("=== BACKTEST COMPARISON ===")
    for name, is_pct in metrics:
        a = get(A, name)
        b = get(B, name)
        delta = b - a
        if is_pct:
            print(f"{name:24} A={_fmt_pct(a)}  B={_fmt_pct(b)}  Δ={_fmt_pct(delta)}")
        else:
            print(f"{name:24} A={a:.4f}  B={b:.4f}  Δ={delta:.4f}")

    print("\nPer-bucket sample counts:")
    ga = A.get("groups", {})
    gb = B.get("groups", {})
    all_keys = sorted(set(ga) | set(gb))
    for k in all_keys:
        na = int(ga.get(k, 0) or 0)
        nb = int(gb.get(k, 0) or 0)
        print(f"  {k:6}  A={na:4d}  B={nb:4d}  Δ={nb-na:+4d}")


if __name__ == "__main__":
    main()
