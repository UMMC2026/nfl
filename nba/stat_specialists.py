"""NBA specialist compatibility wrapper.

Canonical stat-specialist logic lives in the pure module `stat_specialist_engine.py`.
This file exists to keep older imports stable (e.g., `from nba.stat_specialists import ...`).

IMPORTANT: Do not add new logic here. Keep this as a thin adapter to avoid
duplicated rules drifting over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from stat_specialist_engine import (
    StatSpecialist as StatSpecialistType,
    SPECIALIST_CONFIDENCE_CAP as _SPECIALIST_CONFIDENCE_CAP,
    classify_stat_specialist,
    apply_specialist_confidence_cap,
)


# Back-compat: some call sites expect percent ceilings.
SPECIALIST_CONFIDENCE_CEILINGS: Dict[StatSpecialistType, float] = {
    k: float(v) * 100.0 for k, v in _SPECIALIST_CONFIDENCE_CAP.items()
}


def get_matchup_delta_weight(stat: str, specialist: StatSpecialistType) -> float:
    """Matchup memory interaction weight.

    This helper is used by matchup-memory integration.
    """
    stat_u = str(stat or "").upper()
    if stat_u in {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"} and specialist in {
        StatSpecialistType.CATCH_AND_SHOOT_3PM,
        StatSpecialistType.BIG_MAN_3PM,
    }:
        return 1.25
    return 0.85


@dataclass(frozen=True)
class SpecialistClassification:
    specialist: StatSpecialistType
    source: str
    metadata: Dict[str, Any]


class StatSpecialistClassifier:
    """Stat-specialist classifier adapter.

    The canonical rules-based classifier is `classify_stat_specialist(...)`.
    This wrapper supports an optional manual mapping dict.
    """

    def __init__(self, *, mapping: Optional[Dict[str, str]] = None):
        self._mapping = mapping or {}

    def classify(
        self,
        player_name: str,
        *,
        stat: Optional[str] = None,
        prop: Optional[Dict[str, Any]] = None,
    ) -> SpecialistClassification:
        name = str(player_name or "").strip()
        prop = prop or {}

        mapped = self._mapping.get(name)
        if mapped:
            try:
                return SpecialistClassification(
                    specialist=StatSpecialistType(mapped),
                    source="manual",
                    metadata={},
                )
            except Exception:
                pass

        specialist = classify_stat_specialist(prop, stat or prop.get("stat"))
        return SpecialistClassification(
            specialist=specialist,
            source="engine",
            metadata={},
        )


def get_specialist_ceiling(specialist: StatSpecialistType) -> Optional[float]:
    """Return the confidence ceiling (percent) for a specialist, if defined."""
    return SPECIALIST_CONFIDENCE_CEILINGS.get(specialist)


def apply_specialist_confidence_governance(
    *,
    stat: str,
    line: Any,
    confidence_percent: float,
    specialist: StatSpecialistType,
    role_archetype: Optional[str] = None,
) -> Tuple[float, Dict[str, Any]]:
    """Apply specialist caps and volatility dampening.

    This function never increases confidence.
    Returns: (new_confidence_percent, metadata)
    """
    _ = role_archetype  # Role alignment is handled elsewhere; keep this adapter pure.

    stat_u = str(stat or "").upper()
    meta: Dict[str, Any] = {
        "specialist": getattr(specialist, "value", str(specialist)),
        "ceiling": None,
        "ceiling_applied": False,
        "hard_avoid": False,
        "hard_avoid_reason": None,
    }

    try:
        spec = specialist if isinstance(specialist, StatSpecialistType) else StatSpecialistType(str(specialist))
    except Exception:
        spec = StatSpecialistType.GENERIC

    ceiling = get_specialist_ceiling(spec)
    if isinstance(ceiling, (int, float)):
        meta["ceiling"] = float(ceiling)

    # Hard avoid metadata: Big-man 3PM at 3.5+
    try:
        line_f = float(line)
    except Exception:
        line_f = None
    if stat_u in {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"}:
        if spec == StatSpecialistType.BIG_MAN_3PM and isinstance(line_f, (int, float)) and line_f >= 3.5:
            meta["hard_avoid"] = True
            meta["hard_avoid_reason"] = "BIG_MAN_3PM_3.5_PLUS_AVOID"

    new_conf = float(apply_specialist_confidence_cap(float(confidence_percent), spec))
    if new_conf < float(confidence_percent):
        meta["ceiling_applied"] = True

    return new_conf, meta
