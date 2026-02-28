"""
Enforcement Matrix — Unified Export Layer
==========================================
LAYER E — Final enforcement before export.

ENFORCEMENT MATRIX:
| Layer            | Can Change Math? | Can Change Tier? | Can Hide Edge? |
|------------------|------------------|------------------|----------------|
| Core Engine      | ✅               | ✅               | ❌             |
| Validation Gate  | ❌               | ❌               | ✅             |
| Dashboard Export | ❌               | ❌               | ❌             |
| Frontend UI      | ❌               | ❌               | ❌             |

**Truth only flows one direction.**

This module combines all enforcement layers (A-D) into a single export pipeline.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import enforcement layers
from engine.parlay_eligibility import (
    enrich_edges_with_parlay_data,
    evaluate_edge_eligibility,
    BlockReason,
)
from render.mobile_condensed import (
    MobileViewRenderer,
    edge_to_condensed,
)
from render.daily_diff import (
    diff_edges,
    render_diff_text,
    DailyDiff,
)
from render.calibration_dashboard import (
    CalibrationEngine,
    CalibrationPoint,
    enrich_edge_with_calibration,
    render_calibration_table,
    CALIBRATION_ERROR_THRESHOLD,
)


# =============================================================================
# ENFORCEMENT FLAGS
# =============================================================================

@dataclass
class EnforcementFlags:
    """System-wide enforcement flags."""
    calibration_warning: bool = False
    calibration_reason: Optional[str] = None
    
    drift_detected: bool = False
    drift_reason: Optional[str] = None
    
    blocked_parlays_count: int = 0
    total_edges: int = 0
    optimizable_edges: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "calibration_warning": self.calibration_warning,
            "calibration_reason": self.calibration_reason,
            "drift_detected": self.drift_detected,
            "drift_reason": self.drift_reason,
            "blocked_parlays_count": self.blocked_parlays_count,
            "total_edges": self.total_edges,
            "optimizable_edges": self.optimizable_edges,
        }


# =============================================================================
# ENRICHED EXPORT
# =============================================================================

@dataclass
class EnrichedExport:
    """
    Complete enriched edge export with all enforcement layers.
    
    Contains:
    - edges: Full enriched edges (parlay + calibration data)
    - mobile_view: Condensed rows for mobile
    - daily_diff: Changes since yesterday
    - calibration_report: Full calibration state
    - enforcement_flags: System warnings
    """
    generated_at: str
    sport: str
    
    edges: List[Dict] = field(default_factory=list)
    
    # Mobile view
    mobile_compact: str = ""
    mobile_by_tier: str = ""
    mobile_rows: List[Dict] = field(default_factory=list)
    
    # Daily diff
    daily_diff: Optional[Dict] = None
    diff_summary: str = ""
    
    # Calibration
    calibration: Optional[Dict] = None
    calibration_summary: str = ""
    
    # Enforcement
    flags: EnforcementFlags = field(default_factory=EnforcementFlags)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "sport": self.sport,
            "edges": self.edges,
            "mobile": {
                "compact": self.mobile_compact,
                "by_tier": self.mobile_by_tier,
                "rows": self.mobile_rows,
            },
            "daily_diff": self.daily_diff,
            "calibration": self.calibration,
            "flags": self.flags.to_dict(),
        }


# =============================================================================
# EXPORT PIPELINE
# =============================================================================

class EnforcementPipeline:
    """
    Single pipeline that applies all enforcement layers.
    
    Usage:
        pipeline = EnforcementPipeline()
        export = pipeline.process(edges, yesterday_edges, calibration_picks)
    """
    
    def __init__(self, sport: str = "NBA"):
        self.sport = sport
        self.calibration_engine = CalibrationEngine()
    
    def load_calibration_history(self, picks: List[CalibrationPoint]):
        """Load historical picks for calibration."""
        for pick in picks:
            self.calibration_engine.add_pick(pick)
    
    def process(
        self,
        edges: List[Dict],
        yesterday_edges: List[Dict] = None,
        calibration_picks: List[CalibrationPoint] = None,
    ) -> EnrichedExport:
        """
        Process edges through all enforcement layers.
        
        Args:
            edges: Today's edges
            yesterday_edges: Yesterday's edges for diff (optional)
            calibration_picks: Historical picks for calibration (optional)
            
        Returns:
            EnrichedExport with all enforcement data
        """
        export = EnrichedExport(
            generated_at=datetime.now().isoformat(),
            sport=self.sport,
        )
        
        # Load calibration if provided
        if calibration_picks:
            self.load_calibration_history(calibration_picks)
        
        # Initialize flags
        export.flags.total_edges = len(edges)
        
        # =====================================================================
        # LAYER A: Parlay Eligibility
        # =====================================================================
        edges_with_parlay = enrich_edges_with_parlay_data(edges)
        
        # Count blocked
        blocked = sum(
            1 for e in edges_with_parlay
            if not e.get("parlay", {}).get("allowed", True)
        )
        export.flags.blocked_parlays_count = blocked
        
        # Count optimizable
        optimizable = sum(
            1 for e in edges_with_parlay
            if e.get("pick_state", "").upper() == "OPTIMIZABLE"
            or (e.get("tier", "").upper() not in {"NO_PLAY", "NO PLAY", "AVOID", "REJECTED"})
        )
        export.flags.optimizable_edges = optimizable
        
        # =====================================================================
        # LAYER D: Calibration Enrichment
        # =====================================================================
        if self.calibration_engine.picks:
            edges_with_calibration = [
                enrich_edge_with_calibration(e, self.calibration_engine)
                for e in edges_with_parlay
            ]
            
            # Generate calibration report
            cal_report = self.calibration_engine.generate_report()
            export.calibration = cal_report.to_dict()
            export.calibration_summary = render_calibration_table(cal_report)
            
            # Check for recalibration warning
            if cal_report.needs_recalibration:
                export.flags.calibration_warning = True
                export.flags.calibration_reason = cal_report.recalibration_reason
        else:
            edges_with_calibration = edges_with_parlay
        
        export.edges = edges_with_calibration
        
        # =====================================================================
        # LAYER B: Mobile View
        # =====================================================================
        renderer = MobileViewRenderer(export.edges)
        export.mobile_compact = renderer.render_compact_list(include_emoji=True)
        export.mobile_by_tier = renderer.render_by_tier()
        export.mobile_rows = [row.to_dict() for row in renderer.rows]
        
        # =====================================================================
        # LAYER C: Daily Diff
        # =====================================================================
        if yesterday_edges:
            diff = diff_edges(export.edges, yesterday_edges)
            export.daily_diff = diff.to_dict()
            export.diff_summary = render_diff_text(diff)
            
            # Check for drift indicators
            if diff.removed_edges and len(diff.removed_edges) > len(edges) * 0.3:
                export.flags.drift_detected = True
                export.flags.drift_reason = f"{len(diff.removed_edges)} edges removed (>30%)"
        
        return export


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def enrich_and_export(
    edges: List[Dict],
    sport: str = "NBA",
    yesterday_file: Path = None,
    output_file: Path = None,
) -> EnrichedExport:
    """
    One-shot enrichment and export.
    
    Args:
        edges: Today's edges
        sport: Sport identifier
        yesterday_file: Path to yesterday's signals JSON
        output_file: Path to write enriched export
        
    Returns:
        EnrichedExport
    """
    pipeline = EnforcementPipeline(sport=sport)
    
    # Load yesterday if available
    yesterday_edges = []
    if yesterday_file and yesterday_file.exists():
        with open(yesterday_file, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                yesterday_edges = data
            elif isinstance(data, dict):
                yesterday_edges = data.get("edges", data.get("signals", []))
    
    export = pipeline.process(edges, yesterday_edges)
    
    # Write output if requested
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(export.to_dict(), f, indent=2)
    
    return export


def print_enforcement_summary(export: EnrichedExport):
    """Print human-readable enforcement summary."""
    print("=" * 70)
    print("🔒 ENFORCEMENT MATRIX SUMMARY")
    print("=" * 70)
    
    flags = export.flags
    
    print(f"\n📊 Edge Counts:")
    print(f"   Total edges: {flags.total_edges}")
    print(f"   Optimizable: {flags.optimizable_edges}")
    print(f"   Parlay-blocked: {flags.blocked_parlays_count}")
    
    if flags.calibration_warning:
        print(f"\n⚠️  CALIBRATION WARNING:")
        print(f"   {flags.calibration_reason}")
    else:
        print(f"\n✅ Calibration: OK")
    
    if flags.drift_detected:
        print(f"\n⚠️  DRIFT DETECTED:")
        print(f"   {flags.drift_reason}")
    else:
        print(f"\n✅ Drift: None detected")
    
    print("\n" + "-" * 70)
    print("Truth flow: Core Engine → Validation Gate → Dashboard Export → UI")
    print("-" * 70)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Test with sample edges
    test_edges = [
        {
            "edge_id": "maxey_pts_1",
            "player": "Tyrese Maxey",
            "stat": "points",
            "line": 25.5,
            "direction": "higher",
            "probability": 0.68,
            "tier": "STRONG",
            "pick_state": "OPTIMIZABLE",
        },
        {
            "edge_id": "sengun_reb_1",
            "player": "Alperen Sengun",
            "stat": "rebounds",
            "line": 10.5,
            "direction": "higher",
            "probability": 0.62,
            "tier": "STRONG",
            "pick_state": "OPTIMIZABLE",
        },
        {
            "edge_id": "sengun_td_1",
            "player": "Alperen Sengun",
            "stat": "triple_double",
            "line": 0.5,
            "direction": "under",
            "probability": 0.09,
            "tier": "NO_PLAY",
            "pick_state": "REJECTED",
            "risk_tags": ["rare_event", "triple_double"],
        },
        {
            "edge_id": "jokic_reb_1",
            "player": "Nikola Jokic",
            "stat": "rebounds",
            "line": 12.5,
            "direction": "higher",
            "probability": 0.72,
            "tier": "SLAM",
            "pick_state": "OPTIMIZABLE",
        },
    ]
    
    # Yesterday's edges (for diff)
    yesterday_edges = [
        {
            "edge_id": "maxey_pts_1",
            "player": "Tyrese Maxey",
            "stat": "points",
            "line": 25.5,
            "direction": "higher",
            "probability": 0.72,  # Was higher
            "tier": "SLAM",       # Was SLAM
        },
        {
            "edge_id": "embiid_pts_1",
            "player": "Joel Embiid",
            "stat": "points",
            "line": 32.5,
            "direction": "higher",
            "probability": 0.65,
            "tier": "SLAM",
        },
    ]
    
    # Run pipeline
    pipeline = EnforcementPipeline(sport="NBA")
    export = pipeline.process(test_edges, yesterday_edges)
    
    # Print summary
    print_enforcement_summary(export)
    
    # Print mobile view
    print("\n📱 MOBILE CONDENSED VIEW:")
    print(export.mobile_compact)
    
    # Print diff
    print("\n" + export.diff_summary)
    
    # Export JSON
    print("\n" + "=" * 70)
    print("JSON EXPORT (truncated):")
    print("=" * 70)
    print(json.dumps(export.to_dict(), indent=2)[:2000] + "...")
