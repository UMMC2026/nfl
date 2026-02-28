"""scripts/classify_active_nba_players.py

Goal:
- Prevent "BLOCKED: Player '<name>' not classified" by ensuring every active NBA
  player has a role classification in `role_mapping.json`.

How it works:
- Loads:
    - nba_active_players.json (authoritative list of active player names)
    - role_mapping.json (risk_gates role mapping used by the NBA risk-first engine)
    - nba_role_mapping.json (optional: has player -> {team, position} for many players)
- For any active player missing from role_mapping.json, assigns a conservative role
  derived from position when available:
    - C  -> BIG
    - PF -> ATHLETIC_WING
    - SF -> ATHLETIC_WING
    - SG -> SECONDARY_GUARD
    - PG -> SECONDARY_GUARD
  If no position is known, defaults to ROLE_PLAYER.

Outputs:
- Writes an audit JSON into outputs/: outputs/role_mapping_audit_<YYYYMMDD>.json
- Optionally updates role_mapping.json (default: yes) and writes a backup copy.

This script is intentionally conservative:
- It avoids incorrectly tagging unknown players as STAR_GUARD.
- It prefers "safe" roles that don't auto-trigger star-guard traps.

Run:
  .venv\\Scripts\\python.exe scripts\\classify_active_nba_players.py

"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PLAYERS_PATH = ROOT / "nba_active_players.json"
ROLE_MAPPING_PATH = ROOT / "role_mapping.json"
NBA_ROLE_MAPPING_PATH = ROOT / "nba_role_mapping.json"
OUTPUTS_DIR = ROOT / "outputs"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _role_from_position(pos: Optional[str]) -> str:
    """Map nba_role_mapping positional labels to risk_gates roles."""
    p = (pos or "").strip().upper()
    if p == "C":
        return "BIG"
    if p in {"PF", "SF"}:
        return "ATHLETIC_WING"
    if p in {"PG", "SG"}:
        return "SECONDARY_GUARD"
    return "ROLE_PLAYER"


@dataclass
class AddRecord:
    player: str
    assigned_role: str
    source: str
    position: str = ""
    team: str = ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Do not modify role_mapping.json")
    ap.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Write a backup of role_mapping.json before editing (default: on)",
    )
    args = ap.parse_args()

    if not ACTIVE_PLAYERS_PATH.exists():
        raise FileNotFoundError(f"Missing {ACTIVE_PLAYERS_PATH}")
    if not ROLE_MAPPING_PATH.exists():
        raise FileNotFoundError(f"Missing {ROLE_MAPPING_PATH}")

    active_players = _load_json(ACTIVE_PLAYERS_PATH)
    role_cfg = _load_json(ROLE_MAPPING_PATH)

    if not isinstance(active_players, list):
        raise ValueError("nba_active_players.json must be a JSON array")
    if "player_classifications" not in role_cfg or not isinstance(role_cfg["player_classifications"], dict):
        raise ValueError("role_mapping.json missing player_classifications dict")

    existing: dict = role_cfg["player_classifications"]

    nba_role_map: dict[str, dict] = {}
    if NBA_ROLE_MAPPING_PATH.exists():
        try:
            nba_rm = _load_json(NBA_ROLE_MAPPING_PATH)
            pc = nba_rm.get("player_classifications") if isinstance(nba_rm, dict) else None
            if isinstance(pc, dict):
                nba_role_map = pc
        except Exception:
            nba_role_map = {}

    to_add: list[AddRecord] = []

    # Determine missing players (exact string match).
    for name in active_players:
        if not isinstance(name, str) or not name.strip():
            continue
        player = name.strip()
        if player in existing:
            continue

        src = "default"
        pos = ""
        team = ""
        role = "ROLE_PLAYER"

        meta = nba_role_map.get(player)
        if isinstance(meta, dict):
            pos = str(meta.get("position") or "").strip()
            team = str(meta.get("team") or "").strip()
            role = _role_from_position(pos)
            src = "nba_role_mapping.json"

        to_add.append(AddRecord(player=player, assigned_role=role, source=src, position=pos, team=team))

    audit = {
        "schema_version": "role_mapping_audit.v1",
        "run_date": date.today().isoformat(),
        "paths": {
            "active_players": str(ACTIVE_PLAYERS_PATH),
            "role_mapping": str(ROLE_MAPPING_PATH),
            "nba_role_mapping": str(NBA_ROLE_MAPPING_PATH) if NBA_ROLE_MAPPING_PATH.exists() else None,
        },
        "counts": {
            "active_players": len(active_players),
            "already_classified": len([p for p in active_players if isinstance(p, str) and p.strip() in existing]),
            "added": len(to_add),
        },
        "added_players": [
            {
                "player": r.player,
                "assigned_role": r.assigned_role,
                "source": r.source,
                "position": r.position,
                "team": r.team,
            }
            for r in to_add
        ],
    }

    audit_path = OUTPUTS_DIR / f"role_mapping_audit_{date.today().strftime('%Y%m%d')}.json"
    _write_json(audit_path, audit)

    if args.dry_run:
        print(f"[DRY RUN] Would add {len(to_add)} players")
        print(f"[DRY RUN] Audit: {audit_path}")
        return 0

    if to_add:
        if args.backup:
            backup_path = ROLE_MAPPING_PATH.with_suffix(f".backup_{date.today().strftime('%Y%m%d')}.json")
            if not backup_path.exists():
                backup_path.write_text(ROLE_MAPPING_PATH.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"[BACKUP] {backup_path}")

        for r in to_add:
            existing[r.player] = r.assigned_role

        # Keep deterministic ordering (helps diffs)
        role_cfg["player_classifications"] = dict(sorted(existing.items(), key=lambda kv: kv[0].lower()))
        _write_json(ROLE_MAPPING_PATH, role_cfg)

    print(f"[OK] Active players: {len(active_players)}")
    print(f"[OK] Added players : {len(to_add)}")
    print(f"[OK] Audit written : {audit_path}")
    print(f"[OK] Updated       : {ROLE_MAPPING_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
