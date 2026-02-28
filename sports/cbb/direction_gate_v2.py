"""
DIRECTION GATE v2.0 — Graduated Filter (replaces hard abort)
============================================================
Replaces the binary ABORT gate with a graduated response that:
  - Preserves individual picks with genuine edges
  - Compresses confidence on majority-direction picks when skew is high
  - Always passes counter-direction picks (they're MORE trustworthy under skew)
  - Only hard-filters at extreme skew (>80%), and even then keeps SLAM/STRONG

Drop-in replacement for apply_direction_gate() in your CBB pipeline.

RATIONALE:
----------
The old gate treated 75% OVER skew as binary: either the model is broken (abort)
or it's fine (pass). This kills valid individual edges because of portfolio stats.

Reality is nuanced:
- 75% skew CAN mean model miscalibration (lines are fair, model is biased)
- 75% skew CAN ALSO mean tonight's slate genuinely has more OVER value
- Counter-direction picks are CONTRARIAN SIGNALS — more trustworthy under skew

The graduated gate:
1. Compresses confidence on majority picks (accounts for possible bias)
2. Passes minority picks untouched (they fought through the bias)
3. Only hard-filters at extreme skew (>80%), keeping SLAM/STRONG
"""

from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def apply_direction_gate_v2(
    edges: List[Dict],
    context: Optional[Dict] = None,
    warn_threshold: float = 0.65,
    hard_threshold: float = 0.80,
    confidence_penalty: float = 0.05,
) -> Tuple[List[Dict], Dict]:
    """
    Graduated direction gate — replaces binary abort.
    
    Args:
        edges: List of edge dictionaries
        context: Optional context (unused, for interface compatibility)
        warn_threshold: Skew level to trigger confidence compression (default 65%)
        hard_threshold: Skew level to trigger hard filtering (default 80%)
        confidence_penalty: Amount to subtract from majority picks under WARNING (default 5%)
    
    Returns:
        (filtered_edges, gate_report)
        
    Gate report contains:
        - status: "PASS" | "WARNING" | "HARD_FILTER" | "EMPTY"
        - skew: Directional imbalance ratio
        - action: Human-readable description of what happened
        - surviving: Count of picks that passed
    """
    if not edges:
        return edges, {"status": "EMPTY", "skew": 0.0}

    # --- Count directional balance ---
    over_count = sum(1 for e in edges if e.get("direction", "").upper() in ("OVER", "HIGHER"))
    under_count = sum(1 for e in edges if e.get("direction", "").upper() in ("UNDER", "LOWER"))
    total = over_count + under_count

    if total == 0:
        return edges, {"status": "NO_DIRECTIONAL", "skew": 0.0}

    # Determine majority direction
    if over_count >= under_count:
        majority_dir = "OVER"
        majority_count = over_count
    else:
        majority_dir = "UNDER"
        majority_count = under_count

    skew = majority_count / total
    minority_dir = "UNDER" if majority_dir == "OVER" else "OVER"

    # --- Build gate report ---
    report = {
        "majority_direction": majority_dir,
        "skew": round(skew, 3),
        "over_count": over_count,
        "under_count": under_count,
        "total": total,
    }

    # ============================================================
    # ZONE 1: Normal (skew < warn_threshold)
    # All picks pass, no modifications
    # ============================================================
    if skew < warn_threshold:
        report["status"] = "PASS"
        report["action"] = "No modifications"
        logger.info(f"Direction Gate v2: PASS (skew {skew:.1%} {majority_dir})")
        return edges, report

    # ============================================================
    # ZONE 2: Warning (warn_threshold <= skew < hard_threshold)
    # - Majority-direction picks: compress confidence by penalty
    # - Minority-direction picks: pass untouched (more trustworthy)
    # - Nothing is removed unless compression pushes below NO PLAY floor
    # ============================================================
    if skew < hard_threshold:
        report["status"] = "WARNING"
        report["action"] = f"Compressing {majority_dir} confidence by {confidence_penalty:.0%}"
        logger.warning(f"Direction Gate v2: WARNING (skew {skew:.1%} {majority_dir}) — compressing majority picks")

        adjusted = []
        compressed_count = 0
        killed_by_compression = 0
        
        for edge in edges:
            edge_dir = edge.get("direction", "").upper()
            # Normalize direction names
            is_majority = edge_dir in (
                ("OVER", "HIGHER") if majority_dir == "OVER" else ("UNDER", "LOWER")
            )

            if is_majority:
                # Compress confidence on majority-direction picks
                new_edge = edge.copy()
                old_conf = new_edge.get("confidence", new_edge.get("probability", 0.5))
                new_conf = max(old_conf - confidence_penalty, 0.50)
                new_edge["confidence"] = round(new_conf, 4)
                new_edge["probability"] = round(new_conf, 4)
                new_edge["direction_gate_flag"] = "COMPRESSED"

                # Re-check tier after compression
                new_edge["tier"] = _assign_tier(new_conf)

                # If compression pushed it below NO PLAY floor (55%), drop it
                if new_conf < 0.55:
                    new_edge["direction_gate_flag"] = "KILLED_BY_COMPRESSION"
                    killed_by_compression += 1
                    continue  # Skip this pick

                adjusted.append(new_edge)
                compressed_count += 1
            else:
                # Minority-direction picks pass untouched
                edge_copy = edge.copy()
                edge_copy["direction_gate_flag"] = "COUNTER_DIRECTION_PASS"
                adjusted.append(edge_copy)

        report["compressed"] = compressed_count
        report["killed_by_compression"] = killed_by_compression
        report["surviving"] = len(adjusted)
        logger.info(f"Direction Gate v2: {len(adjusted)} picks survived ({compressed_count} compressed, {killed_by_compression} killed)")
        return adjusted, report

    # ZONE 3: Hard Filter (skew >= hard_threshold)
    # - Majority-direction: apply HEAVIER compression (2× penalty)
    #   then keep only picks that remain above the LEAN floor (60%).
    #   SLAM/STRONG picks get the penalty but always survive.
    # - Minority-direction: ALL pass (they're contrarian value)
    #
    # NOTE: The old behaviour killed ALL majority LEAN picks outright,
    # which nuked the entire slate when the platform only offers one
    # direction (e.g. Underdog CBB showing only "higher" lines).
    # A 100% skew is expected in that scenario — not miscalibration.
    # The graduated compression preserves genuine edges while still
    # penalising for the extreme directional bias.
    # ============================================================
    report["status"] = "HARD_FILTER"
    heavy_penalty = confidence_penalty * 1.5  # 7.5% for default 5% base
    report["action"] = (
        f"Heavy compression on {majority_dir} picks (-{heavy_penalty:.0%}); "
        f"SLAM/STRONG always survive; LEAN kept if still ≥60%"
    )
    logger.critical(f"Direction Gate v2: HARD_FILTER (skew {skew:.1%} {majority_dir}) — extreme bias detected")

    filtered = []
    killed_count = 0
    high_conf_survivors = 0
    compressed_survivors = 0
    
    for edge in edges:
        edge_dir = edge.get("direction", "").upper()
        is_majority = edge_dir in (
            ("OVER", "HIGHER") if majority_dir == "OVER" else ("UNDER", "LOWER")
        )

        if is_majority:
            conf = edge.get("confidence", edge.get("probability", 0.5))
            tier = _assign_tier(conf)

            # Apply heavier compression
            new_edge = edge.copy()
            new_conf = max(conf - heavy_penalty, 0.50)
            new_edge["confidence"] = round(new_conf, 4)
            new_edge["probability"] = round(new_conf, 4)
            new_edge["tier"] = _assign_tier(new_conf)

            if tier in ("SLAM", "STRONG"):
                # High-confidence majority picks always survive (compressed)
                new_edge["direction_gate_flag"] = "HIGH_SKEW_SURVIVOR"
                filtered.append(new_edge)
                high_conf_survivors += 1
            elif new_conf >= 0.60:
                # LEAN picks survive if still above floor after heavy compression
                new_edge["direction_gate_flag"] = "HEAVY_COMPRESSED_SURVIVOR"
                filtered.append(new_edge)
                compressed_survivors += 1
            else:
                # Fell below floor — killed
                killed_count += 1
        else:
            # All minority-direction picks pass
            edge_copy = edge.copy()
            edge_copy["direction_gate_flag"] = "COUNTER_DIRECTION_PASS"
            filtered.append(edge_copy)

    report["killed"] = killed_count
    report["high_conf_survivors"] = high_conf_survivors
    report["compressed_survivors"] = compressed_survivors
    report["surviving"] = len(filtered)
    logger.warning(f"Direction Gate v2: {len(filtered)} picks survived ({killed_count} majority LEAN killed)")
    return filtered, report


def _assign_tier(confidence: float) -> str:
    """
    Assign tier based on confidence level.
    
    Uses CBB-specific thresholds from config/thresholds.py:
    - SLAM: None (disabled for CBB)
    - STRONG: 70%+
    - LEAN: 60-70%
    - NO_PLAY: <60%
    """
    # CBB thresholds (stricter than NBA)
    if confidence >= 0.70:
        return "STRONG"
    elif confidence >= 0.60:
        return "LEAN"
    else:
        return "NO_PLAY"


# ============================================================
# INTEGRATION EXAMPLE
# ============================================================
# In your cbb_main.py, replace:
#
#   from sports.cbb.direction_gate import apply_direction_gate
#   edges = apply_direction_gate(edges, context={})
#
# With:
#
#   from sports.cbb.direction_gate_v2 import apply_direction_gate_v2
#   edges, gate_report = apply_direction_gate_v2(edges)
#   print(f"  ✓ Direction Gate v2: {gate_report['status']} "
#         f"(skew: {gate_report['skew']:.1%} {gate_report.get('majority_direction', 'N/A')})")
#   if gate_report['status'] != 'PASS':
#       print(f"    Action: {gate_report['action']}")
#       print(f"    Surviving: {gate_report.get('surviving', len(edges))}")
#


# ============================================================
# QUICK TEST
# ============================================================
if __name__ == "__main__":
    # Simulate tonight's CBB slate: 72 OVER, 24 UNDER out of 96
    test_edges = []
    for i in range(72):
        test_edges.append({
            "player": f"Player_OVER_{i}",
            "direction": "OVER",
            "confidence": 0.58 + (i % 20) * 0.01,  # Range 0.58-0.77
            "probability": 0.58 + (i % 20) * 0.01,
            "stat": "points",
        })
    for i in range(24):
        test_edges.append({
            "player": f"Player_UNDER_{i}",
            "direction": "UNDER",
            "confidence": 0.60 + (i % 15) * 0.01,  # Range 0.60-0.74
            "probability": 0.60 + (i % 15) * 0.01,
            "stat": "points",
        })

    print("=" * 60)
    print("TEST: 72 OVER / 24 UNDER (75% skew)")
    print("=" * 60)

    result, report = apply_direction_gate_v2(test_edges)

    print(f"\nGate Status:  {report['status']}")
    print(f"Skew:         {report['skew']:.1%} {report['majority_direction']}")
    print(f"Action:       {report['action']}")
    print(f"Input:        {report['total']} edges")
    print(f"Surviving:    {report.get('surviving', len(result))} edges")

    # Show what survived
    over_survived = sum(1 for e in result if e["direction"] == "OVER")
    under_survived = sum(1 for e in result if e["direction"] == "UNDER")
    print(f"\nSurvivors:    {over_survived} OVER + {under_survived} UNDER")

    # Show tier breakdown
    tiers = {}
    for e in result:
        t = e.get("tier", _assign_tier(e["confidence"]))
        tiers[t] = tiers.get(t, 0) + 1
    print(f"Tier breakdown: {tiers}")

    print(f"\nFlags:")
    flags = {}
    for e in result:
        f = e.get("direction_gate_flag", "NONE")
        flags[f] = flags.get(f, 0) + 1
    for flag, count in sorted(flags.items()):
        print(f"  {flag}: {count}")
