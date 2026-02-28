"""hq_options.py

HQ Quant-style options loader.

Principles:
- One engine, one order of operations.
- Options only *clamp* (cap probabilities, restrict stat window), never bypass gates.
- Options must be deterministic and usable in backtests (pass the same JSON).

Sources (first wins):
- HQ_OPTIONS_JSON: inline JSON string
- HQ_OPTIONS_PATH: path to JSON file

Schema (minimal):
{
  "injury_return": {
    "enabled": true,
    "players": ["Player A", "Player B"],
    "games_back_threshold": 2,
    "stat_window": "last_5",
    "projection_multiplier": 0.92,
    "max_probability": 0.58
  },
  "player_overrides": {
    "Stephen Curry": {
      "allow_analysis": true,
      "max_probability": 0.55
    }
  },
  "reporting": {
    "top_n_per_team": 5,
    "include_status": ["PLAY", "LEAN", "ANALYSIS_ONLY"]
  }
}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _as_float(v: Any, default: float) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _as_optional_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _as_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _as_str(v: Any, default: str = "") -> str:
    return str(v) if isinstance(v, str) else default


def _as_str_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v if isinstance(x, str) and str(x).strip()]
    if isinstance(v, str):
        # allow comma-separated
        return [p.strip() for p in v.split(",") if p.strip()]
    return []


@dataclass(frozen=True)
class InjuryReturnOptions:
    enabled: bool = False
    players: list[str] = field(default_factory=list)
    games_back_threshold: int = 2
    stat_window: str = "last_5"  # currently only last_5 is implemented
    projection_multiplier: float = 0.92
    max_probability: float = 0.58  # expressed as 0..1


@dataclass(frozen=True)
class PlayerOverride:
    allow_analysis: bool = False
    max_probability: Optional[float] = None  # expressed as 0..1


@dataclass(frozen=True)
class ReportingOptions:
    top_n_per_team: int = 5
    include_status: list[str] = field(default_factory=lambda: ["PLAY", "LEAN", "ANALYSIS_ONLY"])


@dataclass(frozen=True)
class HQOptions:
    injury_return: InjuryReturnOptions = InjuryReturnOptions()
    player_overrides: Dict[str, PlayerOverride] = field(default_factory=dict)
    reporting: ReportingOptions = ReportingOptions()
    source: str = "default"  # default|env_json|file
    source_path: str = ""


def _parse_options_dict(d: Dict[str, Any], *, source: str, source_path: str = "") -> HQOptions:
    inj_raw = d.get("injury_return")
    injury: Dict[str, Any] = inj_raw if isinstance(inj_raw, dict) else {}

    rep_raw = d.get("reporting")
    reporting: Dict[str, Any] = rep_raw if isinstance(rep_raw, dict) else {}

    inj = InjuryReturnOptions(
        enabled=_as_bool(injury.get("enabled"), False),
        players=_as_str_list(injury.get("players")),
        games_back_threshold=_as_int(injury.get("games_back_threshold"), 2),
        stat_window=_as_str(injury.get("stat_window"), "last_5") or "last_5",
        projection_multiplier=_as_float(injury.get("projection_multiplier"), 0.92),
        max_probability=_as_float(injury.get("max_probability"), 0.58),
    )

    overrides: Dict[str, PlayerOverride] = {}
    po = d.get("player_overrides")
    if isinstance(po, dict):
        for name, od in po.items():
            if not isinstance(name, str) or not name.strip():
                continue
            if not isinstance(od, dict):
                continue
            overrides[name.strip()] = PlayerOverride(
                allow_analysis=_as_bool(od.get("allow_analysis"), False),
                max_probability=_as_optional_float(od.get("max_probability")),
            )

    rep = ReportingOptions(
        top_n_per_team=max(1, _as_int(reporting.get("top_n_per_team"), 5)),
        include_status=[str(x).strip().upper() for x in _as_str_list(reporting.get("include_status"))] or ["PLAY", "LEAN", "ANALYSIS_ONLY"],
    )

    return HQOptions(
        injury_return=inj,
        player_overrides=overrides,
        reporting=rep,
        source=source,
        source_path=source_path,
    )


def load_hq_options_from_env() -> HQOptions:
    """Load HQ options from env.

    Never raises; defaults are returned on any error.
    """
    inline = os.getenv("HQ_OPTIONS_JSON", "").strip()
    if inline:
        try:
            data = json.loads(inline)
            if isinstance(data, dict):
                return _parse_options_dict(data, source="env_json")
        except Exception:
            return HQOptions()

    path = os.getenv("HQ_OPTIONS_PATH", "").strip()
    if path:
        try:
            p = Path(path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return _parse_options_dict(data, source="file", source_path=str(p))
        except Exception:
            return HQOptions()

    return HQOptions()
