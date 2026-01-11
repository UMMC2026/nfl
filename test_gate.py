"""Test the new pre-output verification system"""
import subprocess
import sys
from pathlib import Path

workspace = Path(__file__).parent

print("\n" + "="*70)
print("  PRE-OUTPUT VERIFICATION SYSTEM TEST")
print("="*70 + "\n")

print("[*] Running verification_gate.py on picks_hydrated.json...")
result = subprocess.run(
    [sys.executable, "verification_gate.py"],
    cwd=workspace,
    capture_output=True,
    text=True,
    timeout=60
)

print("\n" + "="*70)
if result.returncode == 0:
    print("✅ VERIFICATION PASSED")
else:
    print(f"❌ VERIFICATION FAILED (exit code: {result.returncode})")

print("="*70)

# Show output
lines = result.stdout.split('\n')
for line in lines[:60]:  # First 60 lines
    print(line)

if result.stderr:
    print("\n⚠️ STDERR:")
    print(result.stderr[:500])

print("\n[*] Check outputs/ folder for verification report JSON")
