"""
Slate Quality & Defensive Mode Integration
SOP v2.2: Unified interface for all slate quality controls.

This module provides the main entry point for:
    - Computing slate quality
    - Evaluating defensive mode
    - Scaling confidence by API health
    - Generating rejection summaries
    - Enforcing render gates
"""

from typing import Dict, Any, List, Optional, Tuple
import logging

from .slate_quality import (
    compute_slate_quality,
    compute_slate_context_from_results,
    SlateQualityResult
)
from .api_health import (
    compute_api_health,
    scale_confidence,
    reset_api_health,
    record_api_success,
    record_api_failure,
    APIHealthResult
)
from .defensive_mode import (
    evaluate_defensive_mode,
    enforce_tier_cap,
    DefensiveModeResult
)
from .rejection_summary import (
    build_rejection_summary,
    require_rejection_summary,
    RejectionSummaryResult
)

logger = logging.getLogger(__name__)

__all__ = [
    # Main integration function
    "compute_slate_controls",
    "SlateControlsResult",
    # Re-exports
    "compute_slate_quality",
    "compute_api_health",
    "evaluate_defensive_mode",
    "build_rejection_summary",
    "scale_confidence",
    "enforce_tier_cap",
    "reset_api_health",
    "record_api_success",
    "record_api_failure",
]


class SlateControlsResult:
    """
    Unified result for all slate quality controls.
    
    This is the single source of truth for:
        - Slate quality score
        - API health
        - Defensive mode state
        - Rejection summary
        - Render gate status
    """
    
    def __init__(
        self,
        slate_quality: SlateQualityResult,
        api_health: APIHealthResult,
        defensive_mode: DefensiveModeResult,
        rejection_summary: Optional[RejectionSummaryResult] = None
    ):
        self.slate_quality = slate_quality
        self.api_health = api_health
        self.defensive_mode = defensive_mode
        self.rejection_summary = rejection_summary
        
        # Render gate checks
        self._render_gate_violations = []
        self._validate_render_gates()
    
    def _validate_render_gates(self):
        """Validate all render gates."""
        # Gate 1: Slate quality must be computed
        if self.slate_quality is None:
            self._render_gate_violations.append("Slate quality not computed")
        
        # Gate 2: API health must be computed
        if self.api_health is None:
            self._render_gate_violations.append("API health not computed")
        
        # Gate 3: Defensive mode must be evaluated
        if self.defensive_mode is None:
            self._render_gate_violations.append("Defensive mode not evaluated")
        
        # Gate 4: No SLAM in defensive mode
        if (self.defensive_mode and 
            self.defensive_mode.defensive_mode and 
            self.defensive_mode.max_allowed_tier != "SLAM"):
            # This is enforced, not a violation
            pass
    
    @property
    def render_gate_passed(self) -> bool:
        """Check if all render gates passed."""
        return len(self._render_gate_violations) == 0
    
    @property
    def render_gate_violations(self) -> List[str]:
        """Get list of render gate violations."""
        return self._render_gate_violations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "slate_quality": self.slate_quality.to_dict() if self.slate_quality else None,
            "api_health": self.api_health.to_dict() if self.api_health else None,
            "defensive_mode": self.defensive_mode.to_dict() if self.defensive_mode else None,
            "rejection_summary": self.rejection_summary.to_dict() if self.rejection_summary else None,
            "render_gate_passed": self.render_gate_passed,
            "render_gate_violations": self._render_gate_violations
        }
        return result
    
    def get_report_header(self) -> str:
        """
        Generate the report header with defensive mode banner if active.
        
        Returns:
            Formatted header string for reports
        """
        lines = []
        
        # Slate quality line
        sq = self.slate_quality
        lines.append(f"Slate Quality: {sq.score}/100 ({sq.grade})")
        
        # API health line
        ah = self.api_health
        if ah.status != "HEALTHY":
            lines.append(f"API Health: {ah.status} ({ah.health:.0%})")
        
        # Defensive mode banner
        if self.defensive_mode.defensive_mode:
            lines.append("")
            lines.append(self.defensive_mode.banner_text)
        
        return "\n".join(lines)


def compute_slate_controls(
    results: List[Dict[str, Any]],
    api_health_override: Optional[float] = None,
    require_summary_threshold: int = 200
) -> SlateControlsResult:
    """
    Compute all slate quality controls from analysis results.
    
    This is the MAIN ENTRY POINT for the slate quality system.
    Call this after analyzing all props but before rendering the report.
    
    Args:
        results: List of analysis result dicts
        api_health_override: Optional override for API health (0-1)
        require_summary_threshold: NO PLAY count threshold for requiring summary
    
    Returns:
        SlateControlsResult with all quality controls computed
    
    Example:
        results = [analyze_prop_with_gates(p) for p in props]
        controls = compute_slate_controls(results)
        
        if not controls.render_gate_passed:
            raise RuntimeError(f"Render gate failed: {controls.render_gate_violations}")
        
        print(controls.get_report_header())
    """
    # Step 1: Compute API health
    if api_health_override is not None:
        api_health_result = APIHealthResult(
            health=api_health_override,
            status="HEALTHY" if api_health_override >= 0.9 else "DEGRADED" if api_health_override >= 0.7 else "CRITICAL",
            failures=0,
            successes=0,
            degradation_reason=None,
            confidence_multiplier=api_health_override
        )
    else:
        api_health_result = compute_api_health()
    
    # Step 2: Compute slate context from results
    slate_context = compute_slate_context_from_results(
        results, 
        api_health=api_health_result.health
    )
    
    # Step 3: Compute slate quality
    slate_quality_result = compute_slate_quality(slate_context)
    
    # Step 4: Count NO PLAY decisions
    no_play_decisions = ["NO_PLAY", "NO PLAY", "PASS", "BLOCKED", "SKIP"]
    no_play_count = sum(
        1 for r in results 
        if r.get("decision", "").upper() in no_play_decisions
    )
    no_play_ratio = no_play_count / len(results) if results else 0
    
    # Step 5: Evaluate defensive mode
    defensive_mode_result = evaluate_defensive_mode(
        slate_quality=slate_quality_result.score,
        api_health=api_health_result.health,
        injury_density=slate_context["injury_density"],
        no_play_ratio=no_play_ratio
    )
    
    # Step 6: Generate rejection summary if needed
    if no_play_count > require_summary_threshold:
        rejection_summary = require_rejection_summary(
            no_play_count=no_play_count,
            results=results,
            threshold=require_summary_threshold
        )
    else:
        rejection_summary = None
    
    # Step 7: Build unified result
    controls = SlateControlsResult(
        slate_quality=slate_quality_result,
        api_health=api_health_result,
        defensive_mode=defensive_mode_result,
        rejection_summary=rejection_summary
    )
    
    logger.info(
        f"Slate controls computed: Quality={slate_quality_result.score}/100, "
        f"Defensive={defensive_mode_result.defensive_mode}, "
        f"RenderGate={'PASS' if controls.render_gate_passed else 'FAIL'}"
    )
    
    return controls
