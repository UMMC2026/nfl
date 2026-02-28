"""
Tennis Validate Output — HARD GATE
===================================
Final validation before any tennis edge is released.

THIS IS A GATE — failure blocks output.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

TENNIS_DIR = Path(__file__).parent.parent
CONFIG_DIR = TENNIS_DIR / "config"

# GOVERNANCE: tier thresholds must come from config/thresholds.py (canonical).
try:
    from config.thresholds import get_tier_threshold
except Exception:  # pragma: no cover
    get_tier_threshold = None  # type: ignore


# =============================================================================
# VALIDATION RULES
# =============================================================================

REQUIRED_EDGE_FIELDS = {
    "edge_id",
    "sport",
    "engine",
    "market",
    "direction",
    "probability",
    "tier",
    "blocked",
    "generated_at",
}

VALID_MARKETS = {"TOTAL_GAMES", "TOTAL_SETS", "PLAYER_ACES"}
VALID_TIERS = {"STRONG", "LEAN", "NO_PLAY", "BLOCKED"}
VALID_DIRECTIONS = {"OVER", "UNDER"}

def _prob_clamp_from_config() -> Tuple[float, float]:
    path = CONFIG_DIR / "tennis_global.json"
    try:
        if path.exists():
            global_config = json.loads(path.read_text(encoding="utf-8"))
        else:
            global_config = {}
    except Exception:
        global_config = {}

    clamp = global_config.get("probability_clamp", {}) if isinstance(global_config, dict) else {}
    try:
        lo = float(clamp.get("min", 0.55))
        hi = float(clamp.get("max", 0.72))
        if 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0 and lo < hi:
            return lo, hi
    except Exception:
        pass
    return 0.55, 0.72


PROB_CLAMP = _prob_clamp_from_config()


def load_global_config() -> Dict:
    path = CONFIG_DIR / "tennis_global.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def validate_edge_schema(edge: Dict) -> List[str]:
    """Validate required fields and types."""
    errors = []
    
    # Check required fields
    missing = REQUIRED_EDGE_FIELDS - set(edge.keys())
    if missing:
        errors.append(f"MISSING_FIELDS::{missing}")
    
    # Market validation
    market = edge.get("market")
    if market not in VALID_MARKETS:
        errors.append(f"INVALID_MARKET::{market}")
    
    # Tier validation
    tier = edge.get("tier")
    if tier not in VALID_TIERS:
        errors.append(f"INVALID_TIER::{tier}")
    
    # Direction validation (if not blocked)
    if not edge.get("blocked"):
        direction = edge.get("direction")
        if direction not in VALID_DIRECTIONS:
            errors.append(f"INVALID_DIRECTION::{direction}")
    
    return errors


def validate_probability_bounds(edge: Dict) -> List[str]:
    """Validate probability is within clamp bounds."""
    errors = []
    
    if edge.get("blocked"):
        return errors
    
    prob = edge.get("probability")
    if prob is None:
        errors.append("PROBABILITY_NULL")
        return errors
    
    lo, hi = PROB_CLAMP
    if not (lo <= prob <= hi):
        errors.append(f"PROBABILITY_OUT_OF_BOUNDS::{prob:.4f} not in [{lo}, {hi}]")
    
    return errors


def validate_tier_consistency(edge: Dict) -> List[str]:
    """Validate tier matches probability."""
    errors = []
    
    if edge.get("blocked"):
        if edge.get("tier") != "BLOCKED":
            errors.append("BLOCKED_EDGE_WRONG_TIER")
        return errors
    
    prob = edge.get("probability")
    tier = edge.get("tier")
    
    if prob is None:
        return errors
    
    if get_tier_threshold is None:
        return errors

    try:
        strong_min = float(get_tier_threshold("STRONG", "TENNIS"))
        lean_min = float(get_tier_threshold("LEAN", "TENNIS"))
    except Exception:
        return errors

    # This tennis module intentionally does not emit SLAM in daily runs.
    if tier == "STRONG" and prob < strong_min:
        errors.append(f"TIER_PROB_MISMATCH::STRONG requires ≥{strong_min:.2f}, got {prob:.4f}")
    elif tier == "LEAN" and (prob >= strong_min or prob < lean_min):
        if prob >= strong_min:
            errors.append(f"TIER_PROB_MISMATCH::LEAN at {prob:.4f} should be STRONG")
        elif prob < lean_min:
            errors.append(f"TIER_PROB_MISMATCH::LEAN at {prob:.4f} should be NO_PLAY")
    elif tier == "NO_PLAY" and prob >= lean_min:
        errors.append(f"TIER_PROB_MISMATCH::NO_PLAY at {prob:.4f} should be LEAN or higher")
    
    return errors


def validate_engine_isolation(edges: List[Dict]) -> List[str]:
    """Validate no player appears in multiple engines (correlation blocking)."""
    errors = []
    
    # Track players by engine
    player_engines: Dict[str, Set[str]] = {}
    
    for edge in edges:
        if edge.get("blocked"):
            continue
        
        engine = edge.get("engine", "")
        players = set()
        
        # Extract player(s)
        if "player" in edge:
            players.add(edge["player"].lower())
        if "players" in edge:
            for p in edge["players"]:
                players.add(p.lower())
        if "opponent" in edge:
            players.add(edge["opponent"].lower())
        
        for p in players:
            if p not in player_engines:
                player_engines[p] = set()
            player_engines[p].add(engine)
    
    # Check for cross-engine correlation
    for player, engines in player_engines.items():
        if len(engines) > 1:
            errors.append(f"CORRELATION_VIOLATION::{player} in {engines}")
    
    return errors


def validate_daily_cap(edges: List[Dict], max_total: int = 5) -> List[str]:
    """Validate total plays doesn't exceed daily cap."""
    errors = []
    
    playable = [e for e in edges if not e.get("blocked") and e.get("tier") in ("STRONG", "LEAN")]
    
    if len(playable) > max_total:
        errors.append(f"DAILY_CAP_EXCEEDED::{len(playable)} > {max_total}")
    
    return errors


def validate_blocked_edges(edges: List[Dict]) -> List[str]:
    """Validate blocked edges have block_reason."""
    errors = []
    
    for edge in edges:
        if edge.get("blocked"):
            if not edge.get("block_reason"):
                errors.append(f"BLOCKED_NO_REASON::{edge.get('edge_id')}")
    
    return errors


# =============================================================================
# MAIN VALIDATION
# =============================================================================

def validate_tennis_output(data: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Run all validation rules.
    
    Returns: (passed, errors, summary)
    """
    global_config = load_global_config()
    operational = global_config.get("operational_limits", {})
    max_daily = operational.get("max_daily_plays", 5)
    
    all_errors = []
    
    # Collect all edges from all engine outputs
    edges = data.get("edges", [])
    blocked = data.get("blocked", [])
    all_edges = edges + blocked
    
    # Schema validation
    for edge in all_edges:
        errs = validate_edge_schema(edge)
        all_errors.extend(errs)
    
    # Probability bounds
    for edge in edges:
        errs = validate_probability_bounds(edge)
        all_errors.extend(errs)
    
    # Tier consistency
    for edge in edges:
        errs = validate_tier_consistency(edge)
        all_errors.extend(errs)
    
    # Engine isolation
    errs = validate_engine_isolation(edges)
    all_errors.extend(errs)
    
    # Daily cap
    errs = validate_daily_cap(edges, max_daily)
    all_errors.extend(errs)
    
    # Blocked edges
    errs = validate_blocked_edges(blocked)
    all_errors.extend(errs)
    
    passed = len(all_errors) == 0
    
    summary = {
        "validated_at": datetime.utcnow().isoformat() + "Z",
        "passed": passed,
        "error_count": len(all_errors),
        "edges_checked": len(all_edges),
        "playable_count": len([e for e in edges if e.get("tier") in ("STRONG", "LEAN")]),
        "blocked_count": len(blocked),
    }
    
    return passed, all_errors, summary


def validate_merged_output(merged: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Validate merged output from all engines.
    
    Expected structure:
    {
        "engines": {
            "TOTAL_GAMES_ENGINE": { "edges": [...], "blocked": [...] },
            "TOTAL_SETS_ENGINE": { "edges": [...], "blocked": [...] },
            "PLAYER_ACES_ENGINE": { "edges": [...], "blocked": [...] }
        }
    }
    """
    global_config = load_global_config()
    operational = global_config.get("operational_limits", {})
    max_daily = operational.get("max_daily_plays", 5)
    
    all_errors = []
    all_edges = []
    all_blocked = []
    
    engines_data = merged.get("engines", {})
    
    for engine_name, engine_data in engines_data.items():
        edges = engine_data.get("edges", [])
        blocked = engine_data.get("blocked", [])
        
        all_edges.extend(edges)
        all_blocked.extend(blocked)
        
        # Schema validation
        for edge in edges + blocked:
            errs = validate_edge_schema(edge)
            all_errors.extend([f"{engine_name}::{e}" for e in errs])
        
        # Probability bounds
        for edge in edges:
            errs = validate_probability_bounds(edge)
            all_errors.extend([f"{engine_name}::{e}" for e in errs])
        
        # Tier consistency
        for edge in edges:
            errs = validate_tier_consistency(edge)
            all_errors.extend([f"{engine_name}::{e}" for e in errs])
    
    # Cross-engine validation
    errs = validate_engine_isolation(all_edges)
    all_errors.extend(errs)
    
    errs = validate_daily_cap(all_edges, max_daily)
    all_errors.extend(errs)
    
    passed = len(all_errors) == 0
    
    summary = {
        "validated_at": datetime.utcnow().isoformat() + "Z",
        "passed": passed,
        "error_count": len(all_errors),
        "engines_checked": len(engines_data),
        "edges_checked": len(all_edges) + len(all_blocked),
        "playable_count": len([e for e in all_edges if e.get("tier") in ("STRONG", "LEAN")]),
        "blocked_count": len(all_blocked),
    }
    
    return passed, all_errors, summary


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Tennis Output Validator (HARD GATE)")
    parser.add_argument("--edges", required=True, help="Path to edges JSON file")
    parser.add_argument("--merged", action="store_true", help="Input is merged multi-engine output")
    parser.add_argument("--output", help="Write validation result to JSON")
    
    args = parser.parse_args()
    
    edges_path = Path(args.edges)
    if not edges_path.exists():
        print(f"❌ GATE FAIL: File not found: {edges_path}")
        return 1
    
    data = json.loads(edges_path.read_text(encoding="utf-8"))
    
    if args.merged:
        passed, errors, summary = validate_merged_output(data)
    else:
        passed, errors, summary = validate_tennis_output(data)
    
    # Output
    result = {
        "input_file": str(edges_path),
        "summary": summary,
        "errors": errors,
    }
    
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    # Print summary
    print(f"\n{'='*60}")
    print("TENNIS VALIDATION GATE")
    print(f"{'='*60}")
    print(f"Input: {edges_path}")
    print(f"Edges checked: {summary['edges_checked']}")
    print(f"Playable: {summary['playable_count']} | Blocked: {summary['blocked_count']}")
    print(f"Errors: {summary['error_count']}")
    
    if passed:
        print("\n✅ GATE PASSED")
        return 0
    else:
        print("\n❌ GATE FAILED")
        print("\nErrors:")
        for err in errors[:20]:  # Cap output
            print(f"  • {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
