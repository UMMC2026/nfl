"""interactive_filter_menu.py

Interactive Filter Menu for pick-like rows.

Accepts varied input schemas:
  - Hydrated picks list: list[dict]
  - NFL hydrated matchup blob: { ..., "props": [ ... ] }
  - Risk-first analysis output: { ..., "results": [ ... ] }

Hydration is treated as a *view* — we normalize and enrich in-memory.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    """Return list of dict rows from common project schemas."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]

    if isinstance(payload, dict):
        # Most common keys we emit across scripts
        for key in ("results", "props", "picks", "edges", "signals", "plays"):
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]

    return []


def _direction_norm(direction: Any) -> str:
    d = str(direction or "").strip().lower()
    if d in ("higher", "over", "more", "h", "o"):
        return "over"
    if d in ("lower", "under", "less", "l", "u"):
        return "under"
    return d


def _normal_cdf(x: float) -> float:
    # Standard normal CDF using erf (no scipy dependency)
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _probability_pct(row: Dict[str, Any]) -> float:
    """Best-effort probability in 0..100 (%) for the row's stated direction."""
    # Prefer explicit probability fields if present
    p = row.get("probability")
    if p is None:
        p = row.get("effective_confidence", row.get("model_confidence"))

    if p is not None:
        try:
            p = float(p)
        except Exception:
            p = None

    if p is not None:
        # Normalize 0..1 -> 0..100
        if 0.0 <= p <= 1.0:
            p *= 100.0
        return float(p)

    # Compute from mu/sigma if available (common in NFL hydrated files)
    try:
        mu = float(row.get("mu") or 0.0)
        sigma = float(row.get("sigma") or 0.0)
        line = float(row.get("line") or 0.0)
    except Exception:
        return 0.0

    if sigma <= 0:
        # Degenerate distribution — no variance data, cap at 95% to avoid false 100%
        # This indicates missing/insufficient data; should be flagged as SKIP
        if _direction_norm(row.get("direction")) == "under":
            return 95.0 if mu < line else 5.0  # Cap to avoid false certainty
        return 95.0 if mu > line else 5.0  # Cap to avoid false certainty

    z = (line - mu) / sigma
    p_under = _normal_cdf(z)  # P(X <= line)
    if _direction_norm(row.get("direction")) == "under":
        return 100.0 * p_under
    return 100.0 * (1.0 - p_under)


def _tier_label(row: Dict[str, Any]) -> str:
    return (
        row.get("tier")
        or row.get("confidence_tier")
        or row.get("decision")
        or row.get("status")
        or ""
    )


def _hydrate_view(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a derived row with normalized fields (non-mutating)."""
    out = dict(row)
    out["probability"] = _probability_pct(row)
    out["direction_norm"] = _direction_norm(row.get("direction"))
    if "tier" not in out or not out.get("tier"):
        out["tier"] = _tier_label(row)
    if "player" not in out and out.get("player_name"):
        out["player"] = out.get("player_name")
    return out


if len(sys.argv) < 2:
    print("Usage: python interactive_filter_menu.py <input.json> [output.json]")
    sys.exit(1)

input_path = Path(sys.argv[1])
output_file = sys.argv[2] if len(sys.argv) > 2 else None

if not input_path.exists():
    print(f"❌ Input not found: {input_path}")
    sys.exit(1)

payload = _load_json(input_path)
rows = [_hydrate_view(r) for r in _extract_rows(payload)]

# Interactive prompts
def prompt(msg: str, default: Optional[T] = None, cast: Callable[[str], T] = str) -> T | str:
    val = input(f"{msg} [{default if default is not None else ''}]: ").strip()
    if not val and default is not None:
        return default
    try:
        return cast(val)
    except Exception:
        return val

prob_thresh_raw = prompt("Minimum probability (%)", 0.0, float)
try:
    prob_thresh = float(prob_thresh_raw)  # type: ignore[arg-type]
except Exception:
    prob_thresh = 0.0
direction = prompt("Direction (higher/over/more, lower/under/less, or blank for any)", "", str).lower()
stat = prompt("Stat (e.g., points, rebounds, assists, 3pm, pra, or blank for any)", "", str).lower()
player = prompt("Player name (or blank for any)", "", str).lower()
sort_key = prompt("Sort by (probability/edge/none)", "probability", str).lower()
limit_raw = prompt("Limit results (e.g., 10 for top 10; 0 for all)", 0, int)
try:
    limit = int(limit_raw)  # type: ignore[arg-type]
except Exception:
    limit = 0

# Governance: Exclude SKIP/BLOCKED/REJECTED picks per governance rules
EXCLUDED_TIERS = {"SKIP", "BLOCKED", "REJECTED", "SKIPPED", "NO_PLAY"}

filtered = []
direction_norm = _direction_norm(direction) if direction else ""

for p in rows:
    # Governance gate: Filter out excluded tiers
    tier = str(p.get("tier", "")).upper().strip()
    if tier in EXCLUDED_TIERS:
        continue
    try:
        p_prob = float(p.get("probability", 0) or 0)
    except Exception:
        p_prob = 0.0
    if prob_thresh and p_prob < prob_thresh:
        continue
    if direction_norm and p.get("direction_norm", "") != direction_norm:
        continue
    if stat and p.get("stat", "").lower() != stat:
        continue
    if player and player not in p.get("player", "").lower():
        continue
    filtered.append(p)

if sort_key == "probability":
    filtered.sort(key=lambda r: float(r.get("probability", 0) or 0), reverse=True)
elif sort_key == "edge":
    # Prefer absolute edge magnitude when present.
    filtered.sort(key=lambda r: abs(float(r.get("edge", 0) or 0)), reverse=True)

if limit and limit > 0:
    filtered = filtered[:limit]

print(f"Found {len(filtered)} picks matching your criteria.")

if output_file:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2)
    print(f"Filtered picks saved to {output_file}")
else:
    for i, p in enumerate(filtered, start=1):
        player_name = p.get("player")
        team = p.get("team")
        opp = p.get("opponent")
        stat_name = p.get("stat") or p.get("market")
        line = p.get("line")
        d = str(p.get("direction", "")).upper()
        prob = float(p.get("probability", 0) or 0)
        tier = p.get("tier", "")
        edge = p.get("edge", None)

        matchup = ""
        if team and opp:
            matchup = f" ({team} vs {opp})"
        elif team:
            matchup = f" ({team})"

        edge_str = ""
        try:
            if edge is not None:
                edge_str = f" | Edge={float(edge):.2f}"
        except Exception:
            edge_str = ""

        print(f"{i:>2}. {player_name}{matchup} {stat_name} {line} {d} | Prob={prob:.1f}% | Tier={tier}{edge_str}")
