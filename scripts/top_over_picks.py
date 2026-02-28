"""scripts/top_over_picks.py

Utility: print the top N "Higher" (over) candidates at/above a probability threshold.

This is a read-only helper: it does NOT generate probabilities.
It simply filters an existing *_RISK_FIRST_*.json analysis artifact.

Examples:
  - Latest file auto-detected:
      python scripts/top_over_picks.py

  - Specific file:
      python scripts/top_over_picks.py --file outputs/NBATUESDAYPTS_RISK_FIRST_20260127_FROM_UD.json

Notes:
  - Uses effective_confidence when present (percent scale).
  - Filters to decision in {PLAY, LEAN} by default.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_GLOBS: Tuple[str, ...] = (
    "outputs/*_RISK_FIRST_*.json",
    "sports/*/outputs/*_RISK_FIRST_*.json",
    "soccer/outputs/*_RISK_FIRST_*.json",
    "tennis/outputs/*_RISK_FIRST_*.json",
)


@dataclass(frozen=True)
class PickRow:
    player: str
    team: str
    opponent: str
    stat: str
    line: float
    direction: str
    decision: str
    prob_pct: float
    edge: float
    source_file: str


def _to_prob_pct(value: Any) -> Optional[float]:
    """Normalize probability/confidence fields to a 0..100 percentage."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None

    # Heuristic: <=1 means fraction; otherwise percent.
    if v <= 1.0:
        return v * 100.0
    return v


def _extract_prob_pct(r: Dict[str, Any]) -> Optional[float]:
    # Prefer governed confidence.
    for k in (
        "effective_confidence",  # typically 0..100
        "probability",  # sometimes 0..1
        "status_confidence",
        "model_confidence",
    ):
        p = _to_prob_pct(r.get(k))
        if p is not None:
            return p
    return None


def _iter_results(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    results = payload.get("results")
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict):
                yield r


def _find_latest_results_file() -> Optional[Path]:
    candidates: List[Path] = []
    for pattern in DEFAULT_GLOBS:
        candidates.extend(Path(".").glob(pattern))

    # Filter out empty / directories
    candidates = [p for p in candidates if p.is_file()]

    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_rows(
    results_path: Path,
    min_prob_pct: float,
    top_n: int,
    direction: str,
    decisions: Tuple[str, ...],
) -> List[PickRow]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))

    rows: List[PickRow] = []
    for r in _iter_results(payload):
        if direction and str(r.get("direction", "")).lower() != direction.lower():
            continue

        decision = str(r.get("decision", r.get("status", ""))).upper().strip()
        if decisions and decision not in decisions:
            continue

        prob_pct = _extract_prob_pct(r)
        if prob_pct is None:
            continue

        if prob_pct < min_prob_pct:
            continue

        rows.append(
            PickRow(
                player=str(r.get("player", "")),
                team=str(r.get("team", "")),
                opponent=str(r.get("opponent", "")),
                stat=str(r.get("stat", "")),
                line=float(r.get("line", 0.0) or 0.0),
                direction=str(r.get("direction", "")),
                decision=decision,
                prob_pct=float(prob_pct),
                edge=float(r.get("edge", 0.0) or 0.0),
                source_file=results_path.name,
            )
        )

    # Sort: highest probability first; tie-breaker by absolute edge.
    rows.sort(key=lambda x: (-x.prob_pct, -abs(x.edge)))
    return rows[:top_n]


def _format_row(i: int, r: PickRow) -> str:
    return (
        f"{i:>2}. {r.prob_pct:>5.1f}%  {r.player}  {r.team} vs {r.opponent}  "
        f"{r.stat} {r.direction} {r.line}  ({r.decision})"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Print top N 'Higher' picks at/above a probability threshold")
    ap.add_argument("--file", type=str, default=None, help="Path to a *_RISK_FIRST_*.json file")
    ap.add_argument("--min", dest="min_prob", type=float, default=0.68, help="Min probability (0..1) or percent (0..100)")
    ap.add_argument("--top", dest="top_n", type=int, default=10, help="How many to print")
    ap.add_argument("--direction", type=str, default="higher", help="Direction filter (default: higher)")
    ap.add_argument(
        "--include",
        type=str,
        default="PLAY,LEAN",
        help="Comma-separated decisions to include (default: PLAY,LEAN). Use 'ALL' to include everything.",
    )

    args = ap.parse_args()

    # Normalize min probability
    min_prob_pct = args.min_prob * 100.0 if args.min_prob <= 1.0 else args.min_prob

    # Pick file
    results_path = Path(args.file) if args.file else _find_latest_results_file()
    if results_path is None or not results_path.exists():
        print("No *_RISK_FIRST_*.json results found. Run a pipeline first (Generate/Score Edges), then re-run this helper.")
        return 2

    include_raw = (args.include or "").strip()
    decisions: Tuple[str, ...]
    if include_raw.upper() == "ALL":
        decisions = tuple()  # no filter
    else:
        decisions = tuple(d.strip().upper() for d in include_raw.split(",") if d.strip())

    rows = load_rows(
        results_path=results_path,
        min_prob_pct=min_prob_pct,
        top_n=max(1, int(args.top_n)),
        direction=args.direction,
        decisions=decisions,
    )

    print(f"Source: {results_path}")
    print(f"Filter: direction={args.direction}, decisions={decisions or 'ALL'}, min_prob={min_prob_pct:.1f}%")

    if not rows:
        print("No rows met the threshold. This can happen when gates/caps downgrade confidence or when the slate has no PLAY/LEAN picks.")
        return 0

    print("\nTop candidates:")
    for i, r in enumerate(rows, start=1):
        print(_format_row(i, r))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
