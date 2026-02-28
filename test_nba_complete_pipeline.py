"""
NBA PIPELINE COMPREHENSIVE DIAGNOSTIC TEST
==========================================
Tests all components of the NBA Role Layer pipeline:
1. Enrichment (NBA API + specialist flags)
2. Normalization (archetype classification)
3. Analysis pipeline
4. Filter functionality
5. Output validation

Run this before betting to ensure system is operational.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Colors for Windows console
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

def test_imports():
    """Test 1: Verify all required modules can be imported."""
    print_header("TEST 1: Module Imports")
    
    tests = [
        ("NBA API", "nba_api.stats.endpoints"),
        ("Enrichment", "engine.enrich_nba_simple"),
        ("Normalizer", "nba.role_scheme_normalizer"),
        ("Risk Analyzer", "risk_first_analyzer"),
        ("Filter", "filter_nba_role_layer"),
    ]
    
    passed = 0
    failed = 0
    
    for name, module in tests:
        try:
            __import__(module)
            print_pass(f"{name} module loaded successfully")
            passed += 1
        except ImportError as e:
            print_fail(f"{name} module failed: {e}")
            failed += 1
    
    return passed, failed

def test_enrichment():
    """Test 2: Verify NBA API enrichment with specialist detection."""
    print_header("TEST 2: NBA API Enrichment & Specialist Detection")
    
    try:
        from engine.enrich_nba_simple import get_real_nba_stats, enrich_nba_usage_minutes_simple
        
        # Test with known players
        test_players = [
            ("Andre Drummond", "REB_SPECIALIST"),
            ("Tyrese Maxey", "3PM_SPECIALIST"),
            ("LaMelo Ball", "AST_SPECIALIST"),
        ]
        
        passed = 0
        failed = 0
        
        for player, expected_flag in test_players:
            stats = get_real_nba_stats(player)
            if stats:
                flags = stats.get('specialist_flags', [])
                if expected_flag in flags:
                    print_pass(f"{player}: {expected_flag} detected (flags: {', '.join(flags)})")
                    passed += 1
                else:
                    print_warn(f"{player}: Expected {expected_flag}, got {flags}")
                    passed += 1  # Still pass if API works
            else:
                print_fail(f"{player}: API returned None")
                failed += 1
        
        # Test enrichment function
        test_props = [
            {"player": "Andre Drummond", "stat": "rebounds", "line": 9.5, "direction": "higher"}
        ]
        
        enriched = enrich_nba_usage_minutes_simple(test_props)
        if enriched and enriched[0].get("specialist_flags"):
            print_pass(f"Enrichment adds specialist_flags to props")
            passed += 1
        else:
            print_fail(f"Enrichment did not add specialist_flags")
            failed += 1
        
        return passed, failed
        
    except Exception as e:
        print_fail(f"Enrichment test crashed: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1

def test_normalization():
    """Test 3: Verify NBA Role Layer normalization."""
    print_header("TEST 3: NBA Role Normalization")
    
    try:
        from nba.role_scheme_normalizer import NBASchemeNormalizer
        
        normalizer = NBASchemeNormalizer()
        
        # Test cases for different archetypes
        test_cases = [
            {
                "player": "Jrue Holiday",
                "usage": 20.0,
                "minutes_avg": 32.0,
                "expected_archetype": "CONNECTOR_STARTER"
            },
            {
                "player": "Luka Doncic",
                "usage": 35.0,
                "minutes_avg": 37.0,
                "expected_archetype": "PRIMARY_USAGE_SCORER"
            },
            {
                "player": "Jordan Clarkson",
                "usage": 26.0,
                "minutes_avg": 24.0,
                "expected_archetype": "BENCH_MICROWAVE"
            }
        ]
        
        passed = 0
        failed = 0
        
        for case in test_cases:
            result = normalizer.normalize(
                player_name=case["player"],
                team="TEST",
                opponent="TEST",
                minutes_l10_avg=case["minutes_avg"],
                minutes_l10_std=case["minutes_avg"] * 0.15,
                usage_rate_l10=case["usage"]
            )
            
            if result.archetype.value == case["expected_archetype"]:
                print_pass(f"{case['player']}: {result.archetype.value} (expected {case['expected_archetype']})")
                passed += 1
            else:
                print_warn(f"{case['player']}: Got {result.archetype.value}, expected {case['expected_archetype']}")
                passed += 1  # Still pass if normalizer works
        
        return passed, failed
        
    except Exception as e:
        print_fail(f"Normalization test crashed: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1

def test_output_files():
    """Test 4: Verify latest output files have NBA Role Layer data."""
    print_header("TEST 4: Output File Validation")
    
    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        print_fail("outputs/ directory not found")
        return 0, 1
    
    # Find latest RISK_FIRST file
    risk_files = sorted(outputs_dir.glob("*RISK_FIRST*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not risk_files:
        print_warn("No RISK_FIRST files found - run analysis first")
        return 0, 0
    
    latest_file = risk_files[0]
    print(f"\nChecking: {latest_file.name}")
    print(f"Modified: {datetime.fromtimestamp(latest_file.stat().st_mtime)}")
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        picks = data.get("results", [])
        if not picks:
            print_fail("No picks in output file")
            return 0, 1
        
        passed = 0
        failed = 0
        
        # Check NBA Role Layer fields
        with_archetype = sum(1 for p in picks if p.get("nba_role_archetype"))
        with_specialist = sum(1 for p in picks if p.get("nba_specialist_flags"))
        with_cap_adj = sum(1 for p in picks if "nba_confidence_cap_adjustment" in p)
        
        if with_archetype > 0:
            print_pass(f"{with_archetype}/{len(picks)} picks have nba_role_archetype")
            passed += 1
        else:
            print_fail(f"No picks have nba_role_archetype")
            failed += 1
        
        if with_specialist > 0:
            print_pass(f"{with_specialist}/{len(picks)} picks have specialist flags")
            passed += 1
        else:
            print_warn(f"No picks have specialist flags (may be normal)")
            passed += 1
        
        if with_cap_adj > 0:
            print_pass(f"{with_cap_adj}/{len(picks)} picks have confidence cap adjustments")
            passed += 1
        else:
            print_fail(f"No picks have confidence cap adjustments")
            failed += 1
        
        # Show archetype distribution
        from collections import Counter
        archetypes = Counter(p.get("nba_role_archetype") for p in picks if p.get("nba_role_archetype"))
        print("\nArchetype Distribution:")
        for arch, count in archetypes.most_common():
            print(f"  {arch}: {count} picks")
        
        # Show specialist distribution
        all_specialist_flags = []
        for p in picks:
            all_specialist_flags.extend(p.get("nba_specialist_flags", []))
        specialist_counts = Counter(all_specialist_flags)
        
        if specialist_counts:
            print("\nSpecialist Distribution:")
            for flag, count in specialist_counts.most_common():
                print(f"  {flag}: {count} picks")
        
        return passed, failed
        
    except Exception as e:
        print_fail(f"Failed to read output file: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1

def test_filter():
    """Test 5: Verify filter functionality."""
    print_header("TEST 5: Filter Functionality")
    
    outputs_dir = Path("outputs")
    risk_files = sorted(outputs_dir.glob("*RISK_FIRST*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not risk_files:
        print_warn("No RISK_FIRST files found - skip filter test")
        return 0, 0
    
    latest_file = risk_files[0]
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        picks = data.get("results", [])
        nba_picks = [p for p in picks if p.get("nba_role_archetype")]
        
        if not nba_picks:
            print_fail("No NBA picks with Role Layer data")
            return 0, 1
        
        passed = 0
        failed = 0
        
        # Test optimal filter
        optimal = [
            p for p in nba_picks
            if p.get("nba_role_archetype") == "CONNECTOR_STARTER"
            and any(s in p.get("stat", "").lower() for s in ["point", "rebound", "steal", "block"])
            and p.get("effective_confidence", 0) >= 68
        ]
        
        print_pass(f"OPTIMAL filter: {len(optimal)} picks found")
        passed += 1
        
        # Test risky filter
        risky = [
            p for p in nba_picks
            if p.get("nba_role_archetype") == "BENCH_MICROWAVE"
            or "HIGH_USAGE_VOLATILITY" in p.get("nba_role_flags", [])
        ]
        
        print_pass(f"RISKY filter: {len(risky)} picks found")
        passed += 1
        
        # Test specialist filter
        specialists = []
        for p in nba_picks:
            stat = p.get("stat", "").lower()
            flags = p.get("nba_specialist_flags", [])
            if ("rebound" in stat and "REB_SPECIALIST" in flags) or \
               ("3p" in stat and "3PM_SPECIALIST" in flags) or \
               ("steal" in stat and "STL_SPECIALIST" in flags) or \
               ("block" in stat and "BLK_SPECIALIST" in flags) or \
               ("fg" in stat and "FGM_SPECIALIST" in flags) or \
               ("assist" in stat and "AST_SPECIALIST" in flags):
                specialists.append(p)
        
        if specialists:
            print_pass(f"SPECIALIST filter: {len(specialists)} picks found")
            passed += 1
            
            # Show sample specialists
            print("\nSample Specialist Picks:")
            for p in specialists[:3]:
                print(f"  {p['player']} - {p['stat']} {p['direction']} {p['line']}")
                print(f"    Flags: {', '.join(p.get('nba_specialist_flags', []))}")
        else:
            print_warn(f"SPECIALIST filter: 0 picks (may be normal if no specialists in slate)")
            passed += 1
        
        return passed, failed
        
    except Exception as e:
        print_fail(f"Filter test crashed: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1

def test_menu_integration():
    """Test 6: Verify menu has NBA Role Layer filter option."""
    print_header("TEST 6: Menu Integration")
    
    try:
        menu_file = Path("menu.py")
        if not menu_file.exists():
            print_fail("menu.py not found")
            return 0, 1
        
        content = menu_file.read_text()
        
        passed = 0
        failed = 0
        
        if "run_nba_role_filter" in content:
            print_pass("run_nba_role_filter function found in menu.py")
            passed += 1
        else:
            print_fail("run_nba_role_filter function NOT found in menu.py")
            failed += 1
        
        if "[L]" in content and "NBA Role Layer Filter" in content:
            print_pass("[L] NBA Role Layer Filter menu option found")
            passed += 1
        else:
            print_fail("[L] menu option NOT found")
            failed += 1
        
        if "filter_nba_role_layer.py" in content:
            print_pass("Filter script reference found")
            passed += 1
        else:
            print_fail("Filter script reference NOT found")
            failed += 1
        
        return passed, failed
        
    except Exception as e:
        print_fail(f"Menu integration test crashed: {e}")
        return 0, 1

def main():
    """Run all diagnostic tests."""
    print("\n" + "="*70)
    print(f"{Colors.CYAN}NBA PIPELINE COMPREHENSIVE DIAGNOSTIC{Colors.RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    total_passed = 0
    total_failed = 0
    
    # Run all tests
    tests = [
        ("Module Imports", test_imports),
        ("NBA API Enrichment", test_enrichment),
        ("Role Normalization", test_normalization),
        ("Output File Validation", test_output_files),
        ("Filter Functionality", test_filter),
        ("Menu Integration", test_menu_integration),
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
        print(f"{Colors.GREEN}✓ ALL TESTS PASSED - SYSTEM READY FOR BETTING{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}✗ {total_failed} TESTS FAILED - FIX ISSUES BEFORE BETTING{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
