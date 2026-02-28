"""
CBB Calibration Audit — Track predicted vs actual hit rates.

Logs every pick with probability, tier, direction, stat, and game-script
gate results. After games resolve, records actual outcome (hit/miss).

Generates calibration reports showing:
  - Hit rate by probability bucket (55-60%, 60-65%, 65-70%, 70%+)
  - Hit rate by stat type
  - Hit rate by direction (HIGHER vs LOWER)
  - Game-script gate effectiveness (blocked picks that would have lost)

Usage:
  # Log picks from pipeline output
  python sports/cbb/calibration_audit.py --log outputs/cbb_signals.json

  # Resolve results after games finish
  python sports/cbb/calibration_audit.py --resolve

  # Generate calibration report
  python sports/cbb/calibration_audit.py --report

Implementation Date: 2026-02-15 (Fix 9)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Calibration log location
CALIBRATION_DIR = PROJECT_ROOT / "data" / "cbb"
CALIBRATION_LOG = CALIBRATION_DIR / "calibration_log.json"


def _load_log() -> List[Dict]:
    """Load calibration log from disk."""
    if CALIBRATION_LOG.exists():
        try:
            with open(CALIBRATION_LOG, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_log(entries: List[Dict]) -> None:
    """Save calibration log to disk."""
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_LOG, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def log_pick(edge: Dict, run_id: str = None) -> None:
    """
    Log a single pick for calibration tracking.
    
    Called after pipeline outputs edges. Stores predicted probability,
    tier, game-script gate info, and distribution metadata.
    """
    entry = {
        "logged_at": datetime.now().isoformat(),
        "run_id": run_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
        "edge_id": edge.get("edge_id", ""),
        "player": edge.get("player", ""),
        "team": edge.get("team", ""),
        "opponent": edge.get("opponent", ""),
        "stat": edge.get("stat", ""),
        "line": edge.get("line", 0),
        "direction": edge.get("direction", ""),
        "probability": edge.get("probability", 0),
        "tier": edge.get("tier", ""),
        "model": edge.get("model", ""),
        "mean_source": edge.get("mean_source", ""),
        "player_mean": edge.get("player_mean", 0),
        "game_script_gate": edge.get("game_script_gate", {}),
        "game_script_adjustment": edge.get("game_script_adjustment", {}),
        "calibration_capped": edge.get("calibration_capped", False),
        "distribution_type": (edge.get("decision_trace", {})
                              .get("distribution", {})
                              .get("type", "UNKNOWN")),
        "dispersion_ratio": (edge.get("decision_trace", {})
                             .get("distribution", {})
                             .get("dispersion_ratio")),
        # Result fields — filled in by resolve
        "actual_value": None,
        "hit": None,
        "resolved": False,
        "resolved_at": None,
    }
    
    entries = _load_log()
    
    # Deduplicate by edge_id + date
    date_str = datetime.now().strftime("%Y-%m-%d")
    existing = {(e["edge_id"], e.get("logged_at", "")[:10]) for e in entries}
    if (entry["edge_id"], date_str) in existing:
        return  # Already logged
    
    entries.append(entry)
    _save_log(entries)


def log_picks_from_file(filepath: str) -> int:
    """
    Log all non-SKIP picks from a pipeline output JSON file.
    
    Returns count of picks logged.
    """
    with open(filepath, "r") as f:
        data = json.load(f)
    
    edges = data if isinstance(data, list) else data.get("edges", [])
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    count = 0
    
    for edge in edges:
        if edge.get("tier", "SKIP") not in ("SKIP",):
            log_pick(edge, run_id=run_id)
            count += 1
    
    print(f"  Logged {count} picks to calibration ({CALIBRATION_LOG})")
    return count


def resolve_pick(edge_id: str, actual_value: float) -> bool:
    """
    Resolve a single pick with actual outcome.
    
    Returns True if pick was found and resolved.
    """
    entries = _load_log()
    
    for entry in entries:
        if entry["edge_id"] == edge_id and not entry.get("resolved"):
            entry["actual_value"] = actual_value
            direction = entry.get("direction", "").lower()
            line = entry.get("line", 0)
            
            if direction in ("higher", "over"):
                entry["hit"] = actual_value > line
            else:
                entry["hit"] = actual_value < line
            
            entry["resolved"] = True
            entry["resolved_at"] = datetime.now().isoformat()
            _save_log(entries)
            return True
    
    return False


def run_calibration_report(min_resolved: int = 5) -> Dict:
    """
    Generate calibration report from resolved picks.
    
    Returns dict with hit rates by bucket, stat, direction.
    """
    entries = _load_log()
    resolved = [e for e in entries if e.get("resolved") and e.get("hit") is not None]
    
    if len(resolved) < min_resolved:
        print(f"\n  ⚠ Only {len(resolved)} resolved picks — need {min_resolved}+ for report")
        return {"error": "insufficient_data", "resolved": len(resolved)}
    
    # ---- By probability bucket ----
    buckets = {
        "55-60%": (0.55, 0.60),
        "60-65%": (0.60, 0.65),
        "65-70%": (0.65, 0.70),
        "70%+": (0.70, 1.01),
    }
    bucket_results = {}
    for label, (lo, hi) in buckets.items():
        in_bucket = [e for e in resolved if lo <= e.get("probability", 0) < hi]
        if in_bucket:
            hits = sum(1 for e in in_bucket if e["hit"])
            bucket_results[label] = {
                "count": len(in_bucket),
                "hits": hits,
                "hit_rate": round(hits / len(in_bucket) * 100, 1),
                "expected_midpoint": round((lo + hi) / 2 * 100, 1),
            }
    
    # ---- By stat type ----
    stat_results = {}
    stats = set(e.get("stat", "").lower() for e in resolved)
    for stat in sorted(stats):
        by_stat = [e for e in resolved if e.get("stat", "").lower() == stat]
        if len(by_stat) >= 3:
            hits = sum(1 for e in by_stat if e["hit"])
            stat_results[stat] = {
                "count": len(by_stat),
                "hits": hits,
                "hit_rate": round(hits / len(by_stat) * 100, 1),
            }
    
    # ---- By direction ----
    direction_results = {}
    for direction in ("higher", "lower"):
        by_dir = [e for e in resolved if e.get("direction", "").lower() == direction]
        if by_dir:
            hits = sum(1 for e in by_dir if e["hit"])
            direction_results[direction] = {
                "count": len(by_dir),
                "hits": hits,
                "hit_rate": round(hits / len(by_dir) * 100, 1),
            }
    
    # ---- Game-script gate effectiveness ----
    # Look at blocked picks (in log with game_script_gate.passed = False)
    all_entries = [e for e in entries if e.get("game_script_gate", {}).get("passed") is False]
    gs_blocked = len(all_entries)
    gs_resolved_blocked = [e for e in all_entries if e.get("resolved")]
    gs_would_have_lost = sum(1 for e in gs_resolved_blocked if not e.get("hit", True))
    
    # ---- Distribution type effectiveness ----
    dist_results = {}
    for dtype in ("NEGATIVE_BINOMIAL", "POISSON", "TABLE_FALLBACK"):
        by_dist = [e for e in resolved if e.get("distribution_type", "") == dtype]
        if by_dist:
            hits = sum(1 for e in by_dist if e["hit"])
            dist_results[dtype] = {
                "count": len(by_dist),
                "hits": hits,
                "hit_rate": round(hits / len(by_dist) * 100, 1),
            }
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_logged": len(entries),
        "total_resolved": len(resolved),
        "overall_hit_rate": round(sum(1 for e in resolved if e["hit"]) / len(resolved) * 100, 1),
        "by_probability_bucket": bucket_results,
        "by_stat_type": stat_results,
        "by_direction": direction_results,
        "by_distribution": dist_results,
        "game_script_gate": {
            "total_blocked": gs_blocked,
            "blocked_resolved": len(gs_resolved_blocked),
            "blocked_would_have_lost": gs_would_have_lost,
            "save_rate": (round(gs_would_have_lost / len(gs_resolved_blocked) * 100, 1)
                          if gs_resolved_blocked else None),
        },
    }
    
    return report


def print_calibration_report(report: Dict) -> None:
    """Pretty-print the calibration report."""
    if report.get("error"):
        print(f"\n  {report['error']}: {report.get('resolved', 0)} resolved picks")
        return
    
    print("\n" + "=" * 60)
    print("  CBB CALIBRATION REPORT (v3.0)")
    print("=" * 60)
    print(f"  Generated: {report['generated_at'][:19]}")
    print(f"  Total Logged: {report['total_logged']}")
    print(f"  Total Resolved: {report['total_resolved']}")
    print(f"  Overall Hit Rate: {report['overall_hit_rate']}%")
    
    print("\n  --- By Probability Bucket ---")
    for bucket, data in report.get("by_probability_bucket", {}).items():
        expected = data.get("expected_midpoint", "?")
        actual = data["hit_rate"]
        delta = round(actual - expected, 1) if isinstance(expected, (int, float)) else "?"
        marker = "✓" if isinstance(delta, (int, float)) and abs(delta) <= 5 else "⚠"
        print(f"  {bucket}: {data['hits']}/{data['count']} = {actual}% "
              f"(expected ~{expected}%) [{marker} Δ={delta}%]")
    
    print("\n  --- By Stat Type ---")
    for stat, data in report.get("by_stat_type", {}).items():
        print(f"  {stat:12s}: {data['hits']}/{data['count']} = {data['hit_rate']}%")
    
    print("\n  --- By Direction ---")
    for direction, data in report.get("by_direction", {}).items():
        print(f"  {direction:8s}: {data['hits']}/{data['count']} = {data['hit_rate']}%")
    
    print("\n  --- By Distribution Model ---")
    for dtype, data in report.get("by_distribution", {}).items():
        print(f"  {dtype:22s}: {data['hits']}/{data['count']} = {data['hit_rate']}%")
    
    gs = report.get("game_script_gate", {})
    print(f"\n  --- Game Script Gate ---")
    print(f"  Total Blocked: {gs.get('total_blocked', 0)}")
    if gs.get("blocked_resolved"):
        print(f"  Blocked Resolved: {gs['blocked_resolved']}")
        print(f"  Would Have Lost: {gs['blocked_would_have_lost']}")
        print(f"  Save Rate: {gs.get('save_rate', 'N/A')}%")
    
    print("=" * 60)


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CBB Calibration Audit")
    parser.add_argument("--log", type=str, help="Log picks from pipeline output JSON")
    parser.add_argument("--resolve", action="store_true", help="Interactive resolve mode")
    parser.add_argument("--report", action="store_true", help="Generate calibration report")
    parser.add_argument("--status", action="store_true", help="Show calibration log status")
    args = parser.parse_args()
    
    if args.log:
        log_picks_from_file(args.log)
    
    elif args.resolve:
        entries = _load_log()
        unresolved = [e for e in entries if not e.get("resolved")]
        print(f"\n  {len(unresolved)} unresolved picks")
        for entry in unresolved[:10]:
            print(f"  {entry['player']} {entry['stat']} {entry['direction']} {entry['line']} "
                  f"(prob: {entry['probability']:.1%})")
            val = input(f"    Actual value (Enter to skip): ").strip()
            if val:
                try:
                    resolve_pick(entry["edge_id"], float(val))
                    print(f"    ✓ Resolved")
                except ValueError:
                    print(f"    ✗ Invalid number")
    
    elif args.report:
        report = run_calibration_report()
        print_calibration_report(report)
    
    elif args.status:
        entries = _load_log()
        resolved = [e for e in entries if e.get("resolved")]
        unresolved = [e for e in entries if not e.get("resolved")]
        print(f"\n  Calibration Log: {CALIBRATION_LOG}")
        print(f"  Total entries: {len(entries)}")
        print(f"  Resolved: {len(resolved)}")
        print(f"  Unresolved: {len(unresolved)}")
        
        # Show date range
        if entries:
            dates = sorted(set(e.get("logged_at", "")[:10] for e in entries if e.get("logged_at")))
            print(f"  Date range: {dates[0]} → {dates[-1]}")
    
    else:
        parser.print_help()
