#!/usr/bin/env python3
"""Run NBA council and generate a client-facing report.

Prerequisites:
- daily_pipeline.py has been run for NBA and outputs/validated_primary_edges.json exists.
- Oracle council and reporting modules are available in the current environment.

This script is non-invasive: it does NOT re-run the daily pipeline or modify
validated_primary_edges.json. It only reads that file, runs the NBA council,
and writes council decisions + a Markdown report.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Ensure project root is on sys.path for imports
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.io import load_json  # type: ignore
from oracle.council_cli import main as council_main  # type: ignore
from oracle.reporting.client_report import render_client_report  # type: ignore

try:  # Calibration is optional; report still works without it
    from calibration.unified_tracker import UnifiedCalibration  # type: ignore
except Exception:  # pragma: no cover - missing calibration infra
    UnifiedCalibration = None  # type: ignore


def _build_calibration_snapshot(sport: str) -> Optional[Dict]:
    """Best-effort calibration snapshot for the report.

    Uses UnifiedCalibration if available. Returns None if calibration
    data is missing or any error occurs.
    """

    if UnifiedCalibration is None:
        return None

    try:
        calib = UnifiedCalibration()
    except Exception:
        return None

    sport_key = sport.lower()
    if not getattr(calib, "picks", None):
        return None

    try:
        brier = calib.get_sport_brier(sport_key)
        threshold = calib.BRIER_THRESHOLDS.get(sport_key, 0.25)
        flags = calib.check_drift_flags(sport_key)
    except Exception:
        return None

    status = (
        "DRIFT DETECTED — review calibration"
        if flags.get("requires_recalibration")
        else "Calibration within acceptable range"
    )

    return {"brier": brier, "threshold": threshold, "status": status}


def run_nba_council_report() -> None:
    """Run NBA council on validated edges and emit a Markdown report.

    1) Reads outputs/validated_primary_edges.json (NBA daily pipeline output).
    2) Invokes oracle.council_cli for sport=nba to produce council decisions.
    3) Renders a client-facing Markdown report with optional calibration snapshot.
    """

    edges_path = ROOT / "outputs" / "validated_primary_edges.json"
    if not edges_path.exists():
        print("❌ outputs/validated_primary_edges.json not found. Run daily_pipeline.py for NBA first.")
        return

    council_out = ROOT / "outputs" / "nba_council_decisions.json"

    # Delegate grouping + SOP enforcement to the existing CLI entrypoint
    council_main(
        [
            "--sport",
            "nba",
            "--input-json",
            str(edges_path),
            "--output-json",
            str(council_out),
        ]
    )

    decisions = load_json(str(council_out))

    calib_snapshot = _build_calibration_snapshot("nba")
    report_md = render_client_report(decisions, sport="NBA", calibration_snapshot=calib_snapshot)

    reports_dir = ROOT / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = reports_dir / f"nba_council_report_{ts}.md"
    report_path.write_text(report_md, encoding="utf-8")

    print(f"[OK] Wrote {len(decisions)} NBA council decisions to {council_out}")
    print(f"[OK] Wrote NBA client report to {report_path}")


if __name__ == "__main__":
    run_nba_council_report()
