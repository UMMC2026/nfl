#!/usr/bin/env python3
"""
SOP Bootstrap - Install dependencies and lock environment.
Run this ONCE when setting up the workspace.
"""
import subprocess
import sys
import os
from pathlib import Path

print("\n" + "="*70)
print("UNDERDOG FANTASY ANALYZER - SOP BOOTSTRAP")
print("="*70 + "\n")

# 1. Check Python path
expected = r"C:\Users\hiday\UNDERDOG ANANLYSIS\.venv\Scripts\python.exe"
if sys.executable.lower() != expected.lower():
    print(f"❌ Wrong Python!")
    print(f"   Expected: {expected}")
    print(f"   Got:      {sys.executable}")
    print(f"\nFix: Run from .venv:")
    print(f"   .venv\\Scripts\\python.exe sop_bootstrap.py")
    sys.exit(1)

print(f"✅ Python locked: {sys.executable}")
print()

# 2. Check requirements.txt exists
if not Path("requirements.txt").exists():
    print("❌ requirements.txt not found")
    sys.exit(1)
print("✅ requirements.txt found")
print()

# 3. Install dependencies
print("📦 Installing dependencies from requirements.txt...")
print("   (This may take 1-2 minutes)")
print()

result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"❌ Installation failed:")
    print(result.stderr)
    sys.exit(1)

print("✅ Dependencies installed")
print()

# 4. Verify key packages
print("🔍 Verifying key packages...")

packages = {
    "telegram": "13.15",
    "fastapi": "0.115.6",
    "sqlalchemy": "2.0.36",
    "pydantic": "2.10.4",
    "stripe": "14.1.0"
}

all_good = True
for pkg_name, expected_version in packages.items():
    try:
        mod = __import__(pkg_name.replace("-", "_"))
        actual_version = getattr(mod, "__version__", "unknown")
        if expected_version in actual_version or actual_version == expected_version:
            print(f"   ✅ {pkg_name}: {actual_version}")
        else:
            print(f"   ⚠️  {pkg_name}: expected {expected_version}, got {actual_version}")
    except ImportError:
        print(f"   ❌ {pkg_name}: NOT INSTALLED")
        all_good = False

print()

# 5. Check .env
if not Path(".env").exists():
    print("⚠️  .env not found")
    print("   Create from .env.example and add TELEGRAM_BOT_TOKEN")
    print()
else:
    print("✅ .env configured")
    print()

# 6. Summary
print("="*70)
print("✅ SOP BOOTSTRAP COMPLETE")
print("="*70)
print()
print("Next steps:")
print("  1. Verify setup: python verify_runtime.py")
print("  2. Start bot:    python start_bot.py")
print()
