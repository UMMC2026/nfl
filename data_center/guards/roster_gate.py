import hashlib
import csv
from datetime import datetime, timedelta, timezone
from typing import List, Union, Dict, Any

REQUIRED_COLUMNS = {
    "player_name",
    "team",
    "status",
    "game_id",
    "updated_utc",
}

VALID_ACTIVE_STATUS = {"ACTIVE"}
DOWNGRADE_STATUS = {"QUESTIONABLE", "DOUBTFUL"}

MAX_ROSTER_AGE_MINUTES = 60


class RosterGateError(Exception):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def roster_checksum(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _parse_ts(ts_str: str) -> datetime:
    s = ts_str.strip()
    # Support ISO with 'Z'
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # Fallback: try naive parse and set UTC
        dt = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def roster_version(roster_rows: List[Dict[str, Any]], path: str) -> str:
    """Return a human-friendly roster version string derived from file path and latest timestamp.

    Attempts to infer the league from the roster file name (e.g., contains 'NBA', 'NFL', 'CFB').
    Falls back to 'ROSTER' if no known league token is found.
    """
    latest = max((_parse_ts(row["updated_utc"]) for row in roster_rows), default=_now_utc())
    fname = str(path).upper()
    if "NBA" in fname:
        prefix = "NBA"
    elif "NFL" in fname:
        prefix = "NFL"
    elif "CFB" in fname or "NCAA" in fname:
        prefix = "CFB"
    else:
        prefix = "ROSTER"
    return f"{prefix}_active_{latest.strftime('%Y-%m-%dT%H:%MZ')}"


def load_roster(roster_path: str) -> List[Dict[str, Any]]:
    """Load roster CSV into a list of dict rows, avoiding heavy pandas import.

    Validates required columns and freshness based on max(updated_utc).
    """
    try:
        with open(roster_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [dict(r) for r in reader]
    except FileNotFoundError:
        raise RosterGateError(f"Roster file not found: {roster_path}")

    if not rows:
        raise RosterGateError("Roster file is empty")

    cols = set(rows[0].keys())
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise RosterGateError(f"Roster missing columns: {missing}")

    latest = max((_parse_ts(r["updated_utc"]) for r in rows))
    if latest < (_now_utc() - timedelta(minutes=MAX_ROSTER_AGE_MINUTES)):
        raise RosterGateError("Roster is stale (older than 60 minutes)")

    return rows


def apply_roster_gate(picks: List[Union[dict, object]], roster_rows: List[Dict[str, Any]]) -> List[Union[dict, object]]:
    """Filter picks to ACTIVE players only. Supports dict or objects with .player."""
    active_players = {str(r["player_name"]) for r in roster_rows if str(r.get("status", "")).upper() == "ACTIVE"}

    def _name(p):
        return p.get("player") if isinstance(p, dict) else getattr(p, "player")

    gated = [p for p in picks if _name(p) in active_players]
    if not gated:
        raise RosterGateError("All picks removed by roster gate")
    return gated


def apply_status_downgrade(ranked: List[dict], roster_rows: List[Dict[str, Any]], penalties: dict | None = None) -> List[dict]:
    """Apply status-weighted downgrade to already-ranked dicts containing p_hit."""
    if penalties is None:
        penalties = {"QUESTIONABLE": 0.08, "DOUBTFUL": 0.15}

    status_map = {str(r["player_name"]): str(r["status"]) for r in roster_rows}

    for r in ranked:
        status = status_map.get(r["player"])  # None if not present
        if status in penalties:
            r["p_hit"] = max(0.0, float(r["p_hit"]) - float(penalties[status]))
            flags = r.get("flags", [])
            flags.append("ROSTER_DOWNGRADE")
            r["flags"] = flags
    return ranked

def get_player_status(roster_rows: List[Dict[str, Any]], player_name: str) -> Union[str, None]:
    """Return status string for player or None if not present."""
    for r in roster_rows:
        if str(r.get("player_name", "")) == player_name:
            return str(r.get("status"))
    return None
