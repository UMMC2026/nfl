"""
Combined Slate + Roster Validator — Pipeline Entry Point

This is the SINGLE GATE that all views, Telegram, reports must pass through.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from engine.slate_gate import enforce_today_slate
from engine.roster_gate import bind_player_team, load_roster_map


VALIDATED_OUTPUT = Path("outputs/validated_primary_edges.json")


def validate_and_render(
    picks: List[Dict[str, Any]],
    roster_map: Dict[str, str],
    today_teams: set,
    output_path: Optional[Path] = None,
    min_match_rate: float = 0.95
) -> List[Dict[str, Any]]:
    """
    Full validation pipeline: roster binding → slate enforcement → output.

    Args:
        picks: Raw picks from JSON or user input
        roster_map: Player → team authoritative mapping
        today_teams: Set of teams playing today
        output_path: Where to write validated picks (default: VALIDATED_OUTPUT)
        min_match_rate: Minimum % of picks matching today's teams

    Returns:
        Validated picks list

    Raises:
        RuntimeError: If any gate fails (fail closed)
    """
    if output_path is None:
        output_path = VALIDATED_OUTPUT

    # Step 1: Override teams with roster truth
    picks = bind_player_team(picks, roster_map, override=True)

    # Step 2: Enforce slate (all picks must be in today's teams)
    picks = enforce_today_slate(picks, today_teams, min_match_rate)

    # Step 3: Write validated output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "validated_count": len(picks),
                "picks": picks
            },
            f,
            indent=2
        )

    print(f"✅ Validated {len(picks)} picks → {output_path}")
    return picks


def load_validated_picks(output_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Load the ONLY SOURCE OF TRUTH for all downstream views.

    Args:
        output_path: Path to validated output (default: VALIDATED_OUTPUT)

    Returns:
        List of validated picks (or empty list if file missing)
    """
    if output_path is None:
        output_path = VALIDATED_OUTPUT

    if not output_path.exists():
        raise RuntimeError(
            f"Validated picks not found: {output_path}\n"
            f"Run validate_and_render() first."
        )

    with open(output_path, "r") as f:
        data = json.load(f)
    return data.get("picks", [])
