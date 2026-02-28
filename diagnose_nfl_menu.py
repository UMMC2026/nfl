"""
NFL MENU DIAGNOSTIC & QUICK START
=================================
Run this to verify the menu works before using it interactively.
"""

import sys
import os

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_diagnostics():
    print("=" * 60)
    print("  NFL MENU DIAGNOSTIC CHECK")
    print("=" * 60)
    
    checks = []
    
    # Check 1: Module imports
    print("\n[1] Checking module imports...")
    try:
        import nfl_menu
        print("  ✓ nfl_menu.py loads OK")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ nfl_menu.py FAILED: {e}")
        checks.append(False)
    
    try:
        from analyze_nfl_props import calculate_nfl_probability
        print("  ✓ analyze_nfl_props.py loads OK")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ analyze_nfl_props.py FAILED: {e}")
        checks.append(False)
    
    try:
        from nfl_team_context import NFL_TEAM_CONTEXT
        print("  ✓ nfl_team_context.py loads OK")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ nfl_team_context.py FAILED: {e}")
        checks.append(False)
    
    # Check 2: Role mapping
    print("\n[2] Checking role mapping...")
    try:
        mapping = nfl_menu.load_role_mapping()
        players = mapping.get("player_classifications", {})
        print(f"  ✓ Role mapping: {len(players)} players loaded")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ Role mapping FAILED: {e}")
        checks.append(False)
    
    # Check 3: Parser test
    print("\n[3] Testing parser...")
    try:
        test_lines = "Josh Allen pass yards 265.5 higher\nDerrick Henry rush yds 85 over"
        picks = nfl_menu.parse_nfl_lines(test_lines)
        if len(picks) == 2:
            print(f"  ✓ Parser works: {len(picks)} picks parsed")
            checks.append(True)
        else:
            print(f"  ✗ Parser issue: expected 2, got {len(picks)}")
            checks.append(False)
    except Exception as e:
        print(f"  ✗ Parser FAILED: {e}")
        checks.append(False)
    
    # Check 4: Settings
    print("\n[4] Checking settings...")
    try:
        settings = nfl_menu.load_settings()
        print(f"  ✓ Settings loaded")
        last_slate = settings.get("last_slate")
        if last_slate:
            if os.path.exists(last_slate):
                print(f"  ✓ Last slate exists: {os.path.basename(last_slate)}")
            else:
                print(f"  ⚠ Last slate NOT found (will prompt to ingest new)")
        else:
            print(f"  ⚠ No previous slate (will prompt to ingest new)")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ Settings FAILED: {e}")
        checks.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(checks)
    total = len(checks)
    if passed == total:
        print(f"  ALL {total} CHECKS PASSED ✓")
        print("\n  Menu is ready! Run: python nfl_menu.py")
    else:
        print(f"  {passed}/{total} checks passed")
        print("\n  Fix issues above before running the menu.")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = run_diagnostics()
    sys.exit(0 if success else 1)
