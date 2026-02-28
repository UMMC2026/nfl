"""
STAT DEVIATION GATE (SDG)
=========================
Pre-market filter that blocks/penalizes picks where expected outcome is 
too close to player's normal statistical state.

CONCEPT:
    z_stat = (E - μ_context) / σ
    
Where:
    E = Expected outcome today (projection)
    μ_context = Player's contextual mean (recent performance)
    σ = Player's volatility (standard deviation)

PURPOSE:
    - Block coin-flip bets (player expected to perform at baseline)
    - Prevent star-tax traps (market priced at expectation)
    - Filter variance masquerading as edge

DOES NOT CARE ABOUT THE PROP LINE - only player state quality.

INTEGRATION:
    Called BEFORE probability calculation in decision_governance.py
    Acts as input sanitation, not decision logic.
    
MODES:
    - Soft Gate (current): Penalties applied to raw probability
    - Hard Gate (future): Outright rejection below z_min

Reference: Quant Engineer recommendation 2026-02-01
"""

from typing import Dict, Tuple, Optional
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# SDG CONFIGURATION
# =============================================================================

SDG_CONFIG = {
    "enabled": True,
    "mode": "soft",  # "soft" = penalties, "hard" = rejection
    
    # Soft gate thresholds (multipliers applied to probability)
    "soft_thresholds": {
        "heavy_penalty_z": 0.25,   # |z_stat| < 0.25 → heavy penalty
        "medium_penalty_z": 0.50,  # |z_stat| < 0.50 → medium penalty
        "pass_z": 0.50,            # |z_stat| >= 0.50 → no penalty
    },
    
    # Penalty multipliers (applied to raw probability)
    # NOTE: 0.70 was too aggressive — crushed ALL props on small slates where
    # lines naturally sit near player means. Softened to 0.90/0.95 per 2026-02-09 audit.
    "soft_penalties": {
        "heavy": 0.90,   # 10% reduction (was 0.70 = 30%)
        "medium": 0.95,  # 5% reduction  (was 0.85 = 15%)
        "none": 1.00,    # No penalty
    },
    
    # Hard gate thresholds (future use)
    # Different stats have different z_min based on their variance profiles
    "hard_thresholds": {
        "default": 0.50,
        "pts": 0.60,
        "points": 0.60,
        "pra": 0.50,
        "pts+reb+ast": 0.50,
        "3pm": 0.80,
        "threes": 0.80,
        "reb": 0.50,
        "ast": 0.50,
    },
    
    # Stat-specific adjustments (some stats inherently cluster near mean)
    "stat_z_adjustments": {
        # Assists are naturally low-variance, require less deviation
        "ast": {"z_offset": -0.10, "reason": "low_variance_stat"},
        "assists": {"z_offset": -0.10, "reason": "low_variance_stat"},
        
        # 3PM is high-variance, require more deviation
        "3pm": {"z_offset": 0.10, "reason": "high_variance_stat"},
        "threes": {"z_offset": 0.10, "reason": "high_variance_stat"},
    },
}


# =============================================================================
# SDG CORE FUNCTION
# =============================================================================

def calculate_z_stat(
    mu_context: float,
    sigma: float,
    expected: float,
) -> Tuple[float, str]:
    """
    Calculate stat deviation z-score.
    
    Args:
        mu_context: Player's contextual mean (recent average)
        sigma: Player's volatility (standard deviation)
        expected: Expected outcome today
        
    Returns:
        (z_stat, description)
    """
    if sigma <= 0:
        logger.warning(f"SDG: sigma <= 0 ({sigma}), using 1.0")
        sigma = 1.0
    
    z_stat = (expected - mu_context) / sigma
    
    desc = f"z_stat={z_stat:+.3f} (E={expected:.1f}, μ={mu_context:.1f}, σ={sigma:.2f})"
    
    return z_stat, desc


def stat_deviation_gate(
    mu_context: float,
    sigma: float,
    expected: float,
    stat: str = "default",
    mode: str = "soft",
) -> Tuple[float, str, Dict]:
    """
    Apply Stat Deviation Gate.
    
    Args:
        mu_context: Player's contextual mean
        sigma: Player's volatility  
        expected: Expected outcome today
        stat: Stat type (for stat-specific thresholds)
        mode: "soft" (penalties) or "hard" (rejection)
        
    Returns:
        (multiplier, gate_result_description, details_dict)
        
    Example:
        mult, desc, details = stat_deviation_gate(29.5, 7.5, 29.8, "pts")
        # Returns (0.70, "HEAVY_PENALTY: z_stat=+0.04 below 0.25", {...})
    """
    if not SDG_CONFIG.get("enabled", True):
        return 1.0, "SDG_DISABLED", {"z_stat": 0, "penalty": "none"}
    
    # Calculate z_stat
    z_stat, z_desc = calculate_z_stat(mu_context, sigma, expected)
    abs_z = abs(z_stat)
    
    # Apply stat-specific z adjustment if configured
    stat_lower = stat.lower().strip()
    adjustment = SDG_CONFIG.get("stat_z_adjustments", {}).get(stat_lower, {})
    z_offset = adjustment.get("z_offset", 0)
    if z_offset:
        abs_z = abs_z + z_offset  # Positive offset = easier to pass
        z_desc += f" [adjusted by {z_offset:+.2f} for {stat_lower}]"
    
    # Initialize result
    details = {
        "z_stat": round(z_stat, 4),
        "abs_z_adjusted": round(abs_z, 4),
        "mu_context": mu_context,
        "sigma": sigma,
        "expected": expected,
        "stat": stat,
        "mode": mode,
    }
    
    if mode == "soft":
        # SOFT GATE: Apply penalties
        thresholds = SDG_CONFIG.get("soft_thresholds", {})
        penalties = SDG_CONFIG.get("soft_penalties", {})
        
        heavy_z = thresholds.get("heavy_penalty_z", 0.25)
        medium_z = thresholds.get("medium_penalty_z", 0.50)
        
        if abs_z < heavy_z:
            multiplier = penalties.get("heavy", 0.70)
            penalty_type = "heavy"
            result_desc = f"SDG_HEAVY_PENALTY: z_stat={z_stat:+.3f} < {heavy_z}"
        elif abs_z < medium_z:
            multiplier = penalties.get("medium", 0.85)
            penalty_type = "medium"
            result_desc = f"SDG_MEDIUM_PENALTY: z_stat={z_stat:+.3f} < {medium_z}"
        else:
            multiplier = penalties.get("none", 1.0)
            penalty_type = "none"
            result_desc = f"SDG_PASS: z_stat={z_stat:+.3f} >= {medium_z}"
        
        details["penalty"] = penalty_type
        details["multiplier"] = multiplier
        
        return multiplier, result_desc, details
    
    elif mode == "hard":
        # HARD GATE: Reject below z_min
        hard_thresholds = SDG_CONFIG.get("hard_thresholds", {})
        z_min = hard_thresholds.get(stat_lower, hard_thresholds.get("default", 0.50))
        
        if abs_z < z_min:
            # REJECT
            details["rejected"] = True
            details["z_min"] = z_min
            result_desc = f"SDG_REJECT: z_stat={z_stat:+.3f} < z_min={z_min}"
            return 0.0, result_desc, details  # 0.0 multiplier = rejected
        else:
            # PASS
            details["rejected"] = False
            details["z_min"] = z_min
            result_desc = f"SDG_PASS: z_stat={z_stat:+.3f} >= z_min={z_min}"
            return 1.0, result_desc, details
    
    else:
        logger.warning(f"SDG: Unknown mode '{mode}', defaulting to pass")
        return 1.0, "SDG_UNKNOWN_MODE", details


def apply_sdg_to_pick(pick: Dict, mode: str = "soft") -> Tuple[Dict, Dict]:
    """
    Apply SDG to a pick dictionary.
    
    Args:
        pick: Pick dict with mu, sigma, line fields
        mode: "soft" or "hard"
        
    Returns:
        (modified_pick, sdg_details)
        
    KEY INSIGHT:
        SDG measures how far the LINE deviates from player's contextual mean.
        If line ≈ mu, we're betting on a coin flip (low edge).
        
        For HIGHER bets: line below mu is good (negative z_stat)
        For LOWER bets: line above mu is good (positive z_stat)
        
        We use absolute deviation from mean - the sign doesn't matter,
        only that there IS meaningful deviation.
    """
    # Extract required fields
    mu = pick.get("mu", pick.get("recent_avg", pick.get("player_avg", 0)))
    sigma = pick.get("sigma", pick.get("stddev", pick.get("player_stddev", 3.0)))
    
    # The line IS what we're evaluating against
    line = pick.get("line", 0)
    
    stat = pick.get("stat", pick.get("stat_type", pick.get("market", "default")))
    
    # Skip if no meaningful data
    if mu == 0 and line == 0:
        return pick, {"skipped": True, "reason": "no_data"}
    
    # Apply gate (line compared to mu)
    multiplier, result_desc, details = stat_deviation_gate(
        mu_context=mu,
        sigma=sigma,
        expected=line,  # Using LINE as the reference point
        stat=stat,
        mode=mode,
    )
    
    # Log result
    player = pick.get("player", "Unknown")
    logger.info(f"SDG [{player} {stat}]: {result_desc}")
    
    # Modify pick with SDG results
    pick_modified = pick.copy()
    pick_modified["sdg_z_stat"] = details.get("z_stat", 0)
    pick_modified["sdg_multiplier"] = multiplier
    pick_modified["sdg_penalty"] = details.get("penalty", "none")
    pick_modified["sdg_result"] = result_desc
    
    # Apply multiplier to probability if soft gate
    if mode == "soft" and multiplier < 1.0:
        for prob_field in ["probability", "raw_probability", "p_hit"]:
            if prob_field in pick_modified:
                old_prob = pick_modified[prob_field]
                new_prob = old_prob * multiplier
                pick_modified[prob_field] = new_prob
                pick_modified["sdg_prob_adjustment"] = {
                    "original": old_prob,
                    "adjusted": new_prob,
                    "multiplier": multiplier,
                }
                break
    
    return pick_modified, details


# =============================================================================
# EXAMPLE USAGE & TESTS
# =============================================================================

def _demo():
    """Demo SDG with examples from Quant recommendation."""
    
    print("\n" + "="*60)
    print("STAT DEVIATION GATE — DEMO")
    print("="*60)
    print("\nSDG compares the LINE to player's contextual mean (μ)")
    print("If |line - μ| is small relative to σ, it's a coin flip → PENALTY")
    
    # Example 1: Luka 29.5 PTS line (near his mean — coin flip)
    print("\n📊 Example 1: Luka Doncic PTS (star-tax trap)")
    print("   Line=29.5, μ=29.5, σ=7.5")
    mult, desc, details = stat_deviation_gate(
        mu_context=29.5,  # Recent avg
        sigma=7.5,        # High variance
        expected=29.5,    # LINE at exact mean
        stat="pts",
        mode="soft",
    )
    print(f"   z_stat = (29.5 - 29.5) / 7.5 = {details['z_stat']:+.2f}")
    print(f"   Result: {desc}")
    print(f"   Multiplier: {mult:.2f}")
    print(f"   → {'❌ HEAVY PENALTY' if mult < 0.8 else '✅ PASS'}")
    
    # Example 2: Cade PRA line well below mean (good edge for HIGHER)
    print("\n📊 Example 2: Cade Cunningham PRA (line below mean — good edge)")
    print("   Line=30.5, μ=35.0, σ=6.0")
    mult, desc, details = stat_deviation_gate(
        mu_context=35.0,  # Recent avg
        sigma=6.0,        # Moderate variance
        expected=30.5,    # LINE well below mean
        stat="pra",
        mode="soft",
    )
    print(f"   z_stat = (30.5 - 35.0) / 6.0 = {details['z_stat']:+.2f}")
    print(f"   Result: {desc}")
    print(f"   Multiplier: {mult:.2f}")
    print(f"   → {'❌ PENALTY' if mult < 1.0 else '✅ PASS'}")
    
    # Example 3: Line slightly below mean (borderline)
    print("\n📊 Example 3: Line slightly below mean (medium penalty zone)")
    print("   Line=23.5, μ=25.0, σ=5.0")
    mult, desc, details = stat_deviation_gate(
        mu_context=25.0,
        sigma=5.0,
        expected=23.5,    # z = -0.30 (between 0.25 and 0.50)
        stat="pts",
        mode="soft",
    )
    print(f"   z_stat = (23.5 - 25.0) / 5.0 = {details['z_stat']:+.2f}")
    print(f"   Result: {desc}")
    print(f"   Multiplier: {mult:.2f}")
    
    # Example 4: 3PM line above mean (good edge for LOWER)
    print("\n📊 Example 4: 3PM line well above mean (good LOWER edge)")
    print("   Line=4.5, μ=3.0, σ=1.2")
    mult, desc, details = stat_deviation_gate(
        mu_context=3.0,
        sigma=1.2,
        expected=4.5,     # z = +1.25, clearly deviated
        stat="3pm",
        mode="soft",
    )
    print(f"   z_stat = (4.5 - 3.0) / 1.2 = {details['z_stat']:+.2f}")
    print(f"   After 3PM adjustment: {details.get('abs_z_adjusted', 0):.2f}")
    print(f"   Result: {desc}")
    print(f"   Multiplier: {mult:.2f}")
    
    print("\n" + "="*60)
    print("SDG prevents betting when line ≈ player's mean (coin flip)")
    print("="*60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _demo()
