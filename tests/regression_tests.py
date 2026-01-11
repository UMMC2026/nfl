"""
Regression Test Framework — Anti-Drift Lock

PURPOSE:
If someone re-introduces UNDER bias, bad math, fake confidence, or gate bypassing,
the system FAILS immediately. Not warns. Not logs. FAILS.

ENFORCEMENT CATEGORIES:
1. Directional balance (prevent 90%+ OVER/UNDER days)
2. Probability correctness (ensure empirical-only)
3. Tier integrity (prevent thin-sample SLAMs, tier inflation)
4. Gate immutability (prevent emotional overrides)
5. Analysis ≠ Broadcast (prevent accidental Telegram blasts)
6. Learning freeze (prevent poisoned memory on biased runs)

USAGE:
    from tests.regression_tests import run_all_regression_tests
    
    run_all_regression_tests(
        picks=validated_picks,
        config=pipeline_config,
        context={
            "pipeline_mode": "ANALYSIS",
            "bias_report": bias_report,
            "telegram_sent": False,
            "learning_attempted": False
        }
    )

If ANY test fails:
* Raises AssertionError with detailed message
* Pipeline must abort
* No broadcast, no learning, no output
"""

from typing import List, Dict, Any
from collections import Counter
from engine.bias_attribution import compute_directional_distribution


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1️⃣ DIRECTIONAL BALANCE TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_directional_balance(picks: List[Dict[str, Any]], max_bias: float = 0.80):
    """
    Prevents 90%+ OVER/UNDER days.
    Ensures pace + empirical logic stays active.
    
    Args:
        picks: List of pick dictionaries with 'direction' field
        max_bias: Maximum allowed directional skew (default 80%)
    
    Raises:
        AssertionError: If either direction exceeds max_bias threshold
    """
    dist = compute_directional_distribution(picks)
    
    under_pct = dist["under_pct"] / 100.0
    over_pct = dist["over_pct"] / 100.0
    
    if under_pct > max_bias:
        raise AssertionError(
            f"🚨 REGRESSION: UNDER bias too high ({dist['under_pct']:.1f}% > {max_bias*100:.0f}%)\n"
            f"   Distribution: {dist['unders']} UNDER / {dist['overs']} OVER\n"
            f"   CAUSE: Pace adjustment or empirical logic broken\n"
            f"   ACTION: Review engine/pace_adjustment.py and engine/empirical_probability.py"
        )
    
    if over_pct > max_bias:
        raise AssertionError(
            f"🚨 REGRESSION: OVER bias too high ({dist['over_pct']:.1f}% > {max_bias*100:.0f}%)\n"
            f"   Distribution: {dist['overs']} OVER / {dist['unders']} UNDER\n"
            f"   CAUSE: Pace adjustment or empirical logic broken\n"
            f"   ACTION: Review engine/pace_adjustment.py and engine/empirical_probability.py"
        )
    
    print(f"   ✅ Directional balance: {dist['under_pct']:.1f}% UNDER / {dist['over_pct']:.1f}% OVER")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2️⃣ PROBABILITY METHOD TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_probability_method(picks: List[Dict[str, Any]]):
    """
    Prevents Normal CDF from sneaking back in.
    Prevents "quick fixes" under pressure.
    
    Args:
        picks: List of pick dictionaries with 'probability_method' field
    
    Raises:
        AssertionError: If any pick uses non-empirical probability method
    """
    violations = []
    
    for p in picks:
        method = p.get("probability_method")
        
        if method != "empirical":
            violations.append({
                "player": p.get("player_name", "Unknown"),
                "stat": p.get("stat_type", "Unknown"),
                "method": method,
                "probability": p.get("probability")
            })
    
    if violations:
        error_msg = "🚨 REGRESSION: Non-empirical probability detected\n"
        error_msg += "   VIOLATIONS:\n"
        for v in violations[:5]:  # Show first 5
            error_msg += f"     • {v['player']} {v['stat']}: method={v['method']}, p={v['probability']:.3f}\n"
        if len(violations) > 5:
            error_msg += f"     ... and {len(violations) - 5} more\n"
        error_msg += "   CAUSE: Someone reintroduced Normal CDF or other distributional assumption\n"
        error_msg += "   ACTION: Review engine/score_edges.py and engine/empirical_probability.py"
        
        raise AssertionError(error_msg)
    
    print(f"   ✅ Probability method: All {len(picks)} picks use empirical method")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3️⃣ EMPIRICAL SAMPLE SIZE TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_minimum_sample_sizes(picks: List[Dict[str, Any]]):
    """
    Prevents fake confidence from thin samples.
    Prevents thin-sample SLAMs.
    
    Requirements:
    * SLAM: n ≥ 25
    * STRONG: n ≥ 20
    * LEAN: n ≥ 15
    
    Args:
        picks: List of pick dictionaries with 'confidence_tier' and 'empirical_sample_size'
    
    Raises:
        AssertionError: If any high-tier pick has insufficient sample size
    """
    TIER_MINIMUMS = {
        "SLAM": 25,
        "STRONG": 20,
        "LEAN": 15
    }
    
    violations = []
    
    for p in picks:
        tier = p.get("confidence_tier")
        sample_size = p.get("empirical_sample_size", 0)
        
        if tier in TIER_MINIMUMS:
            required = TIER_MINIMUMS[tier]
            if sample_size < required:
                violations.append({
                    "player": p.get("player_name", "Unknown"),
                    "stat": p.get("stat_type", "Unknown"),
                    "tier": tier,
                    "sample_size": sample_size,
                    "required": required
                })
    
    if violations:
        error_msg = "🚨 REGRESSION: Insufficient sample sizes for tier assignments\n"
        error_msg += "   VIOLATIONS:\n"
        for v in violations[:5]:
            error_msg += f"     • {v['player']} {v['stat']}: {v['tier']} with n={v['sample_size']} (requires {v['required']})\n"
        if len(violations) > 5:
            error_msg += f"     ... and {len(violations) - 5} more\n"
        error_msg += "   CAUSE: Tier calibration policy bypassed or minimum thresholds lowered\n"
        error_msg += "   ACTION: Review engine/tier_calibration.py TIER_POLICY settings"
        
        raise AssertionError(error_msg)
    
    print(f"   ✅ Sample sizes: All tier assignments meet minimum thresholds")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4️⃣ TIER COMPRESSION TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_tier_distribution(picks: List[Dict[str, Any]]):
    """
    Prevents tier inflation ("everything is strong" days).
    Enforces maximum share per tier.
    
    Limits:
    * SLAM: max 15%
    * STRONG: max 30%
    * LEAN: max 50%
    
    Args:
        picks: List of pick dictionaries with 'confidence_tier'
    
    Raises:
        AssertionError: If any tier exceeds maximum share
    """
    MAX_SHARES = {
        "SLAM": 0.15,
        "STRONG": 0.30,
        "LEAN": 0.50
    }
    
    tiers = Counter(p.get("confidence_tier") for p in picks if p.get("confidence_tier") != "NO PLAY")
    total = sum(tiers.values())
    
    if total == 0:
        print("   ⚠️  Tier distribution: No playable picks (skipping test)")
        return
    
    violations = []
    
    for tier, max_share in MAX_SHARES.items():
        count = tiers.get(tier, 0)
        actual_share = count / total
        
        if actual_share > max_share:
            violations.append({
                "tier": tier,
                "count": count,
                "total": total,
                "actual_share": actual_share,
                "max_share": max_share
            })
    
    if violations:
        error_msg = "🚨 REGRESSION: Tier inflation detected\n"
        error_msg += "   VIOLATIONS:\n"
        for v in violations:
            error_msg += f"     • {v['tier']}: {v['count']}/{v['total']} = {v['actual_share']:.1%} (max {v['max_share']:.0%})\n"
        error_msg += "   CAUSE: Tier compression failed or max_share limits bypassed\n"
        error_msg += "   ACTION: Review engine/tier_calibration.py compress_tiers() function"
        
        raise AssertionError(error_msg)
    
    tier_summary = " / ".join([f"{tier}:{count}" for tier, count in tiers.most_common()])
    print(f"   ✅ Tier distribution: {tier_summary} (n={total})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5️⃣ GATE IMMUTABILITY TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_gate_immutability(config: Dict[str, Any]):
    """
    Prevents emotional overrides.
    Prevents "just for tonight" changes.
    
    Gates must be:
    * BIAS_GATE_ENABLED = True
    * RENDER_GATE_ENABLED = True
    * ALLOW_GATE_OVERRIDE = False (if exists)
    
    Args:
        config: Pipeline configuration dictionary
    
    Raises:
        AssertionError: If gates are disabled or overridable
    """
    violations = []
    
    # Check bias gate
    if not config.get("BIAS_GATE_ENABLED", True):
        violations.append("BIAS_GATE_ENABLED = False (should be True)")
    
    # Check render gate
    if not config.get("RENDER_GATE_ENABLED", True):
        violations.append("RENDER_GATE_ENABLED = False (should be True)")
    
    # Check override flag (if exists)
    if config.get("ALLOW_GATE_OVERRIDE", False):
        violations.append("ALLOW_GATE_OVERRIDE = True (should be False)")
    
    if violations:
        error_msg = "🚨 REGRESSION: Gate configuration compromised\n"
        error_msg += "   VIOLATIONS:\n"
        for v in violations:
            error_msg += f"     • {v}\n"
        error_msg += "   CAUSE: Gates manually disabled or override flag set\n"
        error_msg += "   ACTION: Restore gate settings in configuration file\n"
        error_msg += "   WARNING: System is UNSAFE for broadcast"
        
        raise AssertionError(error_msg)
    
    print(f"   ✅ Gate immutability: All gates locked and enforced")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6️⃣ ANALYSIS ≠ BROADCAST TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_broadcast_restriction(pipeline_mode: str, bias_detected: bool, telegram_sent: bool):
    """
    Prevents accidental Telegram blasts.
    Prevents broadcasts during bias or ANALYSIS mode.
    
    Rules:
    * ANALYSIS mode: Never broadcast
    * Bias detected: Never broadcast
    
    Args:
        pipeline_mode: "ANALYSIS" or "BROADCAST"
        bias_detected: Whether bias report flagged bias
        telegram_sent: Whether Telegram broadcast occurred
    
    Raises:
        AssertionError: If broadcast occurred when prohibited
    """
    violations = []
    
    if pipeline_mode == "ANALYSIS" and telegram_sent:
        violations.append(
            "Telegram broadcast occurred in ANALYSIS mode\n"
            "   ANALYSIS mode should NEVER trigger broadcasts"
        )
    
    if bias_detected and telegram_sent:
        violations.append(
            "Telegram broadcast occurred despite bias detection\n"
            f"   Bias flag: {bias_detected}\n"
            "   Biased runs should NEVER broadcast"
        )
    
    if violations:
        error_msg = "🚨 REGRESSION: Unauthorized broadcast detected\n"
        error_msg += "   VIOLATIONS:\n"
        for v in violations:
            error_msg += f"     • {v}\n"
        error_msg += "   CAUSE: Broadcast logic bypassed mode or bias checks\n"
        error_msg += "   ACTION: Review Telegram integration and mode enforcement"
        
        raise AssertionError(error_msg)
    
    if pipeline_mode == "ANALYSIS":
        print(f"   ✅ Broadcast restriction: ANALYSIS mode, no broadcast (as expected)")
    elif bias_detected:
        print(f"   ✅ Broadcast restriction: Bias detected, no broadcast (as expected)")
    else:
        print(f"   ✅ Broadcast restriction: BROADCAST mode, bias-free, broadcast allowed")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7️⃣ LEARNING FREEZE TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_learning_freeze(bias_report: Dict[str, Any], learning_attempted: bool):
    """
    Prevents poisoned memory.
    Prevents self-reinforcing bias.
    
    Rule:
    * If bias detected: NO learning allowed
    
    Args:
        bias_report: Bias attribution report dictionary
        learning_attempted: Whether learning/calibration update was attempted
    
    Raises:
        AssertionError: If learning occurred on biased run
    """
    bias_detected = bias_report.get("bias_detected", False)
    
    if bias_detected and learning_attempted:
        severity = bias_report.get("severity", "UNKNOWN")
        causes = bias_report.get("root_causes", [])
        
        error_msg = "🚨 REGRESSION: Learning attempted on biased run\n"
        error_msg += f"   Bias severity: {severity}\n"
        if causes:
            error_msg += f"   Root causes: {', '.join(causes)}\n"
        error_msg += "   CAUSE: Learning freeze bypassed or bias report ignored\n"
        error_msg += "   ACTION: Review learning/calibration logic and bias enforcement\n"
        error_msg += "   WARNING: Biased data may have poisoned calibration memory"
        
        raise AssertionError(error_msg)
    
    if bias_detected:
        print(f"   ✅ Learning freeze: Bias detected, learning frozen (as expected)")
    else:
        print(f"   ✅ Learning freeze: No bias, learning allowed")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MASTER TEST RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_all_regression_tests(
    picks: List[Dict[str, Any]],
    config: Dict[str, Any],
    context: Dict[str, Any]
) -> None:
    """
    Run complete regression test suite.
    
    If ANY test fails:
    * Raises AssertionError with detailed message
    * Pipeline must abort
    * No broadcast, no learning, no output
    
    Args:
        picks: Final validated pick list
        config: Pipeline configuration
        context: Execution context with:
            - pipeline_mode: "ANALYSIS" or "BROADCAST"
            - bias_report: Bias attribution report dict
            - telegram_sent: Whether broadcast occurred
            - learning_attempted: Whether learning was attempted
    
    Raises:
        AssertionError: If any regression test fails
    """
    print("🔒 REGRESSION TEST SUITE")
    print("   Running anti-drift enforcement...")
    print()
    
    try:
        # Test 1: Directional balance
        test_directional_balance(picks)
        
        # Test 2: Probability method
        test_probability_method(picks)
        
        # Test 3: Sample sizes
        test_minimum_sample_sizes(picks)
        
        # Test 4: Tier distribution
        test_tier_distribution(picks)
        
        # Test 5: Gate immutability
        test_gate_immutability(config)
        
        # Test 6: Broadcast restriction
        test_broadcast_restriction(
            pipeline_mode=context.get("pipeline_mode", "ANALYSIS"),
            bias_detected=context.get("bias_report", {}).get("bias_detected", False),
            telegram_sent=context.get("telegram_sent", False)
        )
        
        # Test 7: Learning freeze
        test_learning_freeze(
            bias_report=context.get("bias_report", {}),
            learning_attempted=context.get("learning_attempted", False)
        )
        
        print()
        print("   ✅ ALL REGRESSION TESTS PASSED")
        print("   System integrity verified — safe to proceed")
        print()
        
    except AssertionError as e:
        print()
        print("   ❌ REGRESSION TEST FAILED")
        print()
        raise


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INDIVIDUAL TEST EXPORTS (for targeted use)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "run_all_regression_tests",
    "test_directional_balance",
    "test_probability_method",
    "test_minimum_sample_sizes",
    "test_tier_distribution",
    "test_gate_immutability",
    "test_broadcast_restriction",
    "test_learning_freeze",
]
