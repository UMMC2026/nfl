#!/usr/bin/env python3
"""Sync legacy calibration_history.csv into cache/pick_history.db.

Why:
- The web dashboard and Phase 5 analytics use SQLite (pick_history.db).
- Much of the repo still appends to calibration_history.csv.

This script performs a safe, idempotent sync:
- Inserts picks (upsert via PickHistoryDB unique index)
- If actual/outcome is present, resolves the pick

Usage:
    .venv\\Scripts\\python.exe scripts/sync_legacy_calibration_csv_to_db.py
    .venv\\Scripts\\python.exe scripts/sync_legacy_calibration_csv_to_db.py --dry-run

Notes:
- Outcome mapping supports: WIN/WON/HIT and LOSS/LOST/MISS and PUSH.
- Probability values in the CSV are often percentages (e.g. 62.5). We normalize to 0-1.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pick_history_db import PickHistoryDB


LEGACY_CSV = Path("calibration_history.csv")
AUDIT_DIR = Path("outputs") / "audit"


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _norm_prob(p: Any) -> Optional[float]:
    f = _to_float(p)
    if f is None:
        return None
    # Heuristic: values > 1 are percentage points
    if f > 1.0:
        f = f / 100.0
    # Clamp to [0,1]
    if f < 0.0:
        f = 0.0
    if f > 1.0:
        f = 1.0
    return f


def _norm_direction(d: str) -> str:
    s = (d or "").strip().lower()
    if s in {"higher", "over", "more", "+"}:
        return "higher"
    if s in {"lower", "under", "less", "-"}:
        return "lower"
    return s or "higher"


def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    # expected YYYY-MM-DD
    try:
        parts = s.split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None
    return None


def _outcome_to_hit(outcome: str) -> Optional[bool]:
    s = (outcome or "").strip().upper()
    if s in {"WIN", "WON", "HIT"}:
        return True
    if s in {"LOSS", "LOST", "MISS"}:
        return False
    # Push/void intentionally unresolved for calibration
    if s in {"PUSH", "VOID", "TIE"}:
        return None
    return None


@dataclass
class SyncStats:
    total_rows: int = 0
    inserted: int = 0
    resolved: int = 0
    updated_existing: int = 0
    skipped_invalid: int = 0
    skipped_unresolved: int = 0


def sync(*, dry_run: bool = False) -> Tuple[SyncStats, Path | None]:
    stats = SyncStats()

    if not LEGACY_CSV.exists():
        raise FileNotFoundError(f"Legacy file not found: {LEGACY_CSV}")

    db = PickHistoryDB()

    with LEGACY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for r in rows:
        stats.total_rows += 1

        player = (r.get("player") or "").strip()
        stat = (r.get("stat") or "").strip()
        line = _to_float(r.get("line"))
        direction = _norm_direction(r.get("direction") or "")

        slate_date = _parse_date(r.get("game_date") or "")
        if slate_date is None:
            # Many legacy rows are blank; treat as unknown date -> skip
            stats.skipped_invalid += 1
            continue

        if not player or not stat or line is None:
            stats.skipped_invalid += 1
            continue

        confidence = _norm_prob(r.get("probability"))
        tier = (r.get("tier") or "").strip() or None
        sport = (r.get("league") or r.get("sport") or "NBA").strip().upper()

        pick: Dict[str, Any] = {
            "sport": sport,
            "player": player,
            "team": (r.get("team") or "").strip() or None,
            "opponent": (r.get("opponent") or "").strip() or None,
            "stat": stat,
            "line": line,
            "direction": direction,
            "confidence": confidence,
            "tier": tier,
            "metadata": {
                "source": (r.get("source") or "legacy_csv").strip() or "legacy_csv",
                "pick_id": (r.get("pick_id") or "").strip() or None,
            },
        }

        if dry_run:
            # Cannot know insert vs duplicate without hitting DB; count as would-insert
            stats.inserted += 1
        else:
            before_id = db.log_pick(pick, slate_date=slate_date, slate_name="legacy_csv")
            if before_id is not None:
                stats.inserted += 1

        actual_value = _to_float(r.get("actual_value"))
        outcome = (r.get("outcome") or "").strip()
        hit = _outcome_to_hit(outcome)

        if actual_value is None and hit is None:
            stats.skipped_unresolved += 1
            continue

        if dry_run:
            stats.resolved += 1
            continue

        # Resolve using actual_value when available; otherwise derive from outcome+line.
        # If actual_value is missing but outcome exists, set synthetic actual_value = line +/- eps.
        if actual_value is None and hit is not None:
            actual_value = (line + 0.01) if (hit and direction == "higher") else (line - 0.01)
            if direction == "lower":
                actual_value = (line - 0.01) if hit else (line + 0.01)

        if actual_value is None:
            continue

        # PickHistoryDB resolves by id; we don't have id reliably here.
        # Use resolve_by_player to match (date, player, stat). This may hit multiple rows.
        resolved_flags = db.resolve_by_player(player, stat, actual_value, slate_date)
        if resolved_flags:
            stats.resolved += sum(1 for x in resolved_flags if x is not None)

    # Write audit
    audit_path: Path | None = None
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        now_utc = datetime.now(timezone.utc)
        audit_path = AUDIT_DIR / f"sync_legacy_calibration_{now_utc.strftime('%Y%m%d_%H%M%S')}.json"
        audit = {
            "timestamp_utc": now_utc.isoformat(),
            "dry_run": dry_run,
            "legacy_csv": str(LEGACY_CSV),
            "db_path": str(Path("cache/pick_history.db")),
            "stats": stats.__dict__,
        }
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    except OSError as e:
        # Never fail the sync due to audit I/O. This can happen in constrained
        # environments (e.g., no free disk space).
        print(f"⚠️  Could not write audit file to {AUDIT_DIR}: {e}")
        audit_path = None

    return stats, audit_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    args = ap.parse_args()

    stats, audit_path = sync(dry_run=args.dry_run)
    print("\nLEGACY CALIBRATION CSV → SQLITE SYNC")
    print("-" * 55)
    print(f"Rows scanned: {stats.total_rows}")
    print(f"Inserted/upserted: {stats.inserted}")
    print(f"Resolved (attempted): {stats.resolved}")
    print(f"Skipped invalid: {stats.skipped_invalid}")
    print(f"Skipped unresolved: {stats.skipped_unresolved}")
    if audit_path:
        print(f"Audit: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
