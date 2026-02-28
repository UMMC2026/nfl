"""tennis/tennis_quant_export.py

Governed quant export for Tennis.

Purpose
- Convert tennis props analysis results into canonical Edge + Signals artifacts.
- Apply EligibilityGate to produce pick_state and governance artifacts.

Artifacts written (mirrors soccer conventions):
- outputs/tennis_signals_latest.json (sport-scoped, stable)
- outputs/tennis_signals_<timestamp>.json (sport-scoped, timestamped)
- tennis/outputs/signals_latest.json (tennis-local legacy)
- tennis/outputs/governance_*.json (+ allowed/blocked exports via governance_artifacts)

Notes
- Signals include ONLY OPTIMIZABLE picks with tier in {LEAN, STRONG, SLAM}.
- Tiers are computed via config/thresholds.py (single source of truth).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.thresholds import implied_tier

try:
    from core.decision_governance import EligibilityGate
except Exception:  # pragma: no cover
    EligibilityGate = None  # type: ignore


def _stable_edge_id(*, player: str, opponent: str, stat: str, direction: str, line: float) -> str:
    key = f"{player}|{opponent}|{stat}|{direction}|{line}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _norm_direction(direction: str) -> str:
    d = str(direction or "").strip().lower()
    if d in {"higher", "over", "more", "hi", "up"} or d.startswith("hi"):
        return "higher"
    if d in {"lower", "under", "less", "lo", "down"} or d.startswith("lo"):
        return "lower"
    # Fallback: treat unknown as-is
    return d


def export_tennis_match_winner_quant_artifacts(
    scored_output: Dict[str, Any],
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Export governed quant artifacts for Tennis match-winner pipeline.

    Writes/updates:
      - outputs/tennis_signals_latest.json (merged; replaces only match_winner subset)
      - tennis/outputs/signals_latest.json (same merged content)

    Only exports playable picks (tiers SLAM/STRONG/LEAN, not blocked).
    """
    root_outputs = Path("outputs")
    root_outputs.mkdir(exist_ok=True)

    tennis_outputs = Path(__file__).resolve().parent / "outputs"
    tennis_outputs.mkdir(exist_ok=True)

    edges = (scored_output or {}).get("edges") or []
    if not isinstance(edges, list):
        edges = []

    playable: List[Dict[str, Any]] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        tier = str(e.get("tier") or "").upper()
        if e.get("blocked"):
            continue
        if tier not in {"SLAM", "STRONG", "LEAN"}:
            continue

        prob = float(e.get("probability") or 0.0)
        # Probability in match-winner output is already decimal (0-1)
        signal: Dict[str, Any] = {
            "edge_id": f"TENNIS_MATCH_{e.get('match_id','')}_{str(e.get('player') or '').strip()}".strip(),
            "sport": "TENNIS",
            "entity": e.get("player"),
            # Back-compat keys used by existing Telegram/parlay helpers
            "player": e.get("player"),
            "opponent": e.get("opponent"),
            "market": "match_winner",
            "stat": "ML",
            "line": e.get("line"),
            "direction": "higher",  # treat as "win" for UI arrow
            "probability": prob,
            "tier": tier,
            "pick_state": "OPTIMIZABLE",
            "generated_at": datetime.now().isoformat(),
        }
        if source:
            signal["source"] = source
        playable.append(signal)

    # Merge with existing signals_latest (preserve props, replace match_winner)
    signals_latest = root_outputs / "tennis_signals_latest.json"
    existing: List[Dict[str, Any]] = []
    try:
        if signals_latest.exists():
            raw = json.loads(signals_latest.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = [s for s in raw if isinstance(s, dict)]
    except Exception:
        existing = []

    merged: List[Dict[str, Any]] = []
    for s in existing:
        if str(s.get("market") or "").lower() == "match_winner":
            continue
        merged.append(s)
    merged.extend(playable)

    # Deduplicate by edge_id when present, else by (player/stat/line/tier)
    seen = set()
    unique: List[Dict[str, Any]] = []
    for s in merged:
        eid = str(s.get("edge_id") or "").strip().lower()
        if eid:
            key = ("edge_id", eid)
        else:
            key = (
                str(s.get("player") or s.get("entity") or "").strip().lower(),
                str(s.get("stat") or s.get("market") or "").strip().lower(),
                str(s.get("line") or ""),
                str(s.get("tier") or "").strip().upper(),
            )
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    signals_latest.write_text(json.dumps(unique, indent=2), encoding="utf-8")
    tennis_signals_latest = tennis_outputs / "signals_latest.json"
    tennis_signals_latest.write_text(json.dumps(unique, indent=2), encoding="utf-8")

    return {
        "signals_latest": signals_latest,
        "tennis_signals_latest": tennis_signals_latest,
        "exported_match_winner": len(playable),
        "merged_total": len(unique),
    }
    return "higher" if "high" in d else "lower" if "low" in d else d


def build_quant_edges_from_props_results(
    results: Dict[str, Any],
    *,
    sport: str = "TENNIS",
    source: str = "tennis_props",
) -> List[Dict[str, Any]]:
    """Convert CalibratedTennisPropsEngine results into canonical edge dicts."""

    gate = EligibilityGate() if EligibilityGate else None

    edges: List[Dict[str, Any]] = []
    for r in (results or {}).get("results") or []:
        player = (r or {}).get("player")
        stat = (r or {}).get("stat") or (r or {}).get("stat_type")
        line = (r or {}).get("line")
        direction_raw = (r or {}).get("direction")
        opponent = (r or {}).get("opponent") or ""

        if not (player and stat and line is not None and direction_raw):
            continue

        try:
            prob = float((r or {}).get("probability") or 0.0)
        except Exception:
            prob = 0.0

        # Canonical tier assignment
        tier = implied_tier(prob, sport)

        # Fragility heuristic for tennis props: small sample profile should never be optimizable.
        profile = (r or {}).get("profile_data") or {}
        try:
            sample_n = int(profile.get("n_matches") or 0)
        except Exception:
            sample_n = 0

        is_fragile = 0 < sample_n < 5

        pick_state = "REJECTED"
        eligibility_dict: Optional[Dict[str, Any]] = None

        if gate:
            try:
                elig = gate.evaluate(
                    {
                        "player": player,
                        "stat": stat,
                        "line": line,
                        "direction": direction_raw,
                        "probability": prob,
                        "is_fragile": is_fragile,
                    }
                )
                eligibility_dict = elig.to_dict()
                pick_state = str(elig.state.value)
            except Exception:
                pick_state = "VETTED" if is_fragile else "REJECTED"
        else:
            # Conservative fallback: require the canonical LEAN threshold at minimum.
            pick_state = "OPTIMIZABLE" if tier in {"LEAN", "STRONG", "SLAM"} and not is_fragile else "VETTED"

        sim = (r or {}).get("simulation") or {}
        try:
            mu = float(sim.get("mean") or 0.0)
        except Exception:
            mu = 0.0
        try:
            sigma = float(sim.get("std") or 0.0)
        except Exception:
            sigma = 0.0

        # Some props may not have reliable sim std; provide a conservative audit fallback.
        if sigma <= 0 and mu > 0:
            sigma = abs(mu) * 0.25

        direction = _norm_direction(str(direction_raw))
        edge = {
            "edge_id": _stable_edge_id(
                player=str(player),
                opponent=str(opponent),
                stat=str(stat).lower().strip(),
                direction=direction,
                line=float(line),
            ),
            "sport": sport,
            "entity": player,
            "player": player,
            "team": "",
            "opponent": opponent,
            "market": str(stat).lower().strip(),
            "stat": str(stat).lower().strip(),
            "line": float(line),
            "direction": direction,
            "probability": prob,
            "tier": tier,
            "pick_state": pick_state,
            "mu": mu,
            "sigma": sigma,
            "sample_n": sample_n,
            "source": source,
        }

        if eligibility_dict is not None:
            edge["eligibility"] = eligibility_dict

        edges.append(edge)

    return edges


def export_tennis_props_quant_artifacts(
    results: Dict[str, Any],
    *,
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write tennis props quant artifacts (signals + governance) like soccer."""

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stamp = datetime.now().strftime("%Y%m%d")
    slug = "TENNIS_PROPS"

    edges = build_quant_edges_from_props_results(results, sport="TENNIS", source="tennis_props")

    signals = [
        e
        for e in edges
        if e.get("pick_state") == "OPTIMIZABLE" and e.get("tier") in {"LEAN", "STRONG", "SLAM"}
    ]

    root_outputs = Path("outputs")
    root_outputs.mkdir(parents=True, exist_ok=True)

    tennis_outputs = Path(__file__).resolve().parent / "outputs"
    tennis_outputs.mkdir(parents=True, exist_ok=True)

    signals_latest = root_outputs / "tennis_signals_latest.json"
    signals_ts = root_outputs / f"tennis_signals_{ts}.json"
    tennis_signals_latest = tennis_outputs / "signals_latest.json"

    signals_latest.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    signals_ts.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    tennis_signals_latest.write_text(json.dumps(signals, indent=2), encoding="utf-8")

    # Governance-style payload (sport-local) for audit + blocked reasons.
    results_rows: List[Dict[str, Any]] = []
    for e in edges:
        p = float(e.get("probability") or 0.0)
        tier = str(e.get("tier") or "AVOID").upper()
        state = str(e.get("pick_state") or "REJECTED").upper()

        if state != "OPTIMIZABLE":
            decision = "BLOCKED"
            block_reason = f"pick_state={state}"
        elif tier in {"SLAM", "STRONG"}:
            decision = "PLAY"
            block_reason = None
        elif tier == "LEAN":
            decision = "LEAN"
            block_reason = None
        else:
            decision = "BLOCKED"
            block_reason = f"tier={tier}"

        mu = float(e.get("mu") or 0.0)
        sigma = float(e.get("sigma") or 0.0)
        if sigma <= 0 and mu > 0:
            sigma = abs(mu) * 0.25

        results_rows.append(
            {
                "player": e.get("player"),
                "team": e.get("team"),
                "opponent": e.get("opponent"),
                "stat": e.get("stat"),
                "line": e.get("line"),
                "direction": e.get("direction"),
                "decision": decision,
                "block_reason": block_reason,
                "model_confidence": p * 100.0,
                "effective_confidence": p * 100.0,
                "mu": mu,
                "sigma": sigma,
                "sample_n": int(e.get("sample_n") or 0),
                "prob_method": "monte_carlo",
                "gate_details": [e.get("eligibility")] if e.get("eligibility") else [],
                "source": e.get("source"),
            }
        )

    analysis_payload = {
        "sport": "TENNIS",
        "slug": slug,
        "stamp": stamp,
        "created_at_local": datetime.now().isoformat(),
        "source": source or {},
        "results": results_rows,
    }

    try:
        from governance_artifacts import export_governance_artifacts

        governance_exports = export_governance_artifacts(
            analysis_payload,
            slug=slug,
            stamp=stamp,
            out_dir=tennis_outputs,
            run_settings=None,
            source=source or {},
        )
    except Exception:
        governance_exports = {}

    return {
        "slug": slug,
        "stamp": stamp,
        "edges": edges,
        "signals": signals,
        "signals_latest": signals_latest,
        "signals_timestamped": signals_ts,
        "tennis_signals_latest": tennis_signals_latest,
        "governance_exports": governance_exports,
    }
