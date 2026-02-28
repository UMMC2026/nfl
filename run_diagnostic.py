# run_diagnostic.py
"""
Runner script for the ultimate diagnostic
"""

import subprocess
import os
from pathlib import Path
import time

def run_ultimate_diagnostic():
    """Run the ultimate diagnostic from project root"""
    print("🏈 NFL Cheatsheet Generator - Ultimate Diagnostic Runner")
    print("="*70)
    
    # Get paths
    project_root = Path(__file__).parent.absolute()
    print(f"Project root: {project_root}")
    
    # Find the diagnostic script
    diagnostic_script = project_root / "tools" / "cheatsheet_pro_generator.py"
    if not diagnostic_script.exists():
        print(f"❌ Diagnostic script not found at: {diagnostic_script}")
        # Try to find it
        for path in project_root.rglob("cheatsheet_pro_generator.py"):
            diagnostic_script = path
            print(f"✅ Found at: {diagnostic_script}")
            break
    
    print(f"Diagnostic script: {diagnostic_script}")
    
    # Change to project root
    original_cwd = os.getcwd()
    os.chdir(project_root)
    print(f"Changed to: {os.getcwd()}")
    
    # Run the diagnostic
    print(f"\n{'='*70}")
    print("🚀 RUNNING ULTIMATE DIAGNOSTIC")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Run with subprocess to capture ALL output
        result = subprocess.run(
            ["python", str(diagnostic_script)],
            capture_output=True,
            text=True,
            timeout=60,
            shell=True
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Execution time: {elapsed:.1f} seconds")
        print(f"📤 Return code: {result.returncode}")
        
        # Save output to file
        output_file = project_root / "DIAGNOSTIC_OUTPUT.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
        
        print(f"📄 Full output saved to: {output_file}")
        
        # Show key parts
        print(f"\n{'='*70}")
        print("KEY OUTPUT (last 50 lines):")
        print(f"{'='*70}")
        
        lines = result.stdout.split('\n')
        for line in lines[-50:]:
            if line.strip():
                print(line)
        
        # Check for success indicators
        success_words = ["SUCCESS", "FILES CREATED", "✅", "VERIFIED"]
        error_words = ["FAILED", "❌", "ERROR", "CRITICAL"]
        
        success_count = sum(1 for word in success_words if word in result.stdout.upper())
        error_count = sum(1 for word in error_words if word in result.stdout.upper())
        
        print(f"\n{'='*70}")
        print("QUICK ANALYSIS:")
        print(f"   Success indicators: {success_count}")
        print(f"   Error indicators: {error_count}")
        
        if success_count > error_count:
            print(f"   👍 Likely SUCCESSFUL")
        else:
            print(f"   👎 Likely FAILED")
        
        # Check what files were actually created
        print(f"\n{'='*70}")
        print("ACTUAL FILES CREATED:")
        print(f"{'='*70}")
        
        check_dirs = [
            project_root / "outputs" / "cheatsheets",
            project_root / "outputs" / "telegram",
            project_root / "logs",
            project_root
        ]
        
        for check_dir in check_dirs:
            if check_dir.exists():
                print(f"\n📁 {check_dir.relative_to(project_root)}/")
                files = list(check_dir.glob("*"))
                if files:
                    for f in files:
                        size = f.stat().st_size if f.exists() else 0
                        print(f"   • {f.name} ({size:,} bytes)")
                else:
                    print(f"   (empty)")
            else:
                print(f"\n❌ {check_dir.relative_to(project_root)}/ - DOES NOT EXIST")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Diagnostic timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running diagnostic: {e}")
        return False
    finally:
        # Restore original directory
        os.chdir(original_cwd)

if __name__ == "__main__":
    print("Starting NFL Cheatsheet Generator Diagnostic...")
    print("This will test file creation in ALL possible locations.")
    print()
    
    success = run_ultimate_diagnostic()
    
    print(f"\n{'='*70}")
    if success:
        print("🎉 DIAGNOSTIC RUNNER: COMPLETED (check output above)")
    else:
        print("❌ DIAGNOSTIC RUNNER: ENCOUNTERED ISSUES")
    
    print(f"\nNext steps:")
    print(f"1. Check {Path(__file__).parent}/outputs/ directory")
    print(f"2. Look for DIAGNOSTIC_OUTPUT.txt")
    print(f"3. Check desktop for NFL_DIAGNOSTIC_SUMMARY.txt")
    
    input("\nPress Enter to exit...")
