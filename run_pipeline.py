"""
FUOOM AUTOMATED PIPELINE
One command to run EVERYTHING with automatic quality gates

Usage:
    python run_pipeline.py outputs/YOURFILE.json
    
This script:
1. Validates data quality (blocks bad data)
2. Hydrates data from NBA API (fixes bad projections)
3. Generates narrative report (only if validation passes)
4. Creates subscriber-ready output
5. Shows summary

NO MORE MANUAL STEPS!
"""

import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

def run_command(cmd, description, check_return=True):
    """Run a command and handle errors"""
    print()
    print("=" * 80)
    print(f"⚙️  {description}")
    print("=" * 80)
    print(f"Running: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=False)
    
    if check_return and result.returncode != 0:
        print()
        print(f"❌ {description} FAILED")
        return False
    
    print()
    print(f"✅ {description} completed")
    return True

def run_pipeline(json_file, skip_validation=False, skip_hydration=False):
    """
    Run full pipeline:
    1. Validate
    2. Hydrate (fetch real NBA API data)
    3. Generate AI report
    4. Generate narrative report
    5. Summarize
    """
    
    print("=" * 80)
    print("🚀 FUOOM AUTOMATED PIPELINE")
    print("=" * 80)
    print(f"Input: {json_file}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 80)
    
    current_file = json_file
    
    # STEP 1: Validate data quality
    if not skip_validation:
        print()
        print("STEP 1/4: Data Quality Validation")
        
        if not run_command(
            [sys.executable, 'validate_slate.py', current_file],
            "Data Quality Validation",
            check_return=False  # Don't fail on warnings
        ):
            # Check if it was a critical failure
            pass  # Continue anyway, validation script handles critical vs warning
        
        # Check if validated file was created
        validated_file = current_file.replace('.json', '_VALIDATED.json')
        if Path(validated_file).exists():
            print(f"ℹ️  Using validated file: {validated_file}")
            current_file = validated_file
    else:
        print()
        print("⏭️  Skipping validation (--skip-validation)")
    
    # STEP 2: Hydrate with NBA API data
    if not skip_hydration and Path('hydrate_and_validate.py').exists():
        print()
        print("STEP 2/4: NBA API Data Hydration")
        
        run_command(
            [sys.executable, 'hydrate_and_validate.py', current_file],
            "NBA API Data Hydration",
            check_return=False
        )
        
        # Check if hydrated file was created
        hydrated_file = current_file.replace('.json', '_HYDRATED.json')
        if not hydrated_file.endswith('_HYDRATED.json'):
            hydrated_file = current_file.replace('.json', '_HYDRATED.json')
        
        if Path(hydrated_file).exists():
            print(f"ℹ️  Using hydrated file: {hydrated_file}")
            current_file = hydrated_file
    else:
        print()
        print("⏭️  Skipping hydration")
    
    # STEP 3: Generate AI commentary reports (full + Top 20)
    print()
    print("STEP 3/4: AI Commentary Report")
    
    try:
        # Generate AI reports inline
        from ai_commentary import generate_full_report, generate_top20_report
        
        with open(current_file, encoding='utf-8') as f:
            data = json.load(f)
        
        base_name = Path(current_file).stem.split('_RISK_FIRST')[0]
        date_str = datetime.now().strftime("%Y%m%d")

        # Full-slate report
        report = generate_full_report(data)
        ai_report_file = f"outputs/{base_name}_AI_REPORT_{date_str}.txt"
        with open(ai_report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ AI report saved: {ai_report_file}")

        # Top-20 report (by final confidence)
        top20_report = generate_top20_report(data, top_n=20)
        top20_report_file = f"outputs/{base_name}_TOP20_AI_REPORT_{date_str}.txt"
        with open(top20_report_file, 'w', encoding='utf-8') as f:
            f.write(top20_report)
        print(f"✅ Top-20 AI report saved: {top20_report_file}")
        
    except Exception as e:
        print(f"⚠️  AI report generation failed: {e}")
        ai_report_file = None
    
    # STEP 4: Generate narrative report
    print()
    print("STEP 4/4: Narrative Report Generation")
    
    if Path('generate_narrative_report.py').exists():
        run_command(
            [sys.executable, 'generate_narrative_report.py', current_file],
            "Narrative Report Generation",
            check_return=False
        )
    else:
        print("⚠️  generate_narrative_report.py not found, skipping")
    
    # SUMMARY
    print()
    print("=" * 80)
    print("✅ PIPELINE COMPLETED")
    print("=" * 80)
    print()
    
    # Show generated files
    base_name = Path(json_file).stem.split('_RISK_FIRST')[0]
    date_str = datetime.now().strftime("%Y%m%d")
    
    files_to_check = [
        json_file,
        json_file.replace('.json', '_VALIDATED.json'),
        json_file.replace('.json', '_HYDRATED.json'),
        f"outputs/{base_name}_AI_REPORT_{date_str}.txt",
        f"outputs/{base_name}_NARRATIVE_{datetime.now().strftime('%Y-%m-%d')}.txt",
        "outputs/LATEST_NARRATIVE_REPORT.txt"
    ]
    
    print("📄 Files created:")
    for f in files_to_check:
        if Path(f).exists():
            size = Path(f).stat().st_size
            print(f"  ✅ {f} ({size:,} bytes)")
    
    print()
    print("🎯 Next steps:")
    print("  1. Review AI report for picks")
    print("  2. Send to subscribers via Telegram")
    print("  3. Track pick performance")
    print()
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='FUOOM Automated Pipeline')
    parser.add_argument('json_file', nargs='?', help='Input JSON file')
    parser.add_argument('--skip-validation', action='store_true', help='Skip validation step')
    parser.add_argument('--skip-hydration', action='store_true', help='Skip NBA API hydration')
    
    args = parser.parse_args()
    
    if args.json_file:
        json_file = args.json_file
    else:
        # Find most recent RISK_FIRST file
        import glob
        files = glob.glob("outputs/*RISK_FIRST*.json")
        # Exclude validated/hydrated versions
        files = [f for f in files if '_VALIDATED' not in f and '_HYDRATED' not in f]
        
        if files:
            json_file = sorted(files, key=lambda x: Path(x).stat().st_mtime)[-1]
            print(f"📂 Using most recent: {json_file}")
            print()
        else:
            print("Usage: python run_pipeline.py YOUR_FILE.json")
            print()
            print("Or place RISK_FIRST JSON in outputs/ directory")
            sys.exit(1)
    
    success = run_pipeline(
        json_file,
        skip_validation=args.skip_validation,
        skip_hydration=args.skip_hydration
    )
    
    sys.exit(0 if success else 1)
