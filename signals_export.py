"""signals_export.py

Create standardized Telegram/bot signal outputs from risk-first analysis results.

Primary consumer today:
- `ufa/services/telegram_simple.py` which reads `output/signals_latest.json` and posts top picks.

Standard requested:
- For a single game (<=2 teams in slate): Top 3 picks (PLAY first, then LEAN fill).
- For multi-team slates (>2 teams): "strong" picks per team (PLAY picks, prefer ELITE/STRONG).

This module only writes local JSON files; it does not send messages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class SignalsExportResult:
    signals: List[Dict[str, Any]]
    mode: str
    path: str


def _tier_for_result(r: Dict[str, Any]) -> str:
    decision = r.get("decision")
    edge_quality = r.get("edge_quality")

    if decision == "PLAY":
        if edge_quality == "ELITE":
            return "SLAM"
        return "STRONG"

    if decision == "LEAN":
        return "LEAN"

    return "AVOID"


def _score(r: Dict[str, Any]) -> float:
    # Prefer effective confidence, then edge magnitude (z_score)
    eff = float(r.get("effective_confidence", 0.0))
    z = abs(float(r.get("z_score", 0.0)))
    return eff * 1000.0 + z


def build_signals_from_risk_first(analysis: Dict[str, Any]) -> SignalsExportResult:
    results = analysis.get("results") or []

    # Only consider PLAY/LEAN for publishing.
    candidates = [r for r in results if r.get("decision") in {"PLAY", "LEAN"}]

    teams = sorted({r.get("team") for r in results if r.get("team")})
    multi_team = len(teams) > 2

    signals: List[Dict[str, Any]] = []

    if not multi_team:
        # Single game: take top 3 overall (PLAY first, then LEAN)
        plays = sorted([r for r in candidates if r.get("decision") == "PLAY"], key=_score, reverse=True)
        leans = sorted([r for r in candidates if r.get("decision") == "LEAN"], key=_score, reverse=True)

        picked = (plays + leans)[:3]
        mode = "single_game_top3"

        for r in picked:
            signals.append(
                {
                    "tier": _tier_for_result(r),
                    "player": r.get("player"),
                    "team": r.get("team"),
                    "stat": r.get("stat"),
                    "line": r.get("line"),
                    "direction": r.get("direction"),
                    "probability": float(r.get("effective_confidence", 0.0)) / 100.0,
                    "edge": float(r.get("edge", 0.0)),
                    "edge_quality": r.get("edge_quality"),
                    "z_score": float(r.get("z_score", 0.0)),
                    "source": "risk_first",
                }
            )

    else:
        # Multi-team: export strong picks per team
        mode = "multi_team_strong_per_team"

        by_team: Dict[str, List[Dict[str, Any]]] = {}
        for r in candidates:
            team = r.get("team")
            if not team:
                continue
            by_team.setdefault(team, []).append(r)

        for team in sorted(by_team.keys()):
            team_rows = by_team[team]

            # Prefer PLAY, and within those prefer ELITE/STRONG
            strong = [
                r
                for r in team_rows
                if r.get("decision") == "PLAY" and r.get("edge_quality") in {"ELITE", "STRONG"}
            ]
            if not strong:
                # Fall back to any PLAY picks
                strong = [r for r in team_rows if r.get("decision") == "PLAY"]

            strong = sorted(strong, key=_score, reverse=True)[:3]
            for r in strong:
                signals.append(
                    {
                        "tier": _tier_for_result(r),
                        "player": r.get("player"),
                        "team": team,
                        "stat": r.get("stat"),
                        "line": r.get("line"),
                        "direction": r.get("direction"),
                        "probability": float(r.get("effective_confidence", 0.0)) / 100.0,
                        "edge": float(r.get("edge", 0.0)),
                        "edge_quality": r.get("edge_quality"),
                        "z_score": float(r.get("z_score", 0.0)),
                        "source": "risk_first",
                    }
                )

    outdir = Path("output")
    outdir.mkdir(parents=True, exist_ok=True)

    # IMPORTANT: `ufa/services/telegram_simple.py` expects this file to be a JSON LIST.
    outpath = outdir / "signals_latest.json"
    outpath.write_text(json.dumps(signals, indent=2), encoding="utf-8")

    # Write metadata separately for troubleshooting/auditing.
    meta_path = outdir / "signals_latest_meta.json"
    meta_payload = {
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "mode": mode,
        "count": len(signals),
    }

    # Optional audit trail: include HQ options source when present.
    try:
        hq = analysis.get("hq_options")
        if isinstance(hq, dict):
            meta_payload["hq_options"] = {
                "source": hq.get("source"),
                "source_path": hq.get("source_path"),
            }
    except Exception:
        pass
    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

    return SignalsExportResult(signals=signals, mode=mode, path=str(outpath))


def load_bot_signals_list() -> List[Dict[str, Any]]:
    """Return the list format that telegram_simple currently expects."""
    p = Path("output") / "signals_latest.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))
