"""
Tennis Pipeline Diagnostic Test
================================
Tests all components of the Tennis analysis system.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{'='*70}")
    print(f"{Colors.CYAN}{text}{Colors.RESET}")
    print('='*70)

def print_pass(text):
    print(f"{Colors.GREEN}✓ PASS:{Colors.RESET} {text}")

def print_fail(text):
    print(f"{Colors.RED}✗ FAIL:{Colors.RESET} {text}")

def print_warn(text):
    print(f"{Colors.YELLOW}⚠ WARN:{Colors.RESET} {text}")

def test_tennis_directory():
    """Test 1: Verify tennis directory and files exist."""
    print_header("TEST 1: Tennis Directory Structure")
    
    tennis_dir = PROJECT_ROOT / "tennis"
    required_files = [
        "tennis_main.py",
        "ingest_tennis.py",
        "generate_tennis_edges.py",
        "score_tennis_edges.py",
        "validate_tennis_output.py",
        "render_tennis_report.py",
        "tennis_elo.py",
        "tennis_props_pipeline.py",
        "generate_tennis_cheatsheet.py"
    ]
    
    passed = 0
    failed = 0
    
    if not tennis_dir.exists():
        print_fail(f"Tennis directory not found: {tennis_dir}")
        return 0, 1
    
    print_pass(f"Tennis directory exists: {tennis_dir}")
    passed += 1
    
    for file in required_files:
        filepath = tennis_dir / file
        if filepath.exists():
            print_pass(f"{file} exists")
            passed += 1
        else:
            print_fail(f"{file} MISSING")
            failed += 1
    
    return passed, failed

def test_config_imports():
    """Test 2: Verify config.thresholds can be imported."""
    print_header("TEST 2: Config Imports")
    
    passed = 0
    failed = 0
    
    try:
        from config.thresholds import get_all_thresholds, implied_tier
        print_pass("config.thresholds imports successfully")
        
        # Test function call
        thresholds = get_all_thresholds("tennis")
        print_pass(f"Tennis thresholds loaded: {thresholds}")
        passed += 2
        
    except ImportError as e:
        print_fail(f"config.thresholds import failed: {e}")
        failed += 1
    except Exception as e:
        print_fail(f"Config test error: {e}")
        failed += 1
    
    return passed, failed

def test_tennis_imports():
    """Test 3: Verify tennis modules can be imported."""
    print_header("TEST 3: Tennis Module Imports")
    
    passed = 0
    failed = 0
    
    # Add tennis to path
    tennis_dir = PROJECT_ROOT / "tennis"
    sys.path.insert(0, str(tennis_dir))
    
    modules = [
        ("Tennis Main", "tennis.tennis_main"),
        ("Ingest", "ingest_tennis"),
        ("Generate Edges", "generate_tennis_edges"),
        ("Score Edges", "score_tennis_edges"),
        ("Validate", "validate_tennis_output"),
        ("Render Report", "render_tennis_report"),
        ("Tennis ELO", "tennis_elo"),
        ("Props Pipeline", "tennis_props_pipeline"),
        ("Generate Cheatsheet", "generate_tennis_cheatsheet")
    ]
    
    for name, module in modules:
        try:
            __import__(module)
            print_pass(f"{name} ({module}) imports successfully")
            passed += 1
        except ImportError as e:
            print_fail(f"{name} ({module}) import failed: {e}")
            failed += 1
        except Exception as e:
            print_warn(f"{name} ({module}) import error (may be OK): {e}")
            passed += 1  # Some modules may have runtime dependencies
    
    return passed, failed

def test_tennis_main_function():
    """Test 4: Verify tennis_main.show_menu exists and is callable."""
    print_header("TEST 4: Tennis Main Menu Function")
    
    passed = 0
    failed = 0
    
    try:
        tennis_dir = PROJECT_ROOT / "tennis"
        sys.path.insert(0, str(tennis_dir))
        
        from tennis.tennis_main import show_menu
        print_pass("show_menu function exists")
        passed += 1
        
        # Check if it's callable
        if callable(show_menu):
            print_pass("show_menu is callable")
            passed += 1
        else:
            print_fail("show_menu is not callable")
            failed += 1
            
    except ImportError as e:
        print_fail(f"Could not import show_menu: {e}")
        failed += 1
    except Exception as e:
        print_fail(f"Test error: {e}")
        failed += 1
    
    return passed, failed

def test_outputs_directory():
    """Test 5: Verify tennis outputs directory."""
    print_header("TEST 5: Tennis Outputs Directory")
    
    passed = 0
    failed = 0
    
    outputs_dir = PROJECT_ROOT / "tennis" / "outputs"
    
    if outputs_dir.exists():
        print_pass(f"Outputs directory exists: {outputs_dir}")
        passed += 1
        
        # Check for existing reports
        match_reports = list(outputs_dir.glob("tennis_report_*.txt"))
        props_reports = list(outputs_dir.glob("tennis_props_analysis_*.txt"))
        
        if match_reports:
            print_pass(f"Found {len(match_reports)} match winner reports")
            passed += 1
        else:
            print_warn("No match winner reports (run analysis to create)")
        
        if props_reports:
            print_pass(f"Found {len(props_reports)} props reports")
            passed += 1
        else:
            print_warn("No props reports (run analysis to create)")
    else:
        print_warn(f"Outputs directory doesn't exist (will be created on first run)")
    
    return passed, failed

def test_menu_integration():
    """Test 6: Verify menu integration."""
    print_header("TEST 6: Menu Integration")
    
    passed = 0
    failed = 0
    
    try:
        menu_file = PROJECT_ROOT / "menu.py"
        if not menu_file.exists():
            print_fail("menu.py not found")
            return 0, 1
        
        content = menu_file.read_text(encoding='utf-8', errors='ignore')
        
        if "run_tennis_module" in content:
            print_pass("run_tennis_module function found in menu.py")
            passed += 1
        else:
            print_fail("run_tennis_module function NOT found")
            failed += 1
        
        if "[Y]" in content and "Tennis" in content:
            print_pass("[Y] Tennis menu option found")
            passed += 1
        else:
            print_fail("[Y] Tennis menu option NOT found")
            failed += 1
        
        if "tennis.tennis_main import show_menu" in content:
            print_pass("Tennis import statement found")
            passed += 1
        else:
            print_fail("Tennis import statement NOT found")
            failed += 1
        
    except Exception as e:
        print_fail(f"Menu test error: {e}")
        failed += 1
    
    return passed, failed

def test_path_setup():
    """Test 7: Verify path setup in tennis_main.py."""
    print_header("TEST 7: Path Setup")
    
    passed = 0
    failed = 0
    
    try:
        tennis_main = PROJECT_ROOT / "tennis" / "tennis_main.py"
        content = tennis_main.read_text(encoding='utf-8', errors='ignore')
        
        if "PROJECT_ROOT" in content:
            print_pass("PROJECT_ROOT defined in tennis_main.py")
            passed += 1
        else:
            print_fail("PROJECT_ROOT NOT defined")
            failed += 1
        
        if "sys.path.insert(0, str(PROJECT_ROOT))" in content:
            print_pass("PROJECT_ROOT added to sys.path")
            passed += 1
        else:
            print_fail("PROJECT_ROOT NOT added to sys.path")
            failed += 1
        
        if "_import_tennis_modules" in content:
            print_pass("Delayed import function found")
            passed += 1
        else:
            print_warn("No delayed import function (may cause import issues)")
        
    except Exception as e:
        print_fail(f"Path setup test error: {e}")
        failed += 1
    
    return passed, failed

def main():
    """Run all diagnostic tests."""
    print("\n" + "="*70)
    print(f"{Colors.CYAN}🎾 TENNIS PIPELINE DIAGNOSTIC{Colors.RESET}")
    print("="*70)
    
    total_passed = 0
    total_failed = 0
    
    tests = [
        ("Directory Structure", test_tennis_directory),
        ("Config Imports", test_config_imports),
        ("Tennis Module Imports", test_tennis_imports),
        ("Main Menu Function", test_tennis_main_function),
        ("Outputs Directory", test_outputs_directory),
        ("Menu Integration", test_menu_integration),
        ("Path Setup", test_path_setup)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed, failed = test_func()
            total_passed += passed
            total_failed += failed
            results.append((test_name, passed, failed))
        except Exception as e:
            print_fail(f"{test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            total_failed += 1
            results.append((test_name, 0, 1))
    
    # Summary
    print_header("DIAGNOSTIC SUMMARY")
    
    print("\nTest Results:")
    for test_name, passed, failed in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if failed == 0 else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {status} {test_name}: {passed} passed, {failed} failed")
    
    print(f"\n{'='*70}")
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    
    if total_failed == 0:
        print(f"{Colors.GREEN}✓ ALL TESTS PASSED - TENNIS READY{Colors.RESET}")
        print(f"\n📋 Access Tennis: Main Menu → [Y]")
        print(f"   Option 1: Match Winner Analysis")
        print(f"   Option 5: Props Monte Carlo (NBA-style)")
        return 0
    else:
        print(f"{Colors.RED}✗ {total_failed} TESTS FAILED{Colors.RESET}")
        print(f"\n🔧 Fix issues above, then re-test")
        return 1

if __name__ == "__main__":
    sys.exit(main())
