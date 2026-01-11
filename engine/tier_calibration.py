"""
Phase 3 - Confidence Tier Calibration

Policy layer on top of probabilities.
Tiers = capital allocation decision, not prediction.
"""
from collections import Counter


# Tier policy (IMMUTABLE)
TIER_POLICY = {
    "SLAM": {
        "prob_min": 0.75,
        "sample_min": 25,
        "requires_bias_free": True,
        "requires_pace_alignment": True,
        "max_share": 0.15  # Max 15% of picks can be SLAM
    },
    "STRONG": {
        "prob_min": 0.65,
        "sample_min": 20,
        "requires_bias_free": True,
        "requires_pace_alignment": True,
        "max_share": 0.30  # Max 30% of picks can be STRONG
    },
    "LEAN": {
        "prob_min": 0.55,
        "sample_min": 15,
        "requires_bias_free": False,
        "requires_pace_alignment": False,
        "max_share": 0.50  # Max 50% of picks can be LEAN
    }
}


def tier_eligible(pick: dict, bias_report: dict = None) -> tuple[bool, str]:
    """
    Check if pick meets minimum eligibility for tiering.
    
    Args:
        pick: Scored pick with probability and context
        bias_report: Optional bias report for bias-free requirement
    
    Returns:
        (is_eligible, reason)
    """
    # Sample size check
    if "prob_method" in pick:
        sample_size = pick["prob_method"].get("sample_size", 0)
    else:
        sample_size = pick.get("sample_size", 0)
    
    if sample_size < 15:
        return False, f"Insufficient sample (n={sample_size}, min=15)"
    
    # Bias check (if report provided)
    if bias_report and bias_report.get("bias_detected"):
        # Only block if bias is HIGH or CRITICAL
        if bias_report.get("severity") in ("HIGH", "CRITICAL"):
            return False, f"Bias detected ({bias_report['severity']})"
    
    # Edge check - avoid coin flips
    if "pace_context" in pick and pick["pace_context"].get("pace_data_available"):
        pace_mean = pick["pace_context"]["pace_adjusted_mean"]
        line = pick.get("line")
        if line and abs(pace_mean - line) < 0.5:
            return False, "Projection too close to line (coin flip)"
    
    return True, "Eligible"


def assign_calibrated_tier(pick: dict, bias_report: dict = None) -> str:
    """
    Assign tier based on strict calibration policy.
    
    Args:
        pick: Scored pick with probability
        bias_report: Optional bias report for requirements
    
    Returns:
        Tier string: "SLAM", "STRONG", "LEAN", or "NO PLAY"
    """
    # Check eligibility first
    eligible, reason = tier_eligible(pick, bias_report)
    if not eligible:
        return "NO PLAY"
    
    prob = pick.get("probability", 0)
    
    # Extract sample size
    if "prob_method" in pick:
        sample_size = pick["prob_method"].get("sample_size", 0)
    else:
        sample_size = pick.get("sample_size", 0)
    
    # Extract bias-free status
    bias_free = True
    if bias_report:
        bias_free = not bias_report.get("bias_detected") or bias_report.get("severity") == "NORMAL"
    
    # Extract pace alignment
    pace_aligned = False
    if "pace_context" in pick and pick["pace_context"].get("pace_data_available"):
        pace_mean = pick["pace_context"]["pace_adjusted_mean"]
        line = pick.get("line")
        direction = str(pick.get("direction", "")).lower()
        
        if direction in ("over", "higher", "o", "h"):
            pace_aligned = pace_mean > line
        else:
            pace_aligned = pace_mean < line
    
    # Check SLAM requirements
    slam_policy = TIER_POLICY["SLAM"]
    if (prob >= slam_policy["prob_min"] and
        sample_size >= slam_policy["sample_min"] and
        (not slam_policy["requires_bias_free"] or bias_free) and
        (not slam_policy["requires_pace_alignment"] or pace_aligned)):
        return "SLAM"
    
    # Check STRONG requirements
    strong_policy = TIER_POLICY["STRONG"]
    if (prob >= strong_policy["prob_min"] and
        sample_size >= strong_policy["sample_min"] and
        (not strong_policy["requires_bias_free"] or bias_free) and
        (not strong_policy["requires_pace_alignment"] or pace_aligned)):
        return "STRONG"
    
    # Check LEAN requirements
    lean_policy = TIER_POLICY["LEAN"]
    if (prob >= lean_policy["prob_min"] and
        sample_size >= lean_policy["sample_min"]):
        return "LEAN"
    
    return "NO PLAY"


def compress_tiers(picks: list) -> list:
    """
    Apply tier compression if too many picks in top tiers.
    
    Markets do not offer 40% SLAM days - that's hallucination.
    
    Args:
        picks: List of tiered picks
    
    Returns:
        List of picks with compressed tiers
    """
    total = len(picks)
    if total == 0:
        return picks
    
    tier_counts = Counter(p.get("confidence_tier") for p in picks)
    
    # Check SLAM overflow
    slam_share = tier_counts.get("SLAM", 0) / total
    if slam_share > TIER_POLICY["SLAM"]["max_share"]:
        # Downgrade excess SLAMs to STRONG
        excess = int(tier_counts["SLAM"] - total * TIER_POLICY["SLAM"]["max_share"])
        downgraded = 0
        
        for p in sorted(picks, key=lambda x: x.get("probability", 0)):
            if p.get("confidence_tier") == "SLAM" and downgraded < excess:
                p["confidence_tier"] = "STRONG"
                p["tier_compressed"] = True
                downgraded += 1
    
    # Recount after SLAM compression
    tier_counts = Counter(p.get("confidence_tier") for p in picks)
    
    # Check STRONG overflow
    strong_share = tier_counts.get("STRONG", 0) / total
    if strong_share > TIER_POLICY["STRONG"]["max_share"]:
        excess = int(tier_counts["STRONG"] - total * TIER_POLICY["STRONG"]["max_share"])
        downgraded = 0
        
        for p in sorted(picks, key=lambda x: x.get("probability", 0)):
            if p.get("confidence_tier") == "STRONG" and downgraded < excess:
                p["confidence_tier"] = "LEAN"
                p["tier_compressed"] = True
                downgraded += 1
    
    return picks


def add_tier_rationale(pick: dict, bias_report: dict = None) -> dict:
    """
    Add tier decision audit trail to pick.
    
    Args:
        pick: Pick with assigned tier
        bias_report: Bias report for context
    
    Returns:
        Pick with tier_decision field added
    """
    sample_size = 0
    if "prob_method" in pick:
        sample_size = pick["prob_method"].get("sample_size", 0)
    
    pace_line_delta = None
    if "pace_context" in pick and pick["pace_context"].get("pace_data_available"):
        pace_mean = pick["pace_context"]["pace_adjusted_mean"]
        line = pick.get("line")
        if line:
            pace_line_delta = round(pace_mean - line, 2)
    
    bias_free = True
    if bias_report:
        bias_free = not bias_report.get("bias_detected") or bias_report.get("severity") == "NORMAL"
    
    pick["tier_decision"] = {
        "assigned_tier": pick.get("confidence_tier"),
        "probability": pick.get("probability"),
        "empirical_sample_size": sample_size,
        "pace_line_delta": pace_line_delta,
        "bias_free": bias_free,
        "tier_compressed": pick.get("tier_compressed", False),
        "tier_policy_version": "v1.0"
    }
    
    return pick
