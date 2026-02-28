"""
UGO Integration Validator
=========================
Validates that all 6 sport pipelines export Universal Governance Object format.

Usage:
    python scripts/validate_ugo_integration.py
"""

from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Pipeline files to check
PIPELINE_FILES = {
    "NBA": "risk_first_analyzer.py",
    "CBB": "sports/cbb/run_daily.py",
    "NFL": "run_autonomous.py",
    "TENNIS": "tennis/run_daily.py",
    "SOCCER": "soccer/soccer_props_pipeline.py",
    "GOLF": "golf/run_daily.py",
}

# Required integration patterns
REQUIRED_PATTERNS = [
    "from core.universal_governance_object import",
    "adapt_edge",
    "Sport.",
    "ugo_edges",
]


def check_file_integration(filepath: Path) -> Tuple[bool, List[str]]:
    """Check if a file has UGO integration."""
    if not filepath.exists():
        return False, [f"File not found: {filepath}"]
    
    content = filepath.read_text(encoding="utf-8")
    issues = []
    
    for pattern in REQUIRED_PATTERNS:
        if pattern not in content:
            issues.append(f"Missing pattern: {pattern}")
    
    return len(issues) == 0, issues


def main():
    print("\n" + "=" * 70)
    print("UGO INTEGRATION VALIDATION")
    print("=" * 70)
    print()
    
    results: Dict[str, Tuple[bool, List[str]]] = {}
    
    for sport, rel_path in PIPELINE_FILES.items():
        filepath = PROJECT_ROOT / rel_path
        passed, issues = check_file_integration(filepath)
        results[sport] = (passed, issues)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"[{sport:7s}] {status} — {rel_path}")
        
        if not passed:
            for issue in issues:
                print(f"          • {issue}")
    
    print()
    print("=" * 70)
    
    passed_count = sum(1 for passed, _ in results.values() if passed)
    total_count = len(results)
    
    if passed_count == total_count:
        print(f"✅ ALL {total_count} PIPELINES INTEGRATED")
        print()
        print("Next steps:")
        print("  1. Run any sport pipeline (e.g., .venv\\Scripts\\python.exe risk_first_analyzer.py)")
        print("  2. Check for 'ugo_edges' field in output JSON")
        print("  3. Verify UGO fields: mu, sigma, edge_std, sport, direction, tier")
        return 0
    else:
        print(f"❌ {total_count - passed_count}/{total_count} PIPELINES MISSING INTEGRATION")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
