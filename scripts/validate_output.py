"""validate_output.py

Validation gate for edges outputs. Exits non-zero on any validation failure.

Usage:
  python scripts/validate_output.py --edges path/to/edges.json [--config path/to/config.yaml] [--allow-time-skip]

The module exposes `validate_edges(edges, config)` for unit tests.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple

DEFAULT_CONFIG = {
    "cooldown_minutes": 30,
    "caps": {
        "core_max": 0.70,
        "alt_max": 0.65,
        "td_max": 0.55
    },
    "primary_tiers": ["SLAM", "STRONG"],
    "tier_map": {
        "SLAM": 0.80,
        "STRONG": 0.65,
        "LEAN": 0.55,
        "AVOID": 0.0
    }
}

REQUIRED_EDGE_KEYS = [
    "edge_id",
    "sport",
    "game_id",
    "entity",
    "market",
    "line",
    "direction",
    "probability",
    "tier",
    "data_sources",
    "injury_verified",
    "correlated"
]


def _implied_tier(prob: float) -> str:
    """Return the implied tier for a probability using conservative boundaries."""
    if prob >= 0.80:
        return "SLAM"
    if prob >= 0.65:
        return "STRONG"
    if prob >= 0.55:
        return "LEAN"
    return "AVOID"


def validate_edges(edges: List[Dict[str, Any]], config: Dict[str, Any] = None, now: datetime = None, allow_time_skip: bool = False) -> Tuple[bool, List[str]]:
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    errors: List[str] = []
    if not edges:
        errors.append("No edges provided")
        return False, errors

    seen_ids = set()
    primary_counts = {}

    for i, e in enumerate(edges):
        # Basic shape check
        missing = [k for k in REQUIRED_EDGE_KEYS if k not in e]
        if missing:
            errors.append(f"Edge {i} ({e.get('edge_id')}) missing keys: {missing}")
            continue

        eid = e["edge_id"]
        if eid in seen_ids:
            errors.append(f"Duplicate edge_id: {eid}")
        seen_ids.add(eid)

        # Data sources
        ds = e.get("data_sources") or []
        if not isinstance(ds, list) or len(ds) < 2:
            errors.append(f"Edge {eid} must have at least 2 data_sources (has: {ds})")

        # Injury
        if not e.get("injury_verified"):
            errors.append(f"Edge {eid} has injury_verified=False")

        # Snap percentage
        if e.get("snap_pct") is None:
            errors.append(f"Edge {eid} missing snap_pct")

        # correlated present
        if not isinstance(e.get("correlated"), bool):
            errors.append(f"Edge {eid} missing or invalid 'correlated' boolean")

        # Probability caps
        prob = float(e["probability"])
        market = str(e["market"]).lower()
        if "td" in market or "touchdown" in market:
            if prob > cfg["caps"]["td_max"] + 1e-9:
                errors.append(f"Edge {eid} ({market}) has probability {prob:.3f} > td_max {cfg['caps']['td_max']}")
        else:
            if prob > cfg["caps"]["core_max"] + 1e-9:
                errors.append(f"Edge {eid} has probability {prob:.3f} > core_max {cfg['caps']['core_max']}")

        # Tier consistency
        implied = _implied_tier(prob)
        if implied != e["tier"] and not (implied == "AVOID" and e["tier"] == "LEAN"):
            errors.append(f"Edge {eid} tier mismatch: implied {implied} vs declared {e['tier']} (prob={prob:.3f})")

        # Primary edge counting
        if e["tier"] in cfg["primary_tiers"]:
            k = (e["game_id"], e["entity"])
            primary_counts[k] = primary_counts.get(k, 0) + 1

        # Game finality / cooldown - optional fields
        status = e.get("game_status")
        end_ts = e.get("game_end_ts")  # ISO format expected if present
        if status and status.upper() != "FINAL":
            errors.append(f"Edge {eid} has non-FINAL game_status: {status}")
        if end_ts and not allow_time_skip:
            try:
                end_dt = datetime.fromisoformat(end_ts)
                now_dt = now or datetime.now(timezone.utc)
                delta = now_dt - end_dt
                if delta < timedelta(minutes=cfg["cooldown_minutes"]):
                    errors.append(f"Edge {eid} game cooldown not met: only {delta} since end (< {cfg['cooldown_minutes']} minutes)")
            except Exception:
                errors.append(f"Edge {eid} has invalid game_end_ts: {end_ts}")

    # Check primary counts
    for (game_id, entity), count in primary_counts.items():
        if count > 1:
            errors.append(f"Multiple primary edges for player {entity} in game {game_id}: {count} found")

    ok = len(errors) == 0
    return ok, errors


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: List[str] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--edges", required=True, help="Path to edges JSON (list)")
    p.add_argument("--config", required=False, help="Optional config JSON with caps/tier mapping")
    p.add_argument("--allow-time-skip", action="store_true", help="Allow skipping cooldown time checks (useful for testing)")
    args = p.parse_args(argv)

    try:
        edges = _load_json(args.edges)
    except Exception as ex:
        print(json.dumps({"STATUS": "ABORTED", "REASON": f"Failed to load edges file: {ex}", "ACTION_REQUIRED": "Provide a valid JSON edges file"}))
        return 2

    cfg = None
    if args.config:
        try:
            cfg = _load_json(args.config)
        except Exception as ex:
            print(json.dumps({"STATUS": "ABORTED", "REASON": f"Failed to load config file: {ex}", "ACTION_REQUIRED": "Fix config JSON or omit --config"}))
            return 2

    ok, errors = validate_edges(edges, cfg, allow_time_skip=args.allow_time_skip)
    if not ok:
        print(json.dumps({"STATUS": "ABORTED", "REASON": errors, "ACTION_REQUIRED": "Fix the above validation failures"}, indent=2))
        return 1

    print(json.dumps({"STATUS": "OK", "MSG": "Validation passed"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
