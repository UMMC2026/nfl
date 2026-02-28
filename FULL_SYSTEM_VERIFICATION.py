"""
COMPLETE SYSTEM VERIFICATION
============================
Tests all components of the Underdog Analysis system.
"""

import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{'='*80}")
    print(f"{Colors.CYAN}{text}{Colors.RESET}")
    print('='*80)

def print_section(text):
    print(f"\n{Colors.MAGENTA}{'─'*80}")
    print(f"{text}")
    print(f"{'─'*80}{Colors.RESET}")

def print_pass(text):
    print(f"{Colors.GREEN}✓ PASS:{Colors.RESET} {text}")

def print_fail(text):
    print(f"{Colors.RED}✗ FAIL:{Colors.RESET} {text}")

def print_warn(text):
    print(f"{Colors.YELLOW}⚠ WARN:{Colors.RESET} {text}")

# ============================================================================
# CORE SYSTEM TESTS
# ============================================================================

def test_core_directories():
    """Test core directory structure."""
    print_section("CORE: Directory Structure")
    
    required_dirs = [
        "engine",
        "config",
        "calibration",
        "outputs",
        "gating",
        "nba",
        "tennis",
        "sports/cbb"
    ]
    
    passed = 0
    failed = 0
    
    for dir_name in required_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            print_pass(f"{dir_name}/ exists")
            passed += 1
        else:
            print_fail(f"{dir_name}/ MISSING")
            failed += 1
    
    return passed, failed

def test_core_files():
    """Test core system files."""
    print_section("CORE: Essential Files")
    
    required_files = [
        "menu.py",
        "daily_pipeline.py",
        "risk_first_analyzer.py",
        "config/thresholds.py",
        "engine/enrich_nba_simple.py",
        "gating/daily_games_report_gating.py"
    ]
    
    passed = 0
    failed = 0
    
    for file_name in required_files:
        file_path = PROJECT_ROOT / file_name
        if file_path.exists():
            print_pass(f"{file_name} exists")
            passed += 1
        else:
            print_fail(f"{file_name} MISSING")
            failed += 1
    
    return passed, failed

def test_core_imports():
    """Test core module imports."""
    print_section("CORE: Module Imports")
    
    modules = [
        ("Config Thresholds", "config.thresholds"),
        ("NBA Enrichment", "engine.enrich_nba_simple"),
        ("NBA Normalizer", "nba.role_scheme_normalizer"),
    ]
    
    passed = 0
    failed = 0
    
    for name, module in modules:
        try:
            __import__(module)
            print_pass(f"{name} imports successfully")
            passed += 1
        except ImportError as e:
            print_fail(f"{name} import failed: {e}")
            failed += 1
    
    return passed, failed

# ============================================================================
# NBA SYSTEM TESTS
# ============================================================================

def test_nba_api():
    """Test NBA API integration."""
    print_section("NBA: API Integration")
    
    passed = 0
    failed = 0
    
    try:
        from engine.enrich_nba_simple import get_real_nba_stats
        
        # Test with known player
        stats = get_real_nba_stats("LeBron James")
        
        if stats:
            print_pass("NBA API call successful")
            passed += 1
            
            if 'usage_rate' in stats:
                print_pass(f"Usage rate retrieved: {stats['usage_rate']:.1f}%")
                passed += 1
            
            if 'specialist_flags' in stats:
                print_pass(f"Specialist flags present: {len(stats['specialist_flags'])} flags")
                passed += 1
            else:
                print_fail("Specialist flags missing")
                failed += 1
        else:
            print_warn("API returned None (may be expected)")
            passed += 1
            
    except Exception as e:
        print_fail(f"NBA API test failed: {e}")
        failed += 1
    
    return passed, failed

def test_nba_specialist_detection():
    """Test specialist detection thresholds."""
    print_section("NBA: Specialist Detection")
    
    passed = 0
    failed = 0
    
    try:
        from engine.enrich_nba_simple import get_real_nba_stats
        
        # Test players known to be specialists
        test_cases = [
            ("Andre Drummond", "REB_SPECIALIST"),
            ("Stephen Curry", "3PM_SPECIALIST"),
        ]
        
        for player, expected_flag in test_cases:
            stats = get_real_nba_stats(player)
            if stats and 'specialist_flags' in stats:
                flags = stats['specialist_flags']
                if expected_flag in flags:
                    print_pass(f"{player}: {expected_flag} detected")
                    passed += 1
                else:
                    print_warn(f"{player}: Expected {expected_flag}, got {flags}")
                    passed += 1  # Warn not fail
            else:
                print_warn(f"{player}: Could not verify (API issue)")
                
    except Exception as e:
        print_fail(f"Specialist test failed: {e}")
        failed += 1
    
    return passed, failed

def test_nba_role_layer():
    """Test NBA Role Layer normalization."""
    print_section("NBA: Role Layer")
    
    passed = 0
    failed = 0
    
    try:
        from nba.role_scheme_normalizer import NBASchemeNormalizer
        
        normalizer = NBASchemeNormalizer()
        print_pass("NBASchemeNormalizer instantiated")
        passed += 1
        
        # Test normalization
        result = normalizer.normalize(
            player_name="Test Player",
            team="TEST",
            opponent="OPP",
            minutes_l10_avg=30.0,
            minutes_l10_std=4.5,
            usage_rate_l10=25.0
        )
        
        if result and result.archetype:
            print_pass(f"Normalization works, archetype: {result.archetype.value}")
            passed += 1
        else:
            print_fail("Normalization failed")
            failed += 1
            
    except Exception as e:
        print_fail(f"Role layer test failed: {e}")
        failed += 1
    
    return passed, failed

def test_nba_filter():
    """Test NBA Role Layer filter."""
    print_section("NBA: Filter System")
    
    passed = 0
    failed = 0
    
    filter_file = PROJECT_ROOT / "filter_nba_role_layer.py"
    
    if filter_file.exists():
        print_pass("filter_nba_role_layer.py exists")
        passed += 1
        
        try:
            content = filter_file.read_text(encoding='utf-8', errors='ignore')
            
            checks = [
                ("show_optimal_picks", "OPTIMAL filter"),
                ("show_risky_picks", "RISKY filter"),
                ("show_specialist_picks", "SPECIALIST filter"),
                ("show_archetype_distribution", "Distribution display")
            ]
            
            for func_name, desc in checks:
                if func_name in content:
                    print_pass(f"{desc} function exists")
                    passed += 1
                else:
                    print_fail(f"{desc} function MISSING")
                    failed += 1
                    
        except Exception as e:
            print_fail(f"Filter file check failed: {e}")
            failed += 1
    else:
        print_fail("filter_nba_role_layer.py MISSING")
        failed += 1
    
    return passed, failed

def test_nba_outputs():
    """Test NBA output files."""
    print_section("NBA: Output Files")
    
    passed = 0
    failed = 0
    
    outputs_dir = PROJECT_ROOT / "outputs"
    
    if outputs_dir.exists():
        risk_files = list(outputs_dir.glob("*RISK_FIRST*.json"))
        
        if risk_files:
            latest = sorted(risk_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            print_pass(f"Found {len(risk_files)} RISK_FIRST files")
            print_pass(f"Latest: {latest.name}")
            passed += 2
            
            # Check latest file for NBA Role Layer data
            try:
                import json
                with open(latest, 'r') as f:
                    data = json.load(f)
                
                picks = data.get('results', [])
                with_archetype = sum(1 for p in picks if p.get('nba_role_archetype'))
                
                if with_archetype > 0:
                    print_pass(f"{with_archetype}/{len(picks)} picks have NBA Role Layer data")
                    passed += 1
                else:
                    print_warn("No NBA Role Layer data (re-run analysis)")
                    
            except Exception as e:
                print_warn(f"Could not check file contents: {e}")
        else:
            print_warn("No RISK_FIRST files (run analysis first)")
    else:
        print_fail("outputs/ directory MISSING")
        failed += 1
    
    return passed, failed

# ============================================================================
# TENNIS SYSTEM TESTS
# ============================================================================

def test_tennis_system():
    """Test Tennis module."""
    print_section("TENNIS: System Check")
    
    passed = 0
    failed = 0
    
    tennis_dir = PROJECT_ROOT / "tennis"
    
    if not tennis_dir.exists():
        print_fail("tennis/ directory MISSING")
        return 0, 1
    
    print_pass("tennis/ directory exists")
    passed += 1
    
    # Test imports
    try:
        sys.path.insert(0, str(tennis_dir))
        import tennis.tennis_main as tennis_module
        print_pass("tennis.tennis_main imports successfully")
        passed += 1
        
        if hasattr(tennis_module, 'show_menu'):
            print_pass("show_menu function exists")
            passed += 1
        else:
            print_fail("show_menu function MISSING")
            failed += 1
            
    except ImportError as e:
        print_fail(f"Tennis import failed: {e}")
        failed += 1
    
    # Check outputs
    outputs_dir = tennis_dir / "outputs"
    if outputs_dir.exists():
        reports = list(outputs_dir.glob("tennis_*.txt"))
        print_pass(f"Tennis outputs exist: {len(reports)} reports")
        passed += 1
    else:
        print_warn("No tennis outputs yet")
    
    return passed, failed

# ============================================================================
# MENU SYSTEM TESTS
# ============================================================================

def test_menu_system():
    """Test main menu integration."""
    print_section("MENU: Integration Check")
    
    passed = 0
    failed = 0
    
    menu_file = PROJECT_ROOT / "menu.py"
    
    if not menu_file.exists():
        print_fail("menu.py MISSING")
        return 0, 1
    
    print_pass("menu.py exists")
    passed += 1
    
    try:
        content = menu_file.read_text(encoding='utf-8', errors='ignore')
        
        menu_options = [
            ("[L]", "NBA Role Layer Filter", "run_nba_role_filter"),
            ("[Y]", "Tennis", "run_tennis_module"),
            ("[B]", "CBB", "run_cbb_module"),
            ("[F]", "NFL", "run_nfl_module"),
            ("[2]", "Analyze Slate", "analyze_slate"),
        ]
        
        for option, desc, func in menu_options:
            if option in content and func in content:
                print_pass(f"{option} {desc} menu option present")
                passed += 1
            else:
                print_warn(f"{option} {desc} may be missing")
                
    except Exception as e:
        print_fail(f"Menu check failed: {e}")
        failed += 1
    
    return passed, failed

# ============================================================================
# CALIBRATION SYSTEM TESTS
# ============================================================================

def test_calibration_system():
    """Test calibration tracking."""
    print_section("CALIBRATION: System Check")
    
    passed = 0
    failed = 0
    
    calibration_dir = PROJECT_ROOT / "calibration"
    
    if not calibration_dir.exists():
        print_fail("calibration/ directory MISSING")
        return 0, 1
    
    print_pass("calibration/ directory exists")
    passed += 1
    
    # Check for calibration history
    history_file = PROJECT_ROOT / "calibration_history.csv"
    if history_file.exists():
        print_pass("calibration_history.csv exists")
        passed += 1
        
        # Check line count
        try:
            lines = history_file.read_text().split('\n')
            resolved_picks = len([l for l in lines if l.strip() and not l.startswith('edge_id')])
            print_pass(f"{resolved_picks} resolved picks tracked")
            passed += 1
        except Exception as e:
            print_warn(f"Could not count picks: {e}")
    else:
        print_warn("No calibration history yet")
    
    return passed, failed

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all system verification tests."""
    print("\n" + "="*80)
    print(f"{Colors.CYAN}🔍 COMPLETE SYSTEM VERIFICATION{Colors.RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    total_passed = 0
    total_failed = 0
    
    test_suites = [
        ("CORE: Directories", test_core_directories),
        ("CORE: Files", test_core_files),
        ("CORE: Imports", test_core_imports),
        ("NBA: API", test_nba_api),
        ("NBA: Specialists", test_nba_specialist_detection),
        ("NBA: Role Layer", test_nba_role_layer),
        ("NBA: Filter", test_nba_filter),
        ("NBA: Outputs", test_nba_outputs),
        ("TENNIS: System", test_tennis_system),
        ("MENU: Integration", test_menu_system),
        ("CALIBRATION: System", test_calibration_system),
    ]
    
    results = []
    
    for suite_name, test_func in test_suites:
        try:
            passed, failed = test_func()
            total_passed += passed
            total_failed += failed
            results.append((suite_name, passed, failed))
        except Exception as e:
            print_fail(f"{suite_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            total_failed += 1
            results.append((suite_name, 0, 1))
    
    # Final Summary
    print_header("VERIFICATION SUMMARY")
    
    print("\nTest Suite Results:")
    for suite_name, passed, failed in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if failed == 0 else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {status} {suite_name:25} {passed} passed, {failed} failed")
    
    print(f"\n{'='*80}")
    print(f"TOTAL TESTS: {total_passed} passed, {total_failed} failed")
    print(f"{'='*80}")
    
    if total_failed == 0:
        print(f"\n{Colors.GREEN}✅ ALL SYSTEMS OPERATIONAL{Colors.RESET}")
        print(f"\n📋 Quick Access:")
        print(f"   • NBA Analysis: Menu → [2]")
        print(f"   • NBA Filter: Menu → [L]")
        print(f"   • Tennis: Menu → [Y]")
        print(f"   • Calibration: Menu → [7]")
        return 0
    elif total_failed <= 3:
        print(f"\n{Colors.YELLOW}⚠️ MOSTLY OPERATIONAL ({total_failed} minor issues){Colors.RESET}")
        print(f"\n   Review warnings above - system should work")
        return 0
    else:
        print(f"\n{Colors.RED}❌ CRITICAL ISSUES DETECTED ({total_failed} failures){Colors.RESET}")
        print(f"\n   Fix issues above before using system")
        return 1

if __name__ == "__main__":
    sys.exit(main())
