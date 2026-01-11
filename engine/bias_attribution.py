"""
Phase 2 - Bias Attribution Report

Automatic root-cause diagnosis for directional skew.
Rule-based, deterministic, no guessing.
"""
from typing import Dict, List
from collections import Counter
import json
from pathlib import Path
from datetime import datetime


def compute_directional_distribution(picks: list) -> dict:
    """
    Quantify OVER/UNDER distribution.
    
    Args:
        picks: List of scored picks with direction field
    
    Returns:
        Distribution stats with percentages
    """
    total = len(picks)
    if total == 0:
        return {
            "total": 0,
            "overs": 0,
            "unders": 0,
            "over_pct": 0.0,
            "under_pct": 0.0
        }
    
    overs = 0
    unders = 0
    
    for p in picks:
        direction = str(p.get("direction", "")).lower()
        if direction in ("over", "higher", "o", "h"):
            overs += 1
        elif direction in ("under", "lower", "u", "l"):
            unders += 1
    
    return {
        "total": total,
        "overs": overs,
        "unders": unders,
        "over_pct": round(overs / total * 100, 1),
        "under_pct": round(unders / total * 100, 1)
    }


def attribute_bias(picks: list, distribution: dict) -> list:
    """
    Identify root causes of directional bias.
    
    Rule-based heuristics mapping to known failure modes:
    - DIRECTIONAL_SKEW_UNDER: >80% UNDERS
    - DIRECTIONAL_SKEW_OVER: >80% OVERS
    - EMPIRICAL_DISTRIBUTION_SKEW: Historical data skewed
    - PACE_CONTEXT_NEGATIVE: Pace adjustments trend negative
    - RECENT_FORM_OVERWEIGHT: Recent games dominating signal
    
    Args:
        picks: Scored picks with audit trail
        distribution: Directional distribution from compute_directional_distribution
    
    Returns:
        List of detected bias causes
    """
    reasons = []
    
    # Check directional skew (>80% threshold)
    if distribution["under_pct"] > 80:
        reasons.append("DIRECTIONAL_SKEW_UNDER")
    if distribution["over_pct"] > 80:
        reasons.append("DIRECTIONAL_SKEW_OVER")
    
    # Check empirical distribution skew
    empirical_rates = []
    for p in picks:
        if "prob_method" in p and "empirical_hit_rate" in p["prob_method"]:
            empirical_rates.append(p["prob_method"]["empirical_hit_rate"])
    
    if empirical_rates:
        avg_emp_rate = sum(empirical_rates) / len(empirical_rates)
        if avg_emp_rate < 0.45:
            reasons.append("EMPIRICAL_DISTRIBUTION_SKEW")
    
    # Check pace context
    pace_deltas = []
    for p in picks:
        if "pace_context" in p and p["pace_context"].get("pace_data_available"):
            pace_adj_mean = p["pace_context"]["pace_adjusted_mean"]
            line = p.get("line")
            if line is not None:
                pace_deltas.append(pace_adj_mean - line)
    
    if pace_deltas:
        avg_pace_delta = sum(pace_deltas) / len(pace_deltas)
        if avg_pace_delta < -0.5:
            reasons.append("PACE_CONTEXT_NEGATIVE")
    
    # Check recent form dominance (if we have that field)
    recent_weights = [p.get("recent_form_weight", 0) for p in picks if "recent_form_weight" in p]
    if recent_weights:
        avg_recent_weight = sum(recent_weights) / len(recent_weights)
        if avg_recent_weight > 0.45:
            reasons.append("RECENT_FORM_OVERWEIGHT")
    
    return reasons


def bias_severity(distribution: dict) -> str:
    """
    Classify bias severity for gate enforcement.
    
    Args:
        distribution: Directional distribution stats
    
    Returns:
        "CRITICAL", "HIGH", "MODERATE", or "NORMAL"
    """
    under_pct = distribution["under_pct"]
    over_pct = distribution["over_pct"]
    
    if under_pct >= 95 or over_pct >= 95:
        return "CRITICAL"
    if under_pct >= 85 or over_pct >= 85:
        return "HIGH"
    if under_pct >= 75 or over_pct >= 75:
        return "MODERATE"
    return "NORMAL"


def generate_bias_report(picks: list, run_date: str = None) -> dict:
    """
    Generate complete bias attribution report.
    
    Args:
        picks: Scored picks from pipeline
        run_date: ISO date string (defaults to today)
    
    Returns:
        Bias report dict with severity, causes, and enforcement flags
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    
    dist = compute_directional_distribution(picks)
    reasons = attribute_bias(picks, dist)
    severity = bias_severity(dist)
    
    return {
        "run_date": run_date,
        "timestamp": datetime.now().isoformat(),
        "severity": severity,
        "directional_distribution": dist,
        "root_causes": reasons,
        "bias_detected": severity != "NORMAL",
        "learning_allowed": severity == "NORMAL",
        "recommendation": get_bias_recommendation(severity, reasons)
    }


def get_bias_recommendation(severity: str, reasons: list) -> str:
    """
    Generate actionable recommendation based on bias diagnosis.
    
    Args:
        severity: Bias severity level
        reasons: List of detected root causes
    
    Returns:
        Human-readable recommendation
    """
    if severity == "CRITICAL":
        return "DO NOT BROADCAST - Critical directional bias detected"
    
    if severity == "HIGH":
        return "ANALYSIS ONLY - High bias requires model investigation"
    
    if severity == "MODERATE":
        return "CAUTION - Moderate bias detected, monitor closely"
    
    return "NORMAL - No significant bias detected"


def save_bias_report(report: dict, output_dir: str = "logs") -> Path:
    """
    Save bias report to audit log.
    
    Args:
        report: Bias report dict from generate_bias_report
        output_dir: Directory for bias logs
    
    Returns:
        Path to saved report file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    report_file = output_path / f"bias_report_{report['run_date']}.json"
    
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    return report_file


def enforce_bias_policy(report: dict, mode: str) -> tuple[bool, str]:
    """
    Enforce bias policy based on severity and mode.
    
    Args:
        report: Bias report from generate_bias_report
        mode: "analysis" or "broadcast"
    
    Returns:
        (allowed_to_continue, reason)
    """
    severity = report["severity"]
    
    # ANALYSIS mode always continues (logs only)
    if mode.lower() == "analysis":
        return True, "ANALYSIS mode - bias logged for inspection"
    
    # BROADCAST mode enforces hard stops
    if severity == "CRITICAL":
        return False, "CRITICAL bias - broadcast blocked"
    
    if severity == "HIGH":
        return False, "HIGH bias - broadcast blocked"
    
    if severity == "MODERATE":
        return True, "MODERATE bias - broadcast allowed with warning"
    
    return True, "NORMAL - no bias concerns"
