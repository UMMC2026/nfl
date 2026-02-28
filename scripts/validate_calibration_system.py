"""
Validation Script - Test Calibration System Upgrade
Verifies all components are installed correctly
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def validate_installation():
    """Validate all components of the calibration system upgrade"""
    
    print("\n" + "=" * 70)
    print("CALIBRATION SYSTEM VALIDATION")
    print("=" * 70)
    print()
    
    issues = []
    warnings = []
    
    # Check 1: Enhanced CalibrationPick class
    print("[1/5] Checking CalibrationPick schema...")
    try:
        from calibration.unified_tracker import CalibrationPick
        import inspect
        
        # Check for new fields
        required_fields = [
            'lambda_player', 'lambda_calculation', 'gap', 'z_score',
            'team', 'opponent', 'game_id',
            'prob_raw', 'prob_stat_capped', 'prob_global_capped', 'cap_applied',
            'model_version', 'edge', 'edge_type'
        ]
        
        sig = inspect.signature(CalibrationPick)
        params = list(sig.parameters.keys())
        
        missing = [f for f in required_fields if f not in params]
        
        if missing:
            issues.append(f"CalibrationPick missing fields: {missing}")
            print("  [FAIL] FAILED - Missing fields")
        else:
            print("  [PASS] PASS - All lambda tracking fields present")
    
    except ImportError as e:
        issues.append(f"Cannot import CalibrationPick: {e}")
        print("  [FAIL] FAILED - Import error")
    
    # Check 2: Calibration tracking in risk_first_analyzer.py
    print("[2/5] Checking prediction capture hook...")
    try:
        analyzer_file = Path(__file__).parent.parent / "risk_first_analyzer.py"
        with open(analyzer_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "ENABLE_CALIBRATION_TRACKING" in content and "cal.add_pick(pick)" in content:
            print("  [PASS] PASS - Prediction capture hook installed")
        else:
            issues.append("risk_first_analyzer.py missing calibration tracking hook")
            print("  [FAIL] FAILED - Hook not found")
    
    except Exception as e:
        issues.append(f"Cannot check risk_first_analyzer.py: {e}")
        print("  [FAIL] FAILED - File check error")
    
    # Check 3: Auto-resolve script
    print("[3/5] Checking auto-resolve NBA script...")
    auto_resolve_script = Path(__file__).parent / "auto_resolve_nba.py"
    if auto_resolve_script.exists():
        print("  [PASS] PASS - Auto-resolve script exists")
        
        # Check if nba_api is installed
        try:
            import nba_api
            print("      ✓ nba_api installed")
        except ImportError:
            warnings.append("nba_api not installed (pip install nba_api)")
            print("      [WARN]  nba_api not installed (optional)")
    else:
        issues.append("scripts/auto_resolve_nba.py not found")
        print("  [FAIL] FAILED - Script missing")
    
    # Check 4: Diagnostic script
    print("[4/5] Checking NBA diagnostic script...")
    diagnostic_script = Path(__file__).parent / "diagnose_nba_calibration.py"
    if diagnostic_script.exists():
        print("  [PASS] PASS - Diagnostic script exists")
    else:
        issues.append("scripts/diagnose_nba_calibration.py not found")
        print("  [FAIL] FAILED - Script missing")
    
    # Check 5: Menu integration
    print("[5/5] Checking menu integration...")
    try:
        menu_file = Path(__file__).parent.parent / "menu.py"
        with open(menu_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ("DG option", '"DG"' in content and "NBA Diagnostic" in content),
            ("run_nba_diagnostic", "def run_nba_diagnostic" in content),
            ("auto_resolve call", "auto_resolve_nba.py" in content),
        ]
        
        all_passed = all(check[1] for check in checks)
        
        if all_passed:
            print("  [PASS] PASS - Menu integration complete")
        else:
            failed = [check[0] for check in checks if not check[1]]
            issues.append(f"Menu integration incomplete: {failed}")
            print(f"  [FAIL] FAILED - Missing: {failed}")
    
    except Exception as e:
        issues.append(f"Cannot check menu.py: {e}")
        print("  [FAIL] FAILED - File check error")
    
    # Summary
    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    if not issues and not warnings:
        print("\n[PASS] ALL CHECKS PASSED")
        print("\nYour calibration system is ready to use!")
        print("\nNext steps:")
        print("  1. Enable tracking: $env:ENABLE_CALIBRATION_TRACKING='1'")
        print("  2. Run analysis to capture predictions")
        print("  3. Resolve outcomes: menu.py → [6] → [A]")
        print("  4. Run diagnostic: menu.py → [DG]")
    else:
        if issues:
            print(f"\n[FAIL] {len(issues)} CRITICAL ISSUES FOUND:")
            for issue in issues:
                print(f"  • {issue}")
        
        if warnings:
            print(f"\n[WARN]  {len(warnings)} WARNINGS:")
            for warning in warnings:
                print(f"  • {warning}")
        
        print("\nPlease fix issues before using the system.")
    
    print()
    return len(issues) == 0


if __name__ == "__main__":
    success = validate_installation()
    sys.exit(0 if success else 1)

