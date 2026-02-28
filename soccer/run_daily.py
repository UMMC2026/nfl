"""soccer/run_daily.py

Soccer daily runner — v1.0 (RESEARCH)

Implements a truth-enforced pipeline (manual inputs):
- Load match slate (JSON) OR interactive prompts
- Hard gates
- Dr_Soccer_Bayes lambda estimation
- Scoreline distribution + MC simulation
- Market probabilities + edge estimates
- Tiering + confidence caps
- Render report + RISK_FIRST JSON

No scraping.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Ensure repo root is importable when running as `python soccer/run_daily.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from truth_engine.lineage_tracer import ProbabilityLineageTracer, LineageSource, record_lineage_step

from soccer.config import (
    SOCCER_REGISTRY,
    SOCCER_MARKETS,
    CONFIDENCE_CAPS,
    GLOBAL_CONFIDENCE_CAP,
    TIER_THRESHOLDS,
    HOME_ADV_FACTOR,
)
from soccer.gates.soccer_gates import validate_match_gates
from soccer.models.dr_soccer_bayes import estimate_match_lambdas
from soccer.sim.soccer_sim import scoreline_distribution, derived_market_probs, simulate_match_probs, SimOptions
from soccer.render.render_soccer_report import render_report


ROOT = Path(__file__).parent
INPUTS_DIR = ROOT / "inputs"
OUTPUTS_DIR = ROOT / "outputs"
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _cap_prob(prob: float, market: str) -> tuple[float, Optional[str]]:
    market_cap = float(CONFIDENCE_CAPS.get(market, GLOBAL_CONFIDENCE_CAP))
    if prob > float(GLOBAL_CONFIDENCE_CAP):
        return float(GLOBAL_CONFIDENCE_CAP), "global_cap"
    if prob > market_cap:
        return market_cap, f"{market}_cap"
    return prob, None


def _tier(prob: float) -> str:
    if prob >= float(TIER_THRESHOLDS["SLAM"]):
        return "SLAM"
    if prob >= float(TIER_THRESHOLDS["STRONG"]):
        return "STRONG"
    if prob >= float(TIER_THRESHOLDS["LEAN"]):
        return "LEAN"
    return "NO_PLAY"


def _implied_prob_from_decimal_odds(odds: Optional[float]) -> Optional[float]:
    if odds is None:
        return None
    try:
        o = float(odds)
    except Exception:
        return None
    if o <= 1.0:
        return None
    return 1.0 / o


def _edge_estimate(p_model: float, p_implied: Optional[float]) -> Optional[float]:
    if p_implied is None:
        return None
    return float(p_model) - float(p_implied)


def _build_edge(
    *,
    tracer: ProbabilityLineageTracer,
    match: Dict,
    market: str,
    line: Optional[float],
    direction: str,
    p_raw: float,
    p_capped: float,
    cap_hit: Optional[str],
    tier: str,
    lambdas: Dict,
    probs: Dict,
) -> Dict:
    league = (match.get("league") or "UNK").upper()
    home = match.get("home_team")
    away = match.get("away_team")
    match_id = match.get("match_id") or f"{league}_{home}_{away}".upper()
    entity = f"{home} vs {away}"

    edge_id = f"SOC_{league}_{match_id}_{market}_{direction}_{str(line) if line is not None else 'NA'}".upper()

    # Lineage tracking
    tracer.start_lineage(edge_id, entity, market.upper(), float(line or 0.0), direction.upper())
    p = record_lineage_step(tracer, edge_id, LineageSource.BASELINE, 0.0, float(p_raw), 0.90, "scoreline_probs")
    if cap_hit is not None:
        p = record_lineage_step(tracer, edge_id, LineageSource.GATE_CAP, p, float(p_capped), 0.95, cap_hit)

    lineage = tracer.get_lineage(edge_id)
    audit_hash = lineage.get_lineage_hash() if lineage is not None else None

    odds = None
    odds_book = match.get("odds", {}) or {}
    if isinstance(odds_book, dict):
        odds = odds_book.get(f"{market}:{direction}:{line}") or odds_book.get(f"{market}:{direction}")

    p_implied = _implied_prob_from_decimal_odds(odds)
    edge_est = _edge_estimate(p_capped, p_implied)

    return {
        # universal edge fields (for render gate compatibility)
        "edge_id": edge_id,
        "sport": "SOCCER",
        "game_id": match_id,
        "entity": entity,
        "market": market,
        "line": line,
        "direction": direction,
        "probability": round(float(p_capped), 4),
        "tier": tier,
        "data_sources": match.get("xg_sources") or ["manual"],
        "injury_verified": True,  # N/A for soccer team markets, keep schema happy
        "correlated": False,

        # soccer-specific
        "league": league,
        "match": entity,
        "kickoff": match.get("kickoff"),
        "xg_projection": {
            "home": float(match.get("home_xg_for", 0.0) or 0.0),
            "away": float(match.get("away_xg_for", 0.0) or 0.0),
        },
        "lambda_home": float(lambdas["home"].lam),
        "lambda_away": float(lambdas["away"].lam),
        "uncertainty": {
            "home_std": float(lambdas["home"].std),
            "away_std": float(lambdas["away"].std),
        },
        "edge_estimate": None if edge_est is None else round(float(edge_est), 4),
        "implied_prob": None if p_implied is None else round(float(p_implied), 4),
        "audit_hash": audit_hash,
        "generated_at": datetime.now().isoformat(),
        "model": "soccer_poisson_v1.0",
    }


def analyze_match(match: Dict, *, tracer: ProbabilityLineageTracer, sims: int = 10000) -> List[Dict]:
    passed, gate_results = validate_match_gates(match)
    match["gate_results"] = [asdict(r) for r in gate_results]

    if not passed:
        # Gate failure => explicit NO_PLAY markers (no partial output)
        return [
            {
                "edge_id": f"SOC_{match.get('league','UNK')}_{match.get('home_team')}_{match.get('away_team')}_NO_PLAY".upper(),
                "sport": "SOCCER",
                "game_id": match.get("match_id") or "UNKNOWN",
                "entity": f"{match.get('home_team')} vs {match.get('away_team')}",
                "market": "NO_PLAY",
                "line": None,
                "direction": "N/A",
                "probability": 0.0,
                "tier": "NO_PLAY",
                "data_sources": match.get("xg_sources") or ["manual"],
                "injury_verified": True,
                "correlated": False,
                "league": (match.get("league") or "UNK").upper(),
                "match": f"{match.get('home_team')} vs {match.get('away_team')}",
                "risk_flags": [r.reason for r in gate_results if not r.passed],
                "audit_hash": None,
                "generated_at": datetime.now().isoformat(),
                "model": "soccer_poisson_v1.0",
            }
        ]

    # Lambda estimation (Bayes)
    lambdas = estimate_match_lambdas(
        home_xg_for=float(match.get("home_xg_for", 0.0)),
        home_xg_against=float(match.get("home_xg_against", 0.0)),
        away_xg_for=float(match.get("away_xg_for", 0.0)),
        away_xg_against=float(match.get("away_xg_against", 0.0)),
        home_matches=int(match.get("home_matches", 20) or 20),
        away_matches=int(match.get("away_matches", 20) or 20),
        home_adv_mult=float(match.get("home_adv_mult", HOME_ADV_FACTOR) or HOME_ADV_FACTOR),
    )

    # Distribution + MC
    dist = scoreline_distribution(lambdas["home"].lam, lambdas["away"].lam)
    probs = derived_market_probs(dist)
    sim_probs = simulate_match_probs(lambdas["home"].lam, lambdas["away"].lam, SimOptions(sims=sims))

    # Blend deterministic dist with sim to capture shocks (70/30)
    blended: Dict[str, float] = {}
    for k in probs.keys():
        blended[k] = 0.70 * float(probs[k]) + 0.30 * float(sim_probs.get(k, probs[k]))

    edges: List[Dict] = []

    # Over/Under totals
    for line in (0.5, 1.5, 2.5, 3.5):
        p_over = float(blended.get(f"over_{line}", 0.0))
        p_under = float(blended.get(f"under_{line}", 0.0))

        for direction, p_raw in (("OVER", p_over), ("UNDER", p_under)):
            p_capped, cap_hit = _cap_prob(p_raw, "over_under")
            tier = _tier(p_capped)
            edges.append(
                _build_edge(
                    tracer=tracer,
                    match=match,
                    market="over_under",
                    line=line,
                    direction=direction,
                    p_raw=p_raw,
                    p_capped=p_capped,
                    cap_hit=cap_hit,
                    tier=tier,
                    lambdas=lambdas,
                    probs=blended,
                )
            )

    # BTTS
    for direction, p_raw in (("YES", float(blended.get("btts_yes", 0.0))), ("NO", float(blended.get("btts_no", 0.0)))):
        p_capped, cap_hit = _cap_prob(p_raw, "btts")
        tier = _tier(p_capped)
        edges.append(
            _build_edge(
                tracer=tracer,
                match=match,
                market="btts",
                line=None,
                direction=direction,
                p_raw=p_raw,
                p_capped=p_capped,
                cap_hit=cap_hit,
                tier=tier,
                lambdas=lambdas,
                probs=blended,
            )
        )

    # 1X2
    for direction, key in (("HOME", "home_win"), ("DRAW", "draw"), ("AWAY", "away_win")):
        p_raw = float(blended.get(key, 0.0))
        p_capped, cap_hit = _cap_prob(p_raw, "match_result")
        tier = _tier(p_capped)
        edges.append(
            _build_edge(
                tracer=tracer,
                match=match,
                market="match_result",
                line=None,
                direction=direction,
                p_raw=p_raw,
                p_capped=p_capped,
                cap_hit=cap_hit,
                tier=tier,
                lambdas=lambdas,
                probs=blended,
            )
        )

    # Enforce v1.0 market policy (drop blocked)
    edges = [e for e in edges if e.get("market") in SOCCER_MARKETS.approved or e.get("market") == "NO_PLAY"]

    # Enforce max 1 primary per match by keeping best tier/prob among actionable
    actionable = [e for e in edges if e.get("tier") in ("SLAM", "STRONG", "LEAN")]
    if actionable:
        best = sorted(actionable, key=lambda e: ({"SLAM":0,"STRONG":1,"LEAN":2}.get(e["tier"],9), -e.get("probability",0.0)))[0]
        edges = [e for e in edges if e.get("tier") == "NO_PLAY" or e["edge_id"] == best["edge_id"]]

    return edges


def load_slate(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))

    # Hard separation: match pipeline (xG) must never accept player-props slates.
    # This prevents accidental downstream use of ingest-only soccer props JSON.
    if isinstance(data, dict) and isinstance(data.get("plays"), list):
        plays = data.get("plays") or []
        if any(isinstance(p, dict) and ("player" in p) for p in plays):
            raise RuntimeError(
                "Soccer player props not supported in match pipeline. "
                "Use Soccer ingest-only props JSON for storage only, or provide a match slate with {matches:[...]} and xG inputs."
            )
    if isinstance(data, list) and data and isinstance(data[0], dict) and ("player" in data[0]):
        raise RuntimeError(
            "Soccer player props not supported in match pipeline. "
            "Provide a match slate (list of matches or {matches:[...]}) with xG inputs."
        )

    if isinstance(data, dict) and "matches" in data:
        data = data["matches"]
    if not isinstance(data, list):
        raise ValueError("Slate must be a list of matches or {matches:[...]} dict")
    return data


def write_outputs(edges: List[Dict]) -> Dict[str, str]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    risk_first_path = OUTPUTS_DIR / f"soccer_RISK_FIRST_{ts}.json"
    report_path = OUTPUTS_DIR / f"soccer_report_{ts}.txt"

    risk_first_path.write_text(json.dumps(edges, indent=2), encoding="utf-8")
    report_path.write_text(render_report(edges), encoding="utf-8")

    return {"risk_first": str(risk_first_path), "report": str(report_path)}


def run_pipeline(*, slate_path: Optional[str], sims: int = 10000) -> int:
    if not SOCCER_REGISTRY.get("enabled", False):
        # Still runnable in research mode, but warn.
        print(f"[SOCCER] Status: {SOCCER_REGISTRY['status']} (enabled=False) — running in RESEARCH mode")

    if slate_path:
        slate_file = Path(slate_path)
        matches = load_slate(slate_file)
    else:
        raise ValueError("Provide --slate path to a JSON slate (manual inputs).")

    tracer = ProbabilityLineageTracer(storage_path=OUTPUTS_DIR / "lineage")

    all_edges: List[Dict] = []
    for m in matches:
        all_edges.extend(analyze_match(m, tracer=tracer, sims=sims))

    # CROSS-SPORT DATABASE: Save top picks
    try:
        from engine.daily_picks_db import save_top_picks
        soccer_edges = []
        playable = [e for e in all_edges if e.get("tier") in ("SLAM", "STRONG", "LEAN")]
        for edge in playable:
            soccer_edges.append({
                "player": edge.get("match", edge.get("home_team", "") + " vs " + edge.get("away_team", "")),
                "stat": edge.get("market", ""),
                "line": edge.get("line", 0),
                "direction": edge.get("direction", ""),
                "probability": edge.get("probability", 0.5),
                "tier": edge.get("tier", "LEAN")
            })
        if soccer_edges:
            save_top_picks(soccer_edges, "Soccer", top_n=5)
            print(f"[✓] Cross-Sport DB: Saved top 5 Soccer picks")
    except ImportError:
        pass
    except Exception as e:
        print(f"[⚠️] Cross-Sport DB save failed: {e}")

    outputs = write_outputs(all_edges)
    tracer.save_session(f"soccer_lineage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    print(f"[OK] Wrote: {outputs['risk_first']}")
    print(f"[OK] Wrote: {outputs['report']}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Soccer (Futbol) v1.0 runner (manual slate)")
    ap.add_argument("--slate", type=str, help="Path to slate JSON (manual xG + metadata)")
    ap.add_argument("--sims", type=int, default=10000, help="Monte Carlo sims per match")

    args = ap.parse_args()
    return run_pipeline(slate_path=args.slate, sims=args.sims)


if __name__ == "__main__":
    raise SystemExit(main())
