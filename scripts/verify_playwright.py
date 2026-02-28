#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""scripts/verify_playwright.py

Playwright environment verification for the prop scraper pipeline.

This is a *pre-flight* check: it validates that the active Python environment
is the repo venv, Playwright is importable, Chromium is available, and the
pipeline directories are writable.

Design goals:
- Fail-fast with actionable messages
- Avoid reliance on PATH (uses `python -m playwright`)
- No network access required
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


def _is_windows() -> bool:
    return os.name == "nt"


def _venv_expected_python(repo_root: Path) -> Path:
    if _is_windows():
        return repo_root / ".venv" / "Scripts" / "python.exe"
    return repo_root / ".venv" / "bin" / "python"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def verify_environment() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    checks: dict[str, bool] = {
        "venv_python": False,
        "playwright_package": False,
        "chromium_installed": False,
        "profile_directory": False,
        "write_permissions": False,
        "parquet_stack": False,
    }

    # Check 0: Running under .venv
    expected = _venv_expected_python(repo_root)
    try:
        exe = Path(sys.executable).resolve()
    except Exception:
        exe = Path(sys.executable)

    if expected.exists() and exe == expected.resolve():
        checks["venv_python"] = True
        print(f"✔ Using venv interpreter: {exe}")
    else:
        print("⚠ Not running under the repo .venv interpreter")
        print(f"  Current:  {exe}")
        print(f"  Expected: {expected} (if present)")
        # Not strictly fatal, but it explains most dependency issues.
        checks["venv_python"] = expected.exists() is False

    # Check 1: Python package
    try:
        import playwright  # noqa: F401

        checks["playwright_package"] = True
        print("✔ Playwright package installed")
    except Exception as e:
        print("✗ Playwright package missing or broken")
        print(f"  Error: {e}")

    # Check 2: Browser binaries (Chromium)
    try:
        # Avoid relying on PATH: call through the active interpreter.
        result = _run([sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"])
        out = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode == 0:
            checks["chromium_installed"] = True
            print("✔ Chromium install check passed")
        else:
            print("✗ Chromium install check failed")
            print(out.strip()[:2000])
    except Exception as e:
        print(f"✗ Browser check failed: {e}")

    # Check 3: Persistent profile directory
    profile_path = repo_root / "chrome_profile"
    if profile_path.exists():
        print(f"✔ Chrome profile exists: {profile_path}")
        checks["profile_directory"] = True
    else:
        print("⚠ Chrome profile missing (will create on first run)")
        checks["profile_directory"] = True

    # Check 4: Write permissions
    data_dir = repo_root / "data" / "raw" / "scraped"
    data_dir.mkdir(parents=True, exist_ok=True)
    test_file = data_dir / ".write_test"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        checks["write_permissions"] = True
        print(f"✔ Write permissions verified: {data_dir}")
    except Exception as e:
        print(f"✗ Cannot write to data directory: {e}")

    # Check 5: Parquet stack (validator output)
    try:
        import pandas  # noqa: F401
        import pyarrow  # noqa: F401

        checks["parquet_stack"] = True
        print("✔ Parquet stack available (pandas + pyarrow)")
    except Exception as e:
        print("✗ Parquet stack missing (pandas + pyarrow)")
        print(f"  Error: {e}")

    if all(checks.values()):
        print("\n✅ All checks passed — scraper ready")
        return 0

    print("\n❌ Environment setup incomplete")
    for k, v in checks.items():
        if not v:
            print(f"  - FAILED: {k}")
    return 1


if __name__ == "__main__":
    raise SystemExit(verify_environment())
