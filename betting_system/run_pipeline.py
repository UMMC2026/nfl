#!/usr/bin/env python3
"""
RUN_PIPELINE.PY — SOP v2.1 MASTER ORCHESTRATOR
===============================================
Enforces correct execution order. No shortcuts.

Usage:
    python run_pipeline.py [sport] [date]
    
Example:
    python run_pipeline.py NFL 2026-01-29
    python run_pipeline.py NBA 2026-01-29

Version: 2.1.0
Status: TRUTH-ENFORCED
"""

import subprocess
import sys
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

PIPELINE_STAGES = [
    {
        "name": "CLEAR_OUTPUTS",
        "script": None,  # Built-in
        "description": "Clear previous outputs",
        "required": True
    },
    {
        "name": "INGEST_DATA",
        "script": "ingest_data.py",
        "description": "Load and verify raw data",
        "required": True
    },
    {
        "name": "GENERATE_EDGES",
        "script": "generate_edges.py",
        "description": "Create raw lines from model",
        "required": True
    },
    {
        "name": "COLLAPSE_EDGES",
        "script": "collapse_edges.py",
        "description": "Collapse to unique edges (Rule A2)",
        "required": True
    },
    {
        "name": "SCORE_EDGES",
        "script": "score_edges.py",
        "description": "Apply confidence scoring",
        "required": True
    },
    {
        "name": "VALIDATE_OUTPUT",
        "script": "validate_output.py",
        "description": "HARD GATE — All SOP v2.1 checks",
        "required": True,
        "is_gate": True
    },
    {
        "name": "RENDER_REPORT",
        "script": "render_report.py",
        "description": "Generate final output",
        "required": True
    }
]

OUTPUTS_DIR = Path("outputs")
LOGS_DIR = Path("logs")


# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

def run_preflight_checks(sport: str) -> Dict:
    """
    VS Code Pre-Run Checklist (automated)
    
    Returns dict with check results
    """
    checks = {}
    
    # Check 1: outputs/ is clean
    if OUTPUTS_DIR.exists() and any(OUTPUTS_DIR.iterdir()):
        checks["outputs_clean"] = False
    else:
        checks["outputs_clean"] = True
    
    # Check 2: logs/ is clean (for this run)
    if LOGS_DIR.exists() and any(LOGS_DIR.iterdir()):
        checks["logs_clean"] = False
    else:
        checks["logs_clean"] = True
    
    # Check 3: Required scripts exist
    missing_scripts = []
    for stage in PIPELINE_STAGES:
        if stage["script"] and not Path(stage["script"]).exists():
            missing_scripts.append(stage["script"])
    checks["scripts_exist"] = len(missing_scripts) == 0
    checks["missing_scripts"] = missing_scripts
    
    # Check 4: Data sources available (placeholder)
    checks["data_sources_available"] = True  # Would check API health
    
    # Check 5: Injury feed health (placeholder)
    checks["injury_feed_healthy"] = True  # Would check feed status
    
    return checks


def clear_directories():
    """Clear outputs/ and logs/ for fresh run"""
    for dir_path in [OUTPUTS_DIR, LOGS_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# PIPELINE EXECUTION
# ============================================================================

class PipelineRunner:
    """
    Orchestrates the SOP v2.1 pipeline
    
    Guarantees:
    - Stages run in correct order
    - Failure at any stage halts pipeline
    - Validation gate must pass before render
    """
    
    def __init__(self, sport: str, date: str):
        self.sport = sport
        self.date = date
        self.run_id = f"{sport}_{date}_{datetime.now().strftime('%H%M%S')}"
        self.results = []
        self.start_time = None
        self.end_time = None
        
    def run(self) -> bool:
        """Execute full pipeline. Returns True if successful."""
        self.start_time = datetime.now()
        
        print("=" * 70)
        print(f"SOP v2.1 PIPELINE — {self.sport} — {self.date}")
        print(f"Run ID: {self.run_id}")
        print("=" * 70)
        
        # Pre-flight
        print("\n🔍 Running pre-flight checks...")
        checks = run_preflight_checks(self.sport)
        
        if checks.get("missing_scripts"):
            print(f"\n❌ MISSING SCRIPTS: {checks['missing_scripts']}")
            print("   Cannot proceed. Create missing scripts first.")
            return False
        
        # Clear outputs
        print("\n🧹 Clearing outputs/ and logs/...")
        clear_directories()
        
        # Run stages
        for stage in PIPELINE_STAGES:
            if stage["name"] == "CLEAR_OUTPUTS":
                continue  # Already done
            
            success = self._run_stage(stage)
            
            if not success:
                self._handle_failure(stage)
                return False
            
            # Special handling for validation gate
            if stage.get("is_gate"):
                print("\n✅ VALIDATION GATE PASSED — Safe to render")
        
        self.end_time = datetime.now()
        self._print_summary()
        return True
    
    def _run_stage(self, stage: Dict) -> bool:
        """Run a single pipeline stage"""
        print(f"\n{'='*60}")
        print(f"STAGE: {stage['name']}")
        print(f"Description: {stage['description']}")
        print("=" * 60)
        
        script = stage["script"]
        if not script:
            return True
        
        if not Path(script).exists():
            print(f"⚠️  Script not found: {script}")
            print(f"   Creating placeholder...")
            self._create_placeholder(script, stage["name"])
        
        # Run script
        try:
            result = subprocess.run(
                [sys.executable, script, self.sport, self.date],
                capture_output=True,
                text=True
            )
            
            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"STDERR: {result.stderr}")
            
            # Log result
            self.results.append({
                "stage": stage["name"],
                "script": script,
                "exit_code": result.returncode,
                "success": result.returncode == 0
            })
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Exception running {script}: {e}")
            self.results.append({
                "stage": stage["name"],
                "script": script,
                "exit_code": -1,
                "success": False,
                "error": str(e)
            })
            return False
    
    def _handle_failure(self, stage: Dict):
        """Handle pipeline failure"""
        print("\n" + "=" * 70)
        print(f"❌ PIPELINE FAILED AT: {stage['name']}")
        print("=" * 70)
        
        if stage.get("is_gate"):
            print("\nVALIDATION GATE BLOCKED OUTPUT")
            print("Review validation_report.json for details")
            print("\nDO NOT manually run render_report.py")
        else:
            print(f"\nFix {stage['script']} and re-run pipeline")
        
        # Save failure log
        self._save_run_log(success=False, failed_at=stage["name"])
    
    def _print_summary(self):
        """Print successful completion summary"""
        duration = (self.end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"\nRun ID: {self.run_id}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"\nStages completed: {len(self.results)}")
        for r in self.results:
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {r['stage']}")
        
        print(f"\n📁 Output files in: {OUTPUTS_DIR}/")
        if OUTPUTS_DIR.exists():
            for f in OUTPUTS_DIR.iterdir():
                print(f"   • {f.name}")
        
        self._save_run_log(success=True)
    
    def _save_run_log(self, success: bool, failed_at: Optional[str] = None):
        """Save run log for audit trail"""
        log = {
            "run_id": self.run_id,
            "sport": self.sport,
            "date": self.date,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "success": success,
            "failed_at": failed_at,
            "stages": self.results,
            "sop_version": "2.1"
        }
        
        log_file = LOGS_DIR / f"run_{self.run_id}.json"
        with open(log_file, "w") as f:
            json.dump(log, f, indent=2)
    
    def _create_placeholder(self, script: str, stage_name: str):
        """Create placeholder script that exits cleanly"""
        content = f'''#!/usr/bin/env python3
"""
{script} — PLACEHOLDER
Stage: {stage_name}

TODO: Implement this stage

This placeholder exits successfully for pipeline testing.
Replace with actual implementation.
"""

import sys
import json
from pathlib import Path

def main():
    sport = sys.argv[1] if len(sys.argv) > 1 else "NFL"
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-01-29"
    
    print(f"[PLACEHOLDER] {{stage_name}} for {{sport}} on {{date}}")
    print("TODO: Implement actual logic")
    
    # Create minimal output for next stage
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    
    # Exit success for pipeline testing
    sys.exit(0)

if __name__ == "__main__":
    main()
'''
        with open(script, "w") as f:
            f.write(content)
        print(f"   Created: {script}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Main entry point
    
    Usage: python run_pipeline.py [sport] [date]
    """
    sport = sys.argv[1] if len(sys.argv) > 1 else "NFL"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    
    # Validate sport
    valid_sports = ["NFL", "NBA", "WNBA", "CFB", "CBB", "BOXING", "TENNIS"]
    if sport.upper() not in valid_sports:
        print(f"❌ Invalid sport: {sport}")
        print(f"   Valid options: {', '.join(valid_sports)}")
        sys.exit(1)
    
    runner = PipelineRunner(sport.upper(), date)
    success = runner.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
