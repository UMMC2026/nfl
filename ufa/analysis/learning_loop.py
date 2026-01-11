"""Learning Loop for Calibration History

Reads calibration_history.csv and turns failure attribution into suggested
rule changes for governance (e.g., blowout penalties, role-based adjustments).

This module **does not** mutate any existing rows. It only:
  - Reads immutable calibration_history.csv
  - Filters to rows where learning_gate_passed=True
  - Aggregates MISS outcomes by failure_primary_cause and governance context
  - Produces human-readable suggestions for tuning penalties

Intended usage:
  python -m ufa.analysis.learning_loop
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

CALIBRATION_PATH = Path("calibration_history.csv")


@dataclass
class FailureBucket:
    count: int = 0
    avg_suggested_increase: float = 0.0


def _load_rows(path: Path = CALIBRATION_PATH) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Calibration history not found at {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def filter_learning_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Filter to rows eligible for learning.

    Criteria:
      - learning_gate_passed == 'True'
      - outcome in {HIT, MISS}
      - correction_risk != 'True' (exclude high correction risk)
    """
    eligible = []
    for r in rows:
        if r.get("learning_gate_passed", "").lower() != "true":
            continue
        outcome = r.get("outcome", "").upper()
        if outcome not in {"HIT", "MISS"}:
            continue
        if r.get("correction_risk", "").lower() == "true":
            continue
        eligible.append(r)
    return eligible


def summarize_failures(rows: List[Dict[str, str]]) -> Dict[str, FailureBucket]:
    """Summarize MISS outcomes by primary failure cause.

    Uses `suggested_penalty_increase_pct` when available to estimate how much
    additional penalty governance would have needed.
    """
    buckets: Dict[str, FailureBucket] = {}
    totals: Dict[str, float] = defaultdict(float)

    for r in rows:
        outcome = r.get("outcome", "").upper()
        if outcome != "MISS":
            continue
        cause = r.get("failure_primary_cause", "UNKNOWN") or "UNKNOWN"
        buckets.setdefault(cause, FailureBucket())
        buckets[cause].count += 1

        try:
            inc_raw = r.get("suggested_penalty_increase_pct", "")
            if inc_raw not in ("", None):
                inc = float(inc_raw)
                totals[cause] += inc
        except ValueError:
            continue

    for cause, bucket in buckets.items():
        if bucket.count > 0:
            bucket.avg_suggested_increase = totals.get(cause, 0.0) / bucket.count

    return buckets


def propose_blowout_penalty_updates(rows: List[Dict[str, str]]) -> Dict[str, FailureBucket]:
    """Group governance misses by (blowout_risk, player_role) and average suggested increase.

    Focuses on rows where:
      - failure_primary_cause in {MINUTES_CUT, GOVERNANCE_MISS}
      - governance_flag_present == True
      - penalty_was_sufficient == False
    """
    key_buckets: Dict[str, FailureBucket] = {}
    totals: Dict[str, float] = defaultdict(float)

    for r in rows:
        outcome = r.get("outcome", "").upper()
        if outcome != "MISS":
            continue
        cause = (r.get("failure_primary_cause") or "").upper()
        if cause not in {"MINUTES_CUT", "GOVERNANCE_MISS"}:
            continue
        if r.get("governance_flag_present", "").lower() != "true":
            continue
        if r.get("penalty_was_sufficient", "").lower() != "false":
            continue

        key = f"{r.get('blowout_risk','?')}/{r.get('player_role','?')}"
        key_buckets.setdefault(key, FailureBucket())
        key_buckets[key].count += 1

        try:
            inc_raw = r.get("suggested_penalty_increase_pct", "")
            if inc_raw not in ("", None):
                inc = float(inc_raw)
                totals[key] += inc
        except ValueError:
            continue

    for key, bucket in key_buckets.items():
        if bucket.count > 0:
            bucket.avg_suggested_increase = totals.get(key, 0.0) / bucket.count

    return key_buckets


def format_learning_report(
    rows: Optional[List[Dict[str, str]]] = None,
    date_filter: Optional[str] = None,
) -> str:
    """Generate a human-readable learning report from calibration_history.csv.

    Args:
        rows: Optional preloaded rows. If None, loads from CALIBRATION_PATH.
        date_filter: Optional slate_date (YYYY-MM-DD) to restrict analysis.
    """
    if rows is None:
        rows = _load_rows()

    if date_filter:
        rows = [r for r in rows if r.get("slate_date") == date_filter]

    eligible = filter_learning_rows(rows)
    total = len(rows)
    eligible_count = len(eligible)

    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(" CALIBRATION LEARNING LOOP — SUMMARY")
    lines.append("=" * 80)
    lines.append(f" Total rows: {total}")
    lines.append(f" Eligible for learning (gate-passed, no correction risk): {eligible_count}")
    lines.append("")

    # Failure summary
    failures = summarize_failures(eligible)
    if failures:
        lines.append(" MISS BREAKDOWN BY PRIMARY CAUSE:")
        for cause, bucket in sorted(failures.items(), key=lambda x: -x[1].count):
            lines.append(
                f"  - {cause}: {bucket.count} misses, "
                f"avg suggested penalty change: {bucket.avg_suggested_increase:+.3f}"
            )
    else:
        lines.append(" No MISS rows with learning_signal yet.")

    lines.append("")
    # Blowout governance suggestions
    blowout_updates = propose_blowout_penalty_updates(eligible)
    if blowout_updates:
        lines.append(" GOVERNANCE SUGGESTIONS (Blowout Risk x Player Role):")
        for key, bucket in sorted(blowout_updates.items(), key=lambda x: -x[1].count):
            risk, role = key.split("/")
            lines.append(
                f"  - {risk}/{role}: {bucket.count} misses with insufficient penalty; "
                f"avg suggested increase {bucket.avg_suggested_increase:+.3f}"
            )
    else:
        lines.append(" No governance-related misses with suggestions yet.")

    lines.append("")
    lines.append(" NOTE: This module never auto-updates penalties. It only surfaces signals.")
    lines.append("       You update governance_context.py and calibration rules manually.")
    lines.append("=" * 80)
    return "\n".join(lines)


def learning_summary(
    *,
    date_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a structured summary suitable for JSON suggestions.

    Structure:
      {
        "slate_date": date_filter or null,
        "total_rows": int,
        "eligible_rows": int,
        "failures": {cause: {count, avg_suggested_increase}},
        "governance_suggestions": {key: {count, avg_suggested_increase}},
      }
    """

    rows = _load_rows()
    if date_filter:
        rows = [r for r in rows if r.get("slate_date") == date_filter]

    eligible = filter_learning_rows(rows)
    failures = summarize_failures(eligible)
    blowout_updates = propose_blowout_penalty_updates(eligible)

    failures_json: Dict[str, Any] = {}
    for cause, bucket in failures.items():
        failures_json[cause] = {
            "count": bucket.count,
            "avg_suggested_increase": bucket.avg_suggested_increase,
        }

    gov_json: Dict[str, Any] = {}
    for key, bucket in blowout_updates.items():
        gov_json[key] = {
            "count": bucket.count,
            "avg_suggested_increase": bucket.avg_suggested_increase,
        }

    return {
        "slate_date": date_filter,
        "total_rows": len(rows),
        "eligible_rows": len(eligible),
        "failures": failures_json,
        "governance_suggestions": gov_json,
    }


if __name__ == "__main__":
    report = format_learning_report()
    print(report)
