"""
Render Layer — Presentation & Visibility Components
====================================================

This module provides enforcement + visibility layers that sit on top
of the core engine. No math changes — only rendering and audit.

Components:
- mobile_condensed.py: Mobile-first scan → decide → exit view
- daily_diff.py: What changed since yesterday
- calibration_dashboard.py: Brier scores, reliability curves, tier accuracy

ENFORCEMENT MATRIX:
| Layer            | Can Change Math? | Can Change Tier? | Can Hide Edge? |
|------------------|------------------|------------------|----------------|
| Core Engine      | ✅               | ✅               | ❌             |
| Validation Gate  | ❌               | ❌               | ✅             |
| Dashboard Export | ❌               | ❌               | ❌             |
| Frontend UI      | ❌               | ❌               | ❌             |

Truth only flows one direction.
"""

from .mobile_condensed import (
    MobileViewRenderer,
    CondensedRow,
    ExpandedDrawer,
    edge_to_condensed,
)

from .daily_diff import (
    DiffType,
    DiffItem,
    DailyDiff,
    diff_edges,
    render_diff_text,
)

from .calibration_dashboard import (
    CalibrationEngine,
    CalibrationPoint,
    CalibrationBucket,
    CalibrationReport,
    TierAccuracy,
    enrich_edge_with_calibration,
    render_calibration_table,
    render_reliability_curve_ascii,
    CALIBRATION_ERROR_THRESHOLD,
    BRIER_THRESHOLD,
)

__all__ = [
    # Mobile
    "MobileViewRenderer",
    "CondensedRow",
    "ExpandedDrawer",
    "edge_to_condensed",
    
    # Diff
    "DiffType",
    "DiffItem",
    "DailyDiff",
    "diff_edges",
    "render_diff_text",
    
    # Calibration
    "CalibrationEngine",
    "CalibrationPoint",
    "CalibrationBucket",
    "CalibrationReport",
    "TierAccuracy",
    "enrich_edge_with_calibration",
    "render_calibration_table",
    "render_reliability_curve_ascii",
    "CALIBRATION_ERROR_THRESHOLD",
    "BRIER_THRESHOLD",
]
