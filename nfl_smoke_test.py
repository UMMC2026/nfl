"""
NFL Smoke Test Script
Runs a minimal pipeline for a known-passing NFL pick and prints the result.
"""
import subprocess
import sys

def main():
    print("\n=== NFL Smoke Test: Known-Passing Pick ===\n")
    cmd = [
        sys.executable, "daily_pipeline.py",
        "--league", "NFL",
        "--mode", "analysis",
        "--input-file", "picks_hydrated_user.json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 0:
        print("\n✅ NFL smoke test completed successfully.")
    else:
        print("\n❌ NFL smoke test failed. See output above.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
