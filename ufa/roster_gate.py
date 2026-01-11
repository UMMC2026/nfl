from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Tuple, Set, List

from ufa.models.schemas import PropPick


@dataclass(frozen=True)
class RosterInfo:
    active_players: Set[str]
    roster_version: str
    updated_utc: datetime


def _parse_updated_utc(row_val: str) -> datetime:
    try:
        # Accept ISO-8601 with or without timezone
        dt = datetime.fromisoformat(row_val.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def load_active_roster(roster_csv_path: str) -> RosterInfo:
    """
    Load canonical roster CSV and return ACTIVE player set and a checksum-like version string.

    Expected CSV headers:
    player_id,player_name,team,status,game_id,updated_utc
    """
    if not os.path.exists(roster_csv_path):
        raise FileNotFoundError(f"Roster file not found: {roster_csv_path}")

    active: Set[str] = set()
    last_updated: datetime = datetime.fromtimestamp(0, tz=timezone.utc)

    with open(roster_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"player_id", "player_name", "team", "status", "game_id", "updated_utc"}
        missing = required - set([h.strip() for h in reader.fieldnames or []])
        if missing:
            raise ValueError(f"Roster CSV missing headers: {sorted(missing)}")

        for row in reader:
            status = (row.get("status") or "").strip().upper()
            name = (row.get("player_name") or "").strip()
            updated = _parse_updated_utc(row.get("updated_utc") or "")
            if updated > last_updated:
                last_updated = updated
            if status == "ACTIVE" and name:
                active.add(name)

    # Construct roster_version using filename + last_updated
    base = os.path.basename(roster_csv_path)
    ts = last_updated.strftime("%Y-%m-%d_%H-%MUTC")
    roster_version = f"{base.replace('.csv','')}_{ts}"

    return RosterInfo(active_players=active, roster_version=roster_version, updated_utc=last_updated)


def apply_roster_gate(picks: List[PropPick], roster: RosterInfo) -> List[PropPick]:
    """
    Filter picks to ACTIVE players only. Hard gate: non-ACTIVE players are removed.
    """
    return [p for p in picks if p.player in roster.active_players]


def assert_roster_fresh(roster: RosterInfo, max_age_hours: int = 24) -> None:
    """
    Hard fail if roster is older than max_age_hours.
    """
    now = datetime.now(timezone.utc)
    age_hours = (now - roster.updated_utc).total_seconds() / 3600.0
    if age_hours > max_age_hours:
        raise RuntimeError(
            f"Roster stale: last update {age_hours:.1f}h ago (>{max_age_hours}h). Update roster before proceeding."
        )
