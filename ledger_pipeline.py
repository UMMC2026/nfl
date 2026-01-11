#!/usr/bin/env python3
"""
LEDGER PIPELINE INTEGRATION
===========================

Connects resolution steps:
1. load_game_results.py (fetch final stats)
2. generate_resolved_ledger.py (grade and report)

Run this AFTER daily cheatsheet is generated and games have finalized.
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime


def run_command(cmd: list, description: str) -> bool:
    """Execute a subprocess command and return success."""
    print(f"\n▶️  {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✓ {description} complete")
            return True
        else:
            print(f"   ✗ {description} failed")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"   ✗ Exception: {e}")
        return False


def main():
    """Orchestrate ledger pipeline."""
    print("=" * 70)
    print("RESOLVED LEDGER PIPELINE")
    print("=" * 70)
    
    workspace = Path.cwd()
    python = ".venv\\Scripts\\python.exe"
    
    # Step 1: Load game results
    print("\n📊 STEP 1: Fetch Final Game Results")
    success = run_command(
        [python, "load_game_results.py"],
        "Load game results from ESPN"
    )
    if not success:
        print("   ⚠️  (May have no games finalized yet)")
    
    # Step 2: Generate resolved ledger
    print("\n📈 STEP 2: Grade Picks & Generate Ledger")
    success = run_command(
        [python, "generate_resolved_ledger.py"],
        "Generate resolved performance ledger"
    )
    if not success:
        print("\n❌ Ledger generation failed")
        return 1
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ LEDGER PIPELINE COMPLETE")
    print("=" * 70)
    print("\nOutputs:")
    print("  📈 CSV Ledger:    reports/resolved_ledger.csv (machine truth)")
    print("  📝 MD Report:     reports/RESOLVED_PERFORMANCE_LEDGER.md (human truth)")
    print("  💾 JSON Snapshot: reports/resolved_YYYY-MM-DD.json (daily rollup)")
    print("\nNext: Check reports/ for daily performance truth.")
    
    return 0


if __name__ == "__main__":
    exit(main())
