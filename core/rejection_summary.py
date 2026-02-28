"""
Rejection Summary — Mandatory Explanation for NO PLAY Heavy Slates
SOP v2.2: If NO_PLAY > 200, a rejection summary is REQUIRED or render aborts.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Counter as CounterType
from collections import Counter
import logging

logger = logging.getLogger(__name__)


# ========== REJECTION REASON CATEGORIES ==========

REJECTION_CATEGORIES = {
    # Injury-related
    "INJURY_UNCERTAINTY": "Injury / minutes uncertainty",
    "EARLY_RETURN": "Early return from injury",
    "MINUTES_VOLATILE": "Minutes volatility too high",
    
    # Variance-related
    "VARIANCE_HIGH": "Variance too high (σ inflation)",
    "CV_ELEVATED": "Coefficient of variation elevated",
    "SAMPLE_SMALL": "Insufficient sample size",
    
    # Edge-related
    "EDGE_INSUFFICIENT": "Insufficient edge (<0.5σ)",
    "EDGE_GATE_FAIL": "Edge gate failure (<3%)",
    "Z_SCORE_LOW": "Z-score below threshold",
    
    # Context-related
    "ROLE_MISMATCH": "Role-stat mismatch",
    "MATCHUP_UNFAVORABLE": "Unfavorable matchup",
    "PACE_MISMATCH": "Pace mismatch",
    "BLOWOUT_RISK": "Blowout risk elevated",
    
    # Correlation-related
    "CORRELATION_CONFLICT": "Correlation conflicts",
    "DUPLICATE_EDGE": "Duplicate edge detected",
    
    # Gate failures
    "GATE_FAIL_COMPOSITE": "Composite gate failure",
    "GATE_FAIL_DEFENSE": "Elite defense gate",
    "GATE_FAIL_BENCH": "Bench trap gate",
    "CONFIDENCE_TOO_LOW": "Confidence below threshold",
    
    # Data issues
    "NO_DATA": "No player data available",
    "API_FALLBACK": "API fallback used",
    "STALE_DATA": "Stale data detected",
    
    # Unknown
    "UNKNOWN": "Other / unclassified"
}


@dataclass
class RejectionSummaryResult:
    """Machine-readable rejection summary."""
    total_rejected: int
    breakdown: Dict[str, float]  # reason -> percentage
    top_reasons: List[str]
    summary_text: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rejected": self.total_rejected,
            "rejection_breakdown": self.breakdown,
            "top_rejection_reasons": self.top_reasons,
            "rejection_summary_text": self.summary_text
        }


def categorize_rejection(result: Dict[str, Any]) -> str:
    """
    Categorize why a prop was rejected based on its result data.
    
    Args:
        result: Analysis result dict for a single prop
    
    Returns:
        Rejection category key
    """
    # Check gate details
    gate_details = result.get("gate_details", [])
    for gate in gate_details:
        if not gate.get("passed", True):
            gate_name = gate.get("gate", "").upper()
            if "COMPOSITE" in gate_name:
                return "GATE_FAIL_COMPOSITE"
            if "DEF" in gate_name or "ELITE" in gate_name:
                return "GATE_FAIL_DEFENSE"
            if "BENCH" in gate_name:
                return "GATE_FAIL_BENCH"
    
    # Check edge gate
    qf = result.get("quant_framework", {})
    if qf.get("edge_gate_passed") is False:
        return "EDGE_GATE_FAIL"
    
    # Check injury
    if result.get("injury_return"):
        return "INJURY_UNCERTAINTY"
    
    # Check variance
    minutes_cv = result.get("minutes_cv", 0)
    if minutes_cv and minutes_cv > 0.25:
        return "MINUTES_VOLATILE"
    
    sigma = result.get("sigma", 0)
    mu = result.get("mu", 1)
    if mu > 0 and sigma / mu > 0.5:
        return "VARIANCE_HIGH"
    
    # Check edge
    z_score = result.get("z_score", 0)
    if abs(z_score) < 0.5:
        return "EDGE_INSUFFICIENT"
    
    # Check confidence
    confidence = result.get("model_confidence", 0)
    if confidence < 55:
        return "CONFIDENCE_TOO_LOW"
    
    # Check sample size
    sample_n = result.get("sample_n", 0)
    if sample_n and sample_n < 10:
        return "SAMPLE_SMALL"
    
    # Check stat adjustment blocks
    if result.get("stat_edge_block"):
        return "EDGE_INSUFFICIENT"
    
    # Check context warnings for clues
    warnings = result.get("context_warnings", [])
    for warning in warnings:
        warning_lower = warning.lower()
        if "role" in warning_lower or "mismatch" in warning_lower:
            return "ROLE_MISMATCH"
        if "matchup" in warning_lower:
            return "MATCHUP_UNFAVORABLE"
        if "blowout" in warning_lower:
            return "BLOWOUT_RISK"
        if "variance" in warning_lower:
            return "CV_ELEVATED"
    
    return "UNKNOWN"


def build_rejection_summary(rejected_picks: List[Dict[str, Any]]) -> RejectionSummaryResult:
    """
    Build a rejection summary from a list of rejected picks.
    
    Args:
        rejected_picks: List of result dicts for props that were rejected
    
    Returns:
        RejectionSummaryResult with breakdown and formatted text
    """
    if not rejected_picks:
        return RejectionSummaryResult(
            total_rejected=0,
            breakdown={},
            top_reasons=[],
            summary_text="No picks rejected."
        )
    
    # Categorize each rejection
    reasons = [categorize_rejection(p) for p in rejected_picks]
    reason_counts = Counter(reasons)
    total = len(reasons)
    
    # Compute percentages
    breakdown = {
        REJECTION_CATEGORIES.get(reason, reason): round(count / total * 100, 1)
        for reason, count in reason_counts.most_common()
    }
    
    # Get top 5 reasons
    top_reasons = list(breakdown.keys())[:5]
    
    # Format summary text
    lines = [
        "WHY PICKS WERE REJECTED",
        "-" * 50,
    ]
    for reason, pct in list(breakdown.items())[:7]:
        lines.append(f"  • {pct:5.1f}% — {reason}")
    
    return RejectionSummaryResult(
        total_rejected=total,
        breakdown=breakdown,
        top_reasons=top_reasons,
        summary_text="\n".join(lines)
    )


def require_rejection_summary(
    no_play_count: int,
    results: List[Dict[str, Any]],
    threshold: int = 200
) -> RejectionSummaryResult:
    """
    Require a rejection summary if NO PLAY count exceeds threshold.
    
    This is a HARD GATE: if NO PLAY > threshold and we can't generate
    a summary, render should abort.
    
    Args:
        no_play_count: Number of NO PLAY decisions
        results: All analysis results
        threshold: NO PLAY count threshold for requiring summary
    
    Returns:
        RejectionSummaryResult
    
    Raises:
        RuntimeError if summary cannot be generated when required
    """
    if no_play_count <= threshold:
        return RejectionSummaryResult(
            total_rejected=no_play_count,
            breakdown={},
            top_reasons=[],
            summary_text=""
        )
    
    # Filter to rejected picks
    rejected = [
        r for r in results
        if r.get("decision", "").upper() in ("NO_PLAY", "NO PLAY", "PASS", "BLOCKED", "SKIP")
    ]
    
    if not rejected:
        raise RuntimeError(
            f"RENDER GATE VIOLATION: {no_play_count} NO PLAY but cannot generate rejection summary"
        )
    
    summary = build_rejection_summary(rejected)
    
    if not summary.breakdown:
        raise RuntimeError(
            f"RENDER GATE VIOLATION: {no_play_count} NO PLAY but rejection summary is empty"
        )
    
    logger.info(f"Rejection summary generated: {no_play_count} picks, {len(summary.breakdown)} categories")
    
    return summary
