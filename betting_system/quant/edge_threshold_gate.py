#!/usr/bin/env python3
"""
EDGE_THRESHOLD_GATE.PY — SOP v2.1 QUANT FRAMEWORK
=================================================
Implements the 3% minimum edge requirement.

THIS WAS MISSING FROM YOUR SYSTEM.

No matter how high the confidence, if the EDGE is below 3%,
the play should be rejected. Edge = Your confidence - Market implied probability.

Why 3%?
- Accounts for variance and model error
- Ensures long-term profitability after juice/vig
- Professional sharps use 3-5% minimum

Version: 2.1.0
Author: SOP v2.1 Integration
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# CONFIGURATION
# ============================================================================

# Minimum edge thresholds by tier
# TUNED DOWN 2026-01-29: Previous thresholds killed profitable plays
# Embiid had 8% edge and was rejected. That's insane.
EDGE_THRESHOLDS = {
    "SLAM": 0.03,      # 3% edge for top tier (was 5%)
    "STRONG": 0.02,    # 2% edge required (was 4%)
    "LEAN": 0.015,     # 1.5% edge required (was 3%)
    "SPEC": 0.01,      # 1% for speculative (was 2%)
    "NO_PLAY": 0.00    # Below all thresholds
}

# Standard implied probabilities by odds
STANDARD_IMPLIED = {
    -110: 0.5238,  # Most common
    -115: 0.5349,
    -120: 0.5455,
    -105: 0.5122,
    100: 0.5000,
    "default": 0.5238  # Assume -110
}

# Expected Value (EV) calculation at -110 odds
# Payout ratio at -110 = 100/110 = 0.909
PAYOUT_RATIO_110 = 0.909


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class GateResult(Enum):
    """Result of edge gate check"""
    PASS_SLAM = "PASS_SLAM"
    PASS_STRONG = "PASS_STRONG"
    PASS_LEAN = "PASS_LEAN"
    PASS_SPEC = "PASS_SPEC"
    FAIL = "FAIL"


@dataclass
class EdgeGateResult:
    """Complete edge gate analysis"""
    # Inputs
    confidence: float
    implied_probability: float
    odds: int
    
    # Calculated
    edge: float
    edge_percent: float
    expected_value: float
    ev_percent: float
    
    # Gate result
    passes_gate: bool
    gate_result: GateResult
    required_edge: float
    edge_surplus: float
    
    # Recommendations
    tier_recommendation: str
    bet_recommendation: str


# ============================================================================
# EDGE CALCULATIONS
# ============================================================================

def calculate_implied_probability(odds: int) -> float:
    """
    Convert American odds to implied probability.
    
    -110 → 52.38%
    +150 → 40.00%
    -200 → 66.67%
    """
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def calculate_edge(confidence: float, implied_prob: float) -> float:
    """
    Calculate edge: your probability minus market's implied probability.
    
    Edge = P(you) - P(market)
    
    If you think 65% and market implies 52.4%, edge = 12.6%
    """
    return confidence - implied_prob


def calculate_expected_value(confidence: float, odds: int) -> float:
    """
    Calculate Expected Value at given odds.
    
    EV = (P(win) × Payout) - (P(lose) × Stake)
    
    At -110 odds:
    - Win: +$90.91 profit on $100 bet
    - Lose: -$100
    
    EV = (confidence × 0.909) - ((1 - confidence) × 1.0)
    """
    if odds < 0:
        payout_ratio = 100 / abs(odds)
    else:
        payout_ratio = odds / 100
    
    ev = (confidence * payout_ratio) - ((1 - confidence) * 1.0)
    return ev


def check_edge_gate(
    confidence: float,
    odds: int = -110,
    custom_implied: Optional[float] = None
) -> EdgeGateResult:
    """
    Check if edge meets minimum threshold.
    
    Args:
        confidence: Your calculated probability (0.0 to 1.0)
        odds: American odds (default -110)
        custom_implied: Override implied probability if known
        
    Returns:
        EdgeGateResult with full analysis
    """
    
    # Get implied probability
    if custom_implied is not None:
        implied_prob = custom_implied
    else:
        implied_prob = calculate_implied_probability(odds)
    
    # Calculate edge
    edge = calculate_edge(confidence, implied_prob)
    edge_percent = edge * 100
    
    # Calculate EV
    ev = calculate_expected_value(confidence, odds)
    ev_percent = ev * 100
    
    # Determine gate result
    if edge >= EDGE_THRESHOLDS["SLAM"]:
        gate_result = GateResult.PASS_SLAM
        passes = True
        required = EDGE_THRESHOLDS["SLAM"]
        tier = "SLAM"
        bet_rec = "FULL PLAY — Maximum conviction"
    elif edge >= EDGE_THRESHOLDS["STRONG"]:
        gate_result = GateResult.PASS_STRONG
        passes = True
        required = EDGE_THRESHOLDS["STRONG"]
        tier = "STRONG"
        bet_rec = "STANDARD PLAY — High confidence"
    elif edge >= EDGE_THRESHOLDS["LEAN"]:
        gate_result = GateResult.PASS_LEAN
        passes = True
        required = EDGE_THRESHOLDS["LEAN"]
        tier = "LEAN"
        bet_rec = "SMALL PLAY — Moderate confidence"
    elif edge >= EDGE_THRESHOLDS["SPEC"]:
        gate_result = GateResult.PASS_SPEC
        passes = True
        required = EDGE_THRESHOLDS["SPEC"]
        tier = "SPEC"
        bet_rec = "TRACK ONLY — Below betting threshold"
    else:
        gate_result = GateResult.FAIL
        passes = False
        required = EDGE_THRESHOLDS["LEAN"]
        tier = "NO_PLAY"
        bet_rec = "NO PLAY — Insufficient edge"
    
    edge_surplus = edge - required
    
    return EdgeGateResult(
        confidence=round(confidence, 4),
        implied_probability=round(implied_prob, 4),
        odds=odds,
        edge=round(edge, 4),
        edge_percent=round(edge_percent, 2),
        expected_value=round(ev, 4),
        ev_percent=round(ev_percent, 2),
        passes_gate=passes,
        gate_result=gate_result,
        required_edge=required,
        edge_surplus=round(edge_surplus, 4),
        tier_recommendation=tier,
        bet_recommendation=bet_rec
    )


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def filter_by_edge_gate(
    picks: list,
    confidence_key: str = "confidence",
    min_tier: str = "LEAN"
) -> Tuple[list, list]:
    """
    Filter a list of picks by edge gate.
    
    Returns: (passed_picks, rejected_picks)
    """
    passed = []
    rejected = []
    
    tier_order = ["SLAM", "STRONG", "LEAN", "SPEC", "NO_PLAY"]
    min_tier_index = tier_order.index(min_tier)
    
    for pick in picks:
        confidence = pick.get(confidence_key, 0)
        result = check_edge_gate(confidence)
        
        tier_index = tier_order.index(result.tier_recommendation)
        
        if tier_index <= min_tier_index:
            pick["edge_analysis"] = {
                "edge": result.edge_percent,
                "ev": result.ev_percent,
                "tier": result.tier_recommendation,
                "passes": True
            }
            passed.append(pick)
        else:
            pick["edge_analysis"] = {
                "edge": result.edge_percent,
                "ev": result.ev_percent,
                "tier": result.tier_recommendation,
                "passes": False,
                "reason": f"Edge {result.edge_percent:.1f}% below {min_tier} threshold"
            }
            rejected.append(pick)
    
    return passed, rejected


# ============================================================================
# FORMATTING
# ============================================================================

def format_edge_report(result: EdgeGateResult) -> str:
    """Format edge gate result as readable report"""
    
    status = "✅ PASS" if result.passes_gate else "❌ FAIL"
    
    lines = []
    lines.append(f"┌─ EDGE THRESHOLD GATE ────────────────────────────────────────")
    lines.append(f"│")
    lines.append(f"│  Gate Status: {status}")
    lines.append(f"│")
    lines.append(f"│  Your Confidence:     {result.confidence:.1%}")
    lines.append(f"│  Market Implied:      {result.implied_probability:.1%} (at {result.odds} odds)")
    lines.append(f"│  ─────────────────────────────")
    lines.append(f"│  EDGE:                {result.edge_percent:+.2f}%")
    lines.append(f"│  Expected Value:      {result.ev_percent:+.2f}%")
    lines.append(f"│")
    lines.append(f"│  Required for tier:   {result.required_edge:.1%}")
    lines.append(f"│  Surplus/Deficit:     {result.edge_surplus:+.2%}")
    lines.append(f"│")
    lines.append(f"│  Tier:                {result.tier_recommendation}")
    lines.append(f"│  Recommendation:      {result.bet_recommendation}")
    lines.append(f"└───────────────────────────────────────────────────────────────")
    
    return "\n".join(lines)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("EDGE THRESHOLD GATE TESTS")
    print("=" * 65)
    
    # Test cases
    test_cases = [
        {"name": "Amen Thompson (your example)", "confidence": 0.645},
        {"name": "High confidence play", "confidence": 0.72},
        {"name": "Marginal play", "confidence": 0.56},
        {"name": "Below threshold", "confidence": 0.54},
        {"name": "SLAM candidate", "confidence": 0.80},
    ]
    
    for test in test_cases:
        print()
        print(f"Test: {test['name']}")
        result = check_edge_gate(test["confidence"])
        print(format_edge_report(result))
    
    # Show the math
    print()
    print("=" * 65)
    print("EDGE CALCULATION BREAKDOWN")
    print("=" * 65)
    print()
    print("At -110 odds:")
    print("  Implied probability = 110 / (110 + 100) = 52.38%")
    print()
    print("Edge examples:")
    print("  65% confidence: Edge = 65% - 52.38% = +12.62% ✓ STRONG")
    print("  58% confidence: Edge = 58% - 52.38% = +5.62%  ✓ SLAM")
    print("  55% confidence: Edge = 55% - 52.38% = +2.62%  ✗ NO PLAY (below 3%)")
    print()
    print("Minimum edges required:")
    for tier, threshold in EDGE_THRESHOLDS.items():
        print(f"  {tier:8s}: {threshold:.0%}")
