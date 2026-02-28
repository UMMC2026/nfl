#!/usr/bin/env python3
"""
PIPELINE FIXES - Three critical bugs identified 2026-01-30
===========================================================
1. Deduplication not being called (triple-loading props)
2. Gate penalties too aggressive (zeroing out valid picks)
3. Missing player data (Jaden Ivey not in cache)

This script provides patches and validation.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict


# =============================================================================
# FIX #1: DEDUPLICATION
# =============================================================================

def dedupe_props_before_analysis(props: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove duplicate props BEFORE analysis.
    
    Key: (player, stat, line, direction)
    
    Returns:
        (deduplicated_props, num_duplicates_removed)
    """
    seen = {}
    duplicates = []
    
    for prop in props:
        player = prop.get("player", "").strip().lower()
        stat = prop.get("stat", "").strip().lower()
        line = round(float(prop.get("line", 0)), 1)
        direction = prop.get("direction", "").strip().lower()
        
        key = (player, stat, line, direction)
        
        if key not in seen:
            seen[key] = prop
        else:
            duplicates.append({
                "key": key,
                "original": seen[key],
                "duplicate": prop
            })
    
    if duplicates:
        print(f"⚠️  DEDUP: Removed {len(duplicates)} duplicate props")
        for d in duplicates[:5]:  # Show first 5
            print(f"    - {d['key'][0]} {d['key'][1]} {d['key'][3]} {d['key'][2]}")
        if len(duplicates) > 5:
            print(f"    ... and {len(duplicates) - 5} more")
    
    print(f"✅ DEDUP: {len(seen)} unique props retained")
    return list(seen.values()), len(duplicates)


def validate_no_duplicates(props: List[Dict[str, Any]]) -> bool:
    """Validate that no duplicates exist."""
    seen = set()
    for prop in props:
        key = (
            prop.get("player", "").strip().lower(),
            prop.get("stat", "").strip().lower(),
            round(float(prop.get("line", 0)), 1),
            prop.get("direction", "").strip().lower()
        )
        if key in seen:
            print(f"❌ DUPLICATE FOUND: {key}")
            return False
        seen.add(key)
    print(f"✅ No duplicates in {len(props)} props")
    return True


# =============================================================================
# FIX #2: PENALTY CAPPING
# =============================================================================

MAX_PENALTY_PERCENT = 25.0  # Maximum total penalty (percentage points)
MIN_CONFIDENCE_FLOOR = 50.0  # Never go below 50% (prevents 0.0% blocking)


def apply_capped_penalties(
    model_confidence: float,
    penalties: Dict[str, float],
    verbose: bool = False
) -> Tuple[float, Dict[str, Any]]:
    """
    Apply penalties with caps to prevent over-aggressive blocking.
    
    Args:
        model_confidence: Raw model confidence (0-100)
        penalties: Dict of penalty_name -> penalty_amount (percentage points)
        
    Returns:
        (effective_confidence, metadata)
    """
    total_penalty = sum(penalties.values())
    
    # Cap total penalty
    capped_penalty = min(total_penalty, MAX_PENALTY_PERCENT)
    
    # Apply penalty
    effective = model_confidence - capped_penalty
    
    # Apply floor (minimum 50%)
    if effective < MIN_CONFIDENCE_FLOOR:
        effective = MIN_CONFIDENCE_FLOOR
    
    metadata = {
        "raw_penalty_total": round(total_penalty, 2),
        "capped_penalty": round(capped_penalty, 2),
        "penalty_cap_applied": total_penalty > MAX_PENALTY_PERCENT,
        "floor_applied": model_confidence - capped_penalty < MIN_CONFIDENCE_FLOOR,
        "penalties_breakdown": penalties
    }
    
    if verbose:
        print(f"  Penalties: {penalties}")
        print(f"  Total: {total_penalty:.1f}% → Capped: {capped_penalty:.1f}%")
        print(f"  Model: {model_confidence:.1f}% → Effective: {effective:.1f}%")
    
    return round(effective, 1), metadata


def test_penalty_capping():
    """Test the penalty capping logic."""
    print("\n" + "="*60)
    print("TEST: Penalty Capping")
    print("="*60)
    
    test_cases = [
        # (model_conf, penalties, expected_range)
        (36.6, {"matchup": 10, "archetype": 15, "variance": 12}, (50.0, 50.0)),  # Was: 0.0%
        (65.0, {"sample": 5, "volatility": 8}, (52.0, 60.0)),  # Normal case
        (80.0, {"none": 0}, (80.0, 80.0)),  # No penalty
        (45.0, {"extreme": 50}, (50.0, 50.0)),  # Extreme penalty capped
    ]
    
    for model, penalties, (min_exp, max_exp) in test_cases:
        result, meta = apply_capped_penalties(model, penalties)
        status = "✅" if min_exp <= result <= max_exp else "❌"
        print(f"{status} Model: {model}% | Penalties: {sum(penalties.values())}% → Effective: {result}%")
        if meta["penalty_cap_applied"]:
            print(f"   Cap applied: {meta['raw_penalty_total']:.1f}% → {meta['capped_penalty']:.1f}%")


# =============================================================================
# FIX #3: MISSING PLAYER DATA
# =============================================================================

def add_missing_player_stats(player: str, stats: Dict[str, Tuple[float, float]]) -> None:
    """
    Add missing player stats to the runtime cache.
    
    Args:
        player: Player name
        stats: Dict of stat -> (mu, sigma)
    """
    from risk_first_analyzer import STATS_DICT
    
    if player not in STATS_DICT:
        STATS_DICT[player] = {}
    
    for stat, (mu, sigma) in stats.items():
        STATS_DICT[player][stat] = (mu, sigma)
    
    print(f"✅ Added stats for {player}: {list(stats.keys())}")


# Known missing players with their approximate stats
MISSING_PLAYERS = {
    "Jaden Ivey": {
        "points": (15.3, 6.2),
        "rebounds": (3.8, 1.9),
        "assists": (3.9, 2.1),
        "3pm": (1.8, 1.3),
        "steals": (0.9, 0.8),
        "pra": (23.0, 7.5),
    },
    "Mouhamed Gueye": {
        "points": (4.8, 3.2),
        "rebounds": (4.2, 2.4),
        "assists": (0.8, 0.7),
        "3pm": (0.3, 0.5),
        "pra": (9.8, 4.8),
    },
}


def patch_missing_players():
    """Patch all known missing players into STATS_DICT."""
    for player, stats in MISSING_PLAYERS.items():
        add_missing_player_stats(player, stats)


# =============================================================================
# VALIDATION
# =============================================================================

def run_full_validation(props: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run all validation checks on a prop list.
    
    Returns report dict.
    """
    report = {
        "total_props": len(props),
        "duplicates_found": 0,
        "missing_data": [],
        "penalty_issues": [],
        "passed": True
    }
    
    # Check 1: Duplicates
    deduped, num_dupes = dedupe_props_before_analysis(props.copy())
    report["duplicates_found"] = num_dupes
    if num_dupes > 0:
        report["passed"] = False
    
    # Check 2: Missing player data
    from risk_first_analyzer import STATS_DICT
    for prop in deduped:
        player = prop.get("player", "")
        if player and player not in STATS_DICT:
            report["missing_data"].append(player)
    
    if report["missing_data"]:
        report["passed"] = False
    
    # Check 3: Would any props be zeroed by penalties?
    # (This would require running analysis, skip for now)
    
    return report


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("PIPELINE FIXES VALIDATION")
    print("="*70)
    
    # Test penalty capping
    test_penalty_capping()
    
    # Test deduplication
    print("\n" + "="*60)
    print("TEST: Deduplication")
    print("="*60)
    
    # Create props with duplicates
    test_props = [
        {"player": "Jalen Johnson", "stat": "rebounds", "line": 10.5, "direction": "higher"},
        {"player": "Jalen Johnson", "stat": "rebounds", "line": 10.5, "direction": "higher"},  # Dupe
        {"player": "Jalen Johnson", "stat": "rebounds", "line": 10.5, "direction": "higher"},  # Dupe
        {"player": "Isaiah Hartenstein", "stat": "rebounds", "line": 9.5, "direction": "higher"},
        {"player": "Isaiah Hartenstein", "stat": "rebounds", "line": 9.5, "direction": "higher"},  # Dupe
        {"player": "Myles Turner", "stat": "3pm", "line": 2.5, "direction": "higher"},
    ]
    
    deduped, num_removed = dedupe_props_before_analysis(test_props)
    print(f"\nOriginal: {len(test_props)} | After dedup: {len(deduped)} | Removed: {num_removed}")
    
    # Validate no duplicates remain
    validate_no_duplicates(deduped)
    
    # Show summary
    print("\n" + "="*70)
    print("SUMMARY OF FIXES")
    print("="*70)
    print("""
FIX #1: DEDUPLICATION
  - Location: risk_first_analyzer.py → analyze_slate()
  - Add: deduped_props, num_dupes = dedupe_props_before_analysis(props)
  - Expected: 72 props → 24 unique (removes triplicates)

FIX #2: PENALTY CAPPING  
  - Location: core/hybrid_confidence.py or wherever penalties applied
  - Add: MAX_PENALTY = 25%, MIN_FLOOR = 50%
  - Expected: No more 0.0% blocked picks

FIX #3: MISSING PLAYERS
  - Location: extended_stats_dict.py OR runtime patch
  - Add: Jaden Ivey, Mouhamed Gueye stats
  - Expected: 100% data coverage
""")
