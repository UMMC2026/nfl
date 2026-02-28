#!/usr/bin/env python3
"""Phase 5 smoke checks.

Goal: quick confidence that Phase 5A (dashboards) + Phase 5D (infra) wiring works.

Checks:
- pick_history.db exists and schema is reachable
- dashboard app imports (no runtime import errors)
- legacy CSV sync script imports

Usage:
    .venv\\Scripts\\python.exe scripts/phase5_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root imports work when executing from /scripts
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    print("PHASE 5 SMOKE CHECK")
    print("-" * 60)

    # 1) DB existence / basic import
    from pick_history_db import PickHistoryDB

    db_path = Path("cache/pick_history.db")
    if not db_path.exists():
        print("⚠️  cache/pick_history.db not found (yet). That is OK on a fresh setup.")

    _ = PickHistoryDB()
    print("✅ PickHistoryDB import + init OK")

    # 2) Dashboard import
    from dashboard import app as dashboard_app  # noqa: F401

    print("✅ dashboard/app.py import OK")

    # 3) Sync script import
    import scripts.sync_legacy_calibration_csv_to_db as _sync  # noqa: F401

    print("✅ sync_legacy_calibration_csv_to_db import OK")

    print("\n✅ Smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
