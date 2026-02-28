"""
Hard fail test for specialist confidence inflation.

Reads the latest backtest result JSON and aborts (non-zero exit) if
  avg_confidence - hit_rate > 0.05.

Usage:
  python scripts/test_no_specialist_confidence_inflation.py --result outputs/specialist_backtest_result.json
"""

import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default="outputs/specialist_backtest_result.json")
    args = ap.parse_args()

    try:
        with open(args.result, "r", encoding="utf-8") as f:
            res = json.load(f)
    except Exception:
        print(f"[!] Missing or unreadable result file: {args.result}")
        sys.exit(2)

    if "error" in res:
        print(f"[!] Backtest error: {res['error']}")
        sys.exit(2)

    avg_conf = float(res.get("avg_confidence", 0.0))
    hit_rate = float(res.get("hit_rate", 0.0))
    diff = avg_conf - hit_rate
    print(f"avg_confidence={avg_conf:.3f}  hit_rate={hit_rate:.3f}  diff={diff:.3f}")

    if diff > 0.05:
        print("[FAIL] Confidence inflation detected (diff > 0.05). Aborting.")
        sys.exit(1)

    print("[OK] No confidence inflation detected.")


if __name__ == "__main__":
    main()
