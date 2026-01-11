#!/usr/bin/env python
"""
Daily workflow wrapper - runs complete pick analysis pipeline
Usage: python scripts/daily_workflow.py
"""
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Fix encoding for Windows console
os.environ['PYTHONIOENCODING'] = 'utf-8'


def run_command(cmd_list, description: str) -> bool:
    """Run a subprocess command and report results."""
    print(f"\n[*] {description}...")
    try:
        result = subprocess.run(cmd_list, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("[OK] Success")
            return True
        else:
            print(f"[!] Failed with code {result.returncode}")
            if result.stderr:
                # Show last line of error
                errors = result.stderr.split('\n')
                print(f"     {errors[-2] if len(errors) > 1 else result.stderr[:100]}")
            return False
    except Exception as e:
        print(f"[!] Error: {str(e)[:80]}")
        return False


def main():
    """Execute the complete daily workflow."""
    workspace = Path(__file__).parent.parent
    
    print("\n" + "="*70)
    print(f"  UNDERDOG FANTASY ANALYZER - DAILY WORKFLOW")
    print(f"  {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    print("="*70)
    
    # Step 0: Refresh rosters for current data (NEW)
    print("\n[*] Step 0: Refreshing NBA rosters...")
    step0 = run_command(
        [sys.executable, str(workspace / "scripts" / "refresh_rosters.py")],
        "Fetching current NBA rosters"
    )
    if not step0:
        print("⚠️  Roster refresh failed - continuing with cached data")
    
    # Step 1: Use cached hydration (or hydrate if needed)
    print("\n[*] Step 1: Using cached hydration data...")
    hydrated_file = workspace / "picks_hydrated.json"
    if hydrated_file.exists():
        print(f"[OK] Found {hydrated_file.name} - using cached data")
        # Only hydrate if picks.json is newer than hydrated file
        picks_file = workspace / "picks.json"
        if picks_file.stat().st_mtime > hydrated_file.stat().st_mtime:
            print("[*] picks.json updated - refreshing hydration...")
            run_command(
                [sys.executable, "hydrate_new_picks.py"],
                "Hydrating picks with nba_api"
            )
    else:
        print("[!] No cached hydration - running full hydration...")
        run_command(
            [sys.executable, "hydrate_new_picks.py"],
            "Hydrating picks with nba_api (10-game rolling avg)"
        )
    
    # Step 2: Generate cheatsheet
    print("\n[*] Step 2: Generating cheatsheet...")
    step2 = run_command(
        [sys.executable, "generate_cheatsheet.py"],
        "Creating comprehensive cheatsheet"
    )
    if not step2:
        print("\n[!] Cheatsheet generation failed.")
        return False
    
    # Step 3: Generate analysis
    print("\n[*] Step 3: Analyzing picks for betting recommendations...")
    step3 = run_command(
        [sys.executable, "scripts/report_analyzer.py"],
        "Extracting top picks and bet sizing"
    )
    if not step3:
        print("[!] Analysis skipped (optional)")
    
    # Step 4: Smart validation (NEW - instant pick validation)
    print("\n[*] Step 4: Validating picks...")
    step4 = run_command(
        [sys.executable, "scripts/smart_validation.py"],
        "Running quick pick validation"
    )
    if not step4:
        print("[!] Validation skipped (optional)")
    
    # Step 5: PRE-OUTPUT VERIFICATION GATE (Critical data integrity check)
    print("\n[*] Step 5: Running verification gate...")
    step5 = run_command(
        [sys.executable, "verification_gate.py"],
        "Verifying data accuracy before output"
    )
    if not step5:
        print("❌ VERIFICATION FAILED - Review errors above")
        return False
    
    # Summary
    print("\n" + "="*70)
    print("  [OK] WORKFLOW COMPLETE!")
    print("="*70)
    
    # Find latest report
    outputs_dir = workspace / "outputs"
    if outputs_dir.exists():
        reports = sorted(
            outputs_dir.glob("CHEATSHEET_*_STATISTICAL.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if reports:
            latest = reports[0]
            print(f"\n[*] Latest Report: {latest.name}")
            
            # Show summary
            with open(latest, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Extract pick counts
                strong_count = content.count('💪') if '💪' in content else 0
                lean_count = content.count('📊') if '📊' in content else 0
                
                if strong_count == 0:
                    # Fall back to text search
                    if 'STRONG PLAYS' in content:
                        strong_count = content[content.find('STRONG PLAYS'):content.find('LEAN PLAYS')].count('•')
                    if 'LEAN PLAYS' in content:
                        lean_count = content[content.find('LEAN PLAYS'):content.find('OVERS')].count('•')
                
                print(f"    Strong Plays: {strong_count}")
                print(f"    Lean Plays: {lean_count}")
    
    print("\n[*] Ready for betting analysis!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
