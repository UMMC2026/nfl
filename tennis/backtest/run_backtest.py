"""
Tennis Backtest Runner
======================
CLI for running backtests on historical data.

Usage:
    python tennis/backtest/run_backtest.py --predictions <file> --results <file>
    python tennis/backtest/run_backtest.py --dir tennis/backtest/data/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BACKTEST_DIR = Path(__file__).parent
TENNIS_DIR = BACKTEST_DIR.parent
sys.path.insert(0, str(TENNIS_DIR))

from backtest.backtest_engine import (
    backtest,
    check_thresholds,
    print_backtest_report,
)

DATA_DIR = BACKTEST_DIR / "data"
RESULTS_DIR = BACKTEST_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_predictions(path: Path) -> list:
    """Load predictions from JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_results(path: Path) -> dict:
    """Load results from JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    
    # Convert to dict keyed by match_id if it's a list
    if isinstance(data, list):
        return {r.get("match_id", str(i)): r for i, r in enumerate(data)}
    return data


def main():
    parser = argparse.ArgumentParser(description="Tennis Backtest Runner")
    parser.add_argument("--predictions", help="Path to predictions JSON")
    parser.add_argument("--results", help="Path to results JSON")
    parser.add_argument("--dir", help="Directory containing predictions.json and results.json")
    parser.add_argument("--output", help="Output file for backtest results")
    parser.add_argument("--check-only", action="store_true", help="Only check thresholds")
    
    args = parser.parse_args()
    
    # Determine file paths
    if args.dir:
        data_dir = Path(args.dir)
        pred_path = data_dir / "predictions.json"
        res_path = data_dir / "results.json"
    elif args.predictions and args.results:
        pred_path = Path(args.predictions)
        res_path = Path(args.results)
    else:
        # Default to data directory
        pred_path = DATA_DIR / "historical_predictions.json"
        res_path = DATA_DIR / "historical_results.json"
    
    # Check files exist
    if not pred_path.exists():
        print(f"❌ Predictions file not found: {pred_path}")
        print("\nCreate sample files in tennis/backtest/data/:")
        print("  - historical_predictions.json")
        print("  - historical_results.json")
        return 1
    
    if not res_path.exists():
        print(f"❌ Results file not found: {res_path}")
        return 1
    
    # Load data
    print(f"Loading predictions: {pred_path}")
    predictions = load_predictions(pred_path)
    print(f"  → {len(predictions)} predictions")
    
    print(f"Loading results: {res_path}")
    results = load_results(res_path)
    print(f"  → {len(results)} results")
    
    # Run backtest
    print("\nRunning backtest...")
    bt_results = backtest(predictions, results)
    
    # Print report
    print_backtest_report(bt_results)
    
    # Save results
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = RESULTS_DIR / f"backtest_{ts}.json"
    
    output_data = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "predictions_file": str(pred_path),
        "results_file": str(res_path),
        "prediction_count": len(predictions),
        "result_count": len(results),
        "engines": {k: v.to_dict() for k, v in bt_results.items()},
    }
    
    passed, violations = check_thresholds(bt_results)
    output_data["thresholds_passed"] = passed
    output_data["violations"] = violations
    
    out_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
    print(f"\nResults saved: {out_path}")
    
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
