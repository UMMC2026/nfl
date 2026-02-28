"""filter_over_picks.py

Filter picks to show only those with probability favoring OVER the line.

This accepts either:
  1) A hydrated picks list (list[dict])
  2) A Risk-First analysis JSON (dict with a top-level "results": [...])

Usage:
  python filter_over_picks.py <input.json> [output.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    """Return a list of pick/edge-like dict rows from varied input schemas."""

    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]

    if isinstance(payload, dict):
        # Risk-first canonical: {"results": [...]}
        if isinstance(payload.get("results"), list):
            return [r for r in payload["results"] if isinstance(r, dict)]

        # Common alternates across scripts
        for key in ("edges", "signals", "picks", "plays", "props"):
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]

    return []


def _probability_pct(row: Dict[str, Any]) -> float:
    """Best-effort probability in 0..100 (%)."""
    p = row.get("probability")
    if p is None:
        # Risk-first fields
        p = row.get("effective_confidence", row.get("model_confidence", 0))

    try:
        p = float(p)
    except Exception:
        return 0.0

    # Normalize 0..1 -> 0..100
    if 0.0 <= p <= 1.0:
        p *= 100.0
    return p


def _direction_norm(row: Dict[str, Any]) -> str:
    d = str(row.get("direction", "")).strip().lower()
    # Normalize some variants
    if d in ("higher", "over", "more"):
        return "over"
    if d in ("lower", "under", "less"):
        return "under"
    return d


def _tier_label(row: Dict[str, Any]) -> str:
    # Prefer explicit tier-like fields, then fall back to risk-first decision/status.
    return (
        row.get("tier")
        or row.get("confidence_tier")
        or row.get("decision")
        or row.get("status")
        or ""
    )


def _as_display_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a lightweight derived view without mutating the source row."""
    out = dict(row)
    out["probability"] = _probability_pct(row)
    if "tier" not in out or not out.get("tier"):
        out["tier"] = _tier_label(row)
    # Standardize some key aliases used by various scripts
    if "player" not in out and row.get("player_name"):
        out["player"] = row.get("player_name")
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python filter_over_picks.py <input.json> [output.json]")
        return 1

    input_path = Path(sys.argv[1])
    output_path: Optional[Path] = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not input_path.exists():
        print(f"❌ Input not found: {input_path}")
        return 1

    payload = _load_json(input_path)
    rows = [_as_display_row(r) for r in _extract_rows(payload)]

    # Filter for OVER direction and probability > 75%
    filtered = [
        r
        for r in rows
        if _direction_norm(r) == "over" and _probability_pct(r) > 75
    ]

    print(f"Found {len(filtered)} picks with true math edge (OVER > 75% probability).")

    if output_path:
        output_path.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
        print(f"Filtered picks saved to {output_path}")
    else:
        for r in filtered:
            player = r.get("player")
            stat = r.get("stat") or r.get("market")
            line = r.get("line")
            prob = r.get("probability")
            tier = r.get("tier")
            print(f"{player} {stat} {line} OVER | Prob={prob:.1f}% | Tier={tier}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
