"""CLI wrapper for running sport-specific councils + SOP on edge files.

Example:

  python -m oracle.council_cli \
      --sport nba \
      --input-json outputs/NBA_EDGES.json \
      --output-json outputs/NBA_COUNCIL_DECISIONS.json
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from .councils import NBACouncil, NFLCouncil, SoccerCouncil
from .sop_enforcer import AgentPick


def _load_edges(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("edges", "signals", "picks", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
    raise ValueError(f"Unrecognized edges JSON structure in {path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run sport-specific council on edges JSON")
    p.add_argument("--sport", required=True, choices=["nba", "nfl", "soccer"], help="Sport")
    p.add_argument("--input-json", required=True, help="Input edges JSON file")
    p.add_argument("--output-json", required=True, help="Output JSON with council decisions")
    return p


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    sport = args.sport.lower()
    if sport == "nba":
        council = NBACouncil()
    elif sport == "nfl":
        council = NFLCouncil()
    else:
        council = SoccerCouncil()

    edges = _load_edges(Path(args.input_json))

    # Group edges by (entity, market, line, direction)
    groups: Dict[tuple, List[AgentPick]] = {}
    for e in edges:
        key = (
            e.get("entity") or e.get("player"),
            e.get("market") or e.get("stat"),
            e.get("line"),
            e.get("direction", "Higher"),
        )
        prob = e.get("probability", 50.0)
        if prob > 1.0:
            prob = prob / 100.0
        src = e.get("source", "oracle")
        ap = AgentPick(
            sport=sport,
            entity=str(key[0]),
            market=str(key[1]),
            line=float(key[2] or 0.0),
            direction=str(key[3]),
            probability=float(prob),
            edge=float(e.get("edge")) if e.get("edge") is not None else None,
            tier=str(e.get("tier")) if e.get("tier") is not None else None,
            source=src,
            metadata={"raw": e},
        )
        groups.setdefault(key, []).append(ap)

    decisions: List[Dict[str, Any]] = []
    for key, picks in groups.items():
        decision = council.aggregate(picks)
        decisions.append(decision)

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)

    print(f"[OK] Wrote {len(decisions)} council decisions to {out_path}")


if __name__ == "__main__":
    main()
