r"""ingestion/ingest_daily_props.py

Daily Prop Results Ingestion
===========================

Purpose
-------
Normalize daily prop outcomes (WIN/LOSS/PENDING) into:
  - row-level CSV for quant pipelines
  - JSON summary for dashboards/audit
  - immutable timestamped artifacts

This script is intentionally conservative:
  - It will NOT modify calibration_history.csv unless you explicitly opt-in
    *and* you provide enough identifiers (player+stat+line+direction).

Inputs
------
Option A (recommended): JSON list of dicts
  [{"sport":"NBA","player":"...","stat":"points","line":25.5,
    "direction":"higher","result":"WIN"}, ...]

Option B: Plain text tally (paste output) — parses bullets like:
  • Player Name — WIN

Outputs
-------
Written to ingestion/output/ as timestamped files + *_latest.* convenience copies.

Run
---
  .venv\Scripts\python.exe ingestion/ingest_daily_props.py --json ingestion/output/daily_props_raw.json
  .venv\Scripts\python.exe ingestion/ingest_daily_props.py --text ingestion/output/daily_props_tally.txt

"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_RESULTS = {"WIN", "LOSS", "PENDING", "PUSH", "VOID", "CANCELLED", "UNKNOWN"}


@dataclass(frozen=True)
class RawResult:
    sport: str
    player: str
    result: str
    stat: Optional[str] = None
    line: Optional[float] = None
    direction: Optional[str] = None  # higher/lower/over/under
    ticket: Optional[str] = None
    notes: Optional[str] = None


def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iso_date(d: Optional[str]) -> str:
    if d:
        return d
    return date.today().isoformat()


def _normalize_direction(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    v = str(d).strip().lower()
    if v in {"more", "over", "higher", "hi", "h"}:
        return "higher"
    if v in {"less", "under", "lower", "lo", "l"}:
        return "lower"
    return v


def _normalize_sport(s: Optional[str]) -> str:
    if not s:
        return "UNKNOWN"
    v = str(s).strip().upper()
    aliases = {
        "NCAAB": "CBB",
        "COLLEGE": "CBB",
        "HOCKEY": "NHL",
        "FUTBOL": "SOCCER",
        "PGA": "GOLF",
    }
    return aliases.get(v, v)


def _normalize_result(r: str) -> str:
    v = str(r).strip().upper()
    # common variants
    if v in {"W", "HIT", "WINNER"}:
        v = "WIN"
    if v in {"L", "MISS", "LOSER"}:
        v = "LOSS"
    if v in {"TBD", "UNCONFIRMED"}:
        v = "PENDING"
    if v not in ALLOWED_RESULTS:
        return "UNKNOWN"
    return v


def load_raw_results_from_json(path: Path) -> List[RawResult]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON input must be a list of objects")

    out: List[RawResult] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise ValueError(f"Row {i} is not an object")

        sport = _normalize_sport(row.get("sport"))
        player = str(row.get("player") or row.get("entity") or "").strip()
        if not player:
            raise ValueError(f"Row {i} missing player")

        result = _normalize_result(row.get("result", "UNKNOWN"))
        stat = row.get("stat") or row.get("market")

        line = row.get("line")
        line_f: Optional[float] = None
        if line is not None and line != "":
            try:
                line_f = float(line)
            except Exception:
                line_f = None

        direction = _normalize_direction(row.get("direction") or row.get("pick"))

        out.append(
            RawResult(
                sport=sport,
                player=player,
                result=result,
                stat=str(stat).strip() if stat not in (None, "") else None,
                line=line_f,
                direction=direction,
                ticket=row.get("ticket") or row.get("group"),
                notes=row.get("notes"),
            )
        )

    return out


_BULLET_RE = re.compile(r"^\s*[•\-*]\s*(?P<player>.+?)\s*[—\-:]\s*(?P<result>WIN|LOSS|PENDING|HIT|MISS|W|L|TBD|UNCONFIRMED)\s*$", re.IGNORECASE)


def load_raw_results_from_text(path: Path) -> List[RawResult]:
    """Parse a human tally.

    This is best-effort:
      - Uses last seen section header as `ticket`
      - Attempts to infer sport from section header keywords
    """

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    current_section: Optional[str] = None
    current_sport: str = "UNKNOWN"
    out: List[RawResult] = []

    def infer_sport_from_section(section: str) -> str:
        s = section.upper()
        if "NBA" in s:
            return "NBA"
        if "NHL" in s or "HOCKEY" in s:
            return "NHL"
        if "NFL" in s:
            return "NFL"
        if "CBB" in s or "NCAAB" in s:
            return "CBB"
        if "TENNIS" in s:
            return "TENNIS"
        if "SOCCER" in s:
            return "SOCCER"
        if "GOLF" in s or "PGA" in s:
            return "GOLF"
        if "MIX" in s:
            return "MIX"
        return "UNKNOWN"

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        m = _BULLET_RE.match(raw)
        if m:
            player = m.group("player").strip()
            result = _normalize_result(m.group("result"))
            out.append(
                RawResult(
                    sport=current_sport,
                    player=player,
                    result=result,
                    ticket=current_section,
                )
            )
            continue

        # treat non-bullet lines as section headers if they look like headings
        if len(line) <= 64 and not line.startswith("#") and not line.startswith("*"):
            # Examples: "NBA Props", "Golf Props", "Tennis / Golf Mix Ticket"
            if any(k in line.upper() for k in ["NBA", "NFL", "NHL", "CBB", "TENNIS", "GOLF", "SOCCER", "TICKET", "PROPS"]):
                current_section = line
                current_sport = infer_sport_from_section(line)

    return out


def summarize(rows: List[RawResult], run_date: str) -> Dict[str, Any]:
    counts = {k: 0 for k in sorted(ALLOWED_RESULTS)}
    by_sport: Dict[str, Dict[str, int]] = {}

    for r in rows:
        counts[r.result] = counts.get(r.result, 0) + 1
        s = r.sport
        if s not in by_sport:
            by_sport[s] = {}
        by_sport[s][r.result] = by_sport[s].get(r.result, 0) + 1

    confirmed = counts.get("WIN", 0) + counts.get("LOSS", 0)
    win_rate = (counts.get("WIN", 0) / confirmed) if confirmed else 0.0

    return {
        "date": run_date,
        "total": len(rows),
        "wins": counts.get("WIN", 0),
        "losses": counts.get("LOSS", 0),
        "pending": counts.get("PENDING", 0),
        "confirmed": confirmed,
        "win_rate_confirmed": round(win_rate, 4),
        "by_sport": by_sport,
        "counts": counts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_outputs(rows: List[RawResult], summary: Dict[str, Any], run_date: str, tag: str) -> Tuple[Path, Path, Path]:
    ts = _now_ts()

    raw_path = OUTPUT_DIR / f"daily_props_raw_{tag}_{ts}.json"
    norm_csv = OUTPUT_DIR / f"daily_props_normalized_{tag}_{ts}.csv"
    summary_path = OUTPUT_DIR / f"daily_props_summary_{tag}_{ts}.json"

    raw_path.write_text(json.dumps([asdict(r) for r in rows], indent=2), encoding="utf-8")

    # CSV normalization
    csv_rows: List[Dict[str, Any]] = []
    for r in rows:
        csv_rows.append(
            {
                "date": run_date,
                "sport": r.sport,
                "ticket": r.ticket or "",
                "player": r.player,
                "stat": r.stat or "",
                "line": "" if r.line is None else r.line,
                "direction": r.direction or "",
                "result": r.result,
                "is_win": 1 if r.result == "WIN" else 0,
                "is_loss": 1 if r.result == "LOSS" else 0,
                "is_pending": 1 if r.result == "PENDING" else 0,
                "notes": r.notes or "",
            }
        )

    if csv_rows:
        with open(norm_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Latest pointers (convenience, overwrite allowed)
    (OUTPUT_DIR / "daily_props_raw_latest.json").write_text(raw_path.read_text(encoding="utf-8"), encoding="utf-8")
    (OUTPUT_DIR / "daily_props_normalized_latest.csv").write_text(norm_csv.read_text(encoding="utf-8"), encoding="utf-8")
    (OUTPUT_DIR / "daily_props_summary_latest.json").write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")

    return raw_path, norm_csv, summary_path


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Ingest daily prop results and produce normalized outputs")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--json", dest="json_path", help="Path to raw results JSON list")
    src.add_argument("--text", dest="text_path", help="Path to raw text tally")
    p.add_argument("--date", dest="run_date", help="Override run date YYYY-MM-DD (default: today)")
    p.add_argument("--tag", default="daily", help="Tag to include in output filenames (default: daily)")

    args = p.parse_args(argv)

    run_date = _iso_date(args.run_date)

    if args.json_path:
        rows = load_raw_results_from_json(Path(args.json_path))
    else:
        rows = load_raw_results_from_text(Path(args.text_path))

    summary = summarize(rows, run_date)

    raw_path, csv_path, summary_path = write_outputs(rows, summary, run_date, args.tag)

    print("✅ Daily prop ingestion complete")
    print(f"  Raw:     {raw_path}")
    print(f"  CSV:     {csv_path}")
    print(f"  Summary: {summary_path}")
    print(f"  Confirmed win rate: {summary['win_rate_confirmed']:.1%} ({summary['wins']}W / {summary['losses']}L)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
