#!/usr/bin/env python3
"""
SOP v2.1 Render Gate Validator
Enforces hard constraints before any report is generated.
FAIL-FAST: raises SystemExit(1) on any violation.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

TIER_CONFIDENCE_MAP = {
    "SLAM": (0.75, 1.00),
    "STRONG": (0.65, 0.74),
    "LEAN": (0.55, 0.64),
    "NO_PLAY": (0.00, 0.54),
}

STAT_MAP = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "pts+reb+ast": "pra",
    "pra": "pra",
    "pts+reb": "points+rebounds",
    "pts+ast": "points+assists",
}


# ============================================================================
# VALIDATORS
# ============================================================================

def load_json(path: Path):
    """Load JSON file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def detect_duplicate_edges(picks: List[Dict]) -> List[Dict]:
    """Detect multiple lines for the same (player, stat, direction)."""
    groups = defaultdict(list)
    for idx, p in enumerate(picks):
        key = (p.get("player_name", p.get("player")), 
               p.get("prop_type", p.get("stat")), 
               p.get("direction"))
        groups[key].append((idx, p))
    
    violations = []
    for key, items in groups.items():
        if len(items) > 1:
            violations.append({
                "edge": key,
                "count": len(items),
                "lines": [it[1].get("line") for it in items],
                "indices": [it[0] for it in items],
            })
    return violations


def detect_outlier_lines(picks: List[Dict], gt: Dict, factor: float = 2.5) -> List[Dict]:
    """
    Flag lines that deviate excessively from official averages.
    Rule: if line > avg × factor, flag as outlier.
    """
    players = gt.get("players", {})
    outliers = []
    
    for p in picks:
        player = p.get("player_name", p.get("player", ""))
        stat = p.get("prop_type", p.get("stat", ""))
        line = p.get("line")
        
        if not player or not stat or line is None:
            continue
        
        if player not in players:
            continue
        
        stat_key = STAT_MAP.get(stat)
        if not stat_key:
            continue
        
        avg = players[player].get(stat_key)
        if avg is None or avg <= 0:
            continue
        
        if line > avg * factor:
            outliers.append({
                "player": player,
                "stat": stat,
                "line": line,
                "avg": avg,
                "ratio": line / avg if avg > 0 else 0,
            })
    
    return outliers


def detect_duplicate_players_as_primary(picks: List[Dict]) -> List[Dict]:
    """Rule B1: Ensure each (player, game_id) has max 1 PRIMARY bet."""
    seen = {}
    violations = []
    
    for idx, p in enumerate(picks):
        correlation = p.get("correlation_tag", "PRIMARY")
        if correlation != "PRIMARY":
            continue
        
        player = p.get("player_name", p.get("player", ""))
        game_id = p.get("game_id", "")
        pk = (player, game_id)
        
        if pk in seen:
            violations.append({
                "player": player,
                "game_id": game_id,
                "indices": [seen[pk], idx],
            })
        else:
            seen[pk] = idx
    
    return violations


def detect_correlated_in_tiers(picks: List[Dict]) -> List[Dict]:
    """Rule B2: Ensure CORRELATED picks are never in tier sections."""
    violations = []
    
    for idx, p in enumerate(picks):
        correlation = p.get("correlation_tag", "PRIMARY")
        tier = p.get("tier", "")
        
        if correlation == "CORRELATED" and tier in ["SLAM", "STRONG", "LEAN"]:
            violations.append({
                "player": p.get("player_name", p.get("player")),
                "tier": tier,
                "index": idx,
            })
    
    return violations


def check_tier_confidence_alignment(picks: List[Dict]) -> List[Dict]:
    """Rule C2: Ensure tier labels match probability ranges."""
    mismatches = []
    
    for idx, p in enumerate(picks):
        correlation = p.get("correlation_tag", "PRIMARY")
        if correlation == "CORRELATED":
            continue
        
        tier = p.get("tier", "")
        confidence = p.get("confidence", 0.0)
        
        if not tier or tier not in TIER_CONFIDENCE_MAP:
            continue
        
        min_conf, max_conf = TIER_CONFIDENCE_MAP[tier]
        if not (min_conf <= confidence <= max_conf):
            mismatches.append({
                "player": p.get("player_name", p.get("player")),
                "tier": tier,
                "confidence": confidence,
                "expected_range": f"{min_conf*100:.0f}%-{max_conf*100:.0f}%",
                "index": idx,
            })
    
    return mismatches


def main():
    """Run all SOP v2.1 validation checks."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate picks against SOP v2.1 (truth-enforced)")
    parser.add_argument("--picks", default="picks.json", help="Path to picks JSON")
    parser.add_argument(
        "--ground-truth",
        default="outputs/ground_truth_official.json",
        help="Path to ground truth averages JSON",
    )
    args = parser.parse_args()

    picks_path = Path(args.picks)
    gt_path = Path(args.ground_truth)

    if not picks_path.exists():
        print(f"❌ ERROR: picks file not found: {picks_path}")
        sys.exit(1)
    if not gt_path.exists():
        print(f"❌ ERROR: ground truth file not found: {gt_path}")
        sys.exit(1)

    picks = load_json(picks_path)
    if not isinstance(picks, list):
        picks = [picks]
    
    gt = load_json(gt_path)

    print("\n" + "="*80)
    print("RENDER GATE VALIDATION (SOP v2.1)")
    print("="*80 + "\n")

    # Run checks
    duplicate_edges = detect_duplicate_edges(picks)
    outlier_lines = detect_outlier_lines(picks, gt)
    dup_players = detect_duplicate_players_as_primary(picks)
    corr_in_tiers = detect_correlated_in_tiers(picks)
    tier_mismatches = check_tier_confidence_alignment(picks)

    # Report
    all_pass = all(x == [] for x in [duplicate_edges, outlier_lines, dup_players, corr_in_tiers, tier_mismatches])

    print(f"Check: No Duplicate EDGES (A2)           {'✅ PASS' if not duplicate_edges else f'❌ FAIL ({len(duplicate_edges)})'}")
    print(f"Check: No Outlier Lines (Rule A3)        {'✅ PASS' if not outlier_lines else f'❌ FAIL ({len(outlier_lines)})'}")
    print(f"Check: One Player, One PRIMARY (B1)      {'✅ PASS' if not dup_players else f'❌ FAIL ({len(dup_players)})'}")
    print(f"Check: CORRELATED Excluded From Tiers (B2) {'✅ PASS' if not corr_in_tiers else f'❌ FAIL ({len(corr_in_tiers)})'}")
    print(f"Check: Tier ↔ Confidence Alignment (C2)  {'✅ PASS' if not tier_mismatches else f'❌ FAIL ({len(tier_mismatches)})'}")

    if duplicate_edges:
        print(f"\n🔴 Duplicate EDGES (first 5):")
        for v in duplicate_edges[:5]:
            print(f"   {v['edge']} → lines: {v['lines']}")
        if len(duplicate_edges) > 5:
            print(f"   ... and {len(duplicate_edges) - 5} more")

    if outlier_lines:
        print(f"\n🔴 Outlier Lines (first 5):")
        for o in outlier_lines[:5]:
            print(f"   {o['player']} {o['stat']} line={o['line']} avg={o['avg']:.1f} (ratio={o['ratio']:.2f}x)")
        if len(outlier_lines) > 5:
            print(f"   ... and {len(outlier_lines) - 5} more")

    if dup_players:
        print(f"\n🔴 Duplicate PRIMARY Per Player/Game (first 5):")
        for d in dup_players[:5]:
            print(f"   {d['player']} in game {d['game_id']} at indices {d['indices']}")
        if len(dup_players) > 5:
            print(f"   ... and {len(dup_players) - 5} more")

    if corr_in_tiers:
        print(f"\n🔴 CORRELATED in Tier (first 5):")
        for c in corr_in_tiers[:5]:
            print(f"   {c['player']} tier={c['tier']}")
        if len(corr_in_tiers) > 5:
            print(f"   ... and {len(corr_in_tiers) - 5} more")

    if tier_mismatches:
        print(f"\n🔴 Tier ↔ Confidence Mismatch (first 5):")
        for m in tier_mismatches[:5]:
            print(f"   {m['player']} tier={m['tier']} conf={m['confidence']*100:.0f}% expected={m['expected_range']}")
        if len(tier_mismatches) > 5:
            print(f"   ... and {len(tier_mismatches) - 5} more")

    print("\n" + "="*80)
    if all_pass:
        print("✅ ALL CHECKS PASSED — Safe to render.")
        print("="*80 + "\n")
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED — Fix violations before rendering.")
        print("="*80 + "\n")
        sys.exit(1)

