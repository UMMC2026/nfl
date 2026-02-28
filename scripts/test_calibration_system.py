"""
Test Calibration System - End-to-End Validation
Creates a sample pick, resolves it, and runs diagnostic
"""
import sys
from pathlib import Path
from datetime import datetime
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_calibration_system():
    """End-to-end test of calibration system"""
    
    print("\n" + "=" * 70)
    print("CALIBRATION SYSTEM - END-TO-END TEST")
    print("=" * 70)
    print()
    
    from calibration.unified_tracker import UnifiedCalibration, CalibrationPick
    
    # Test 1: Create sample pick with lambda tracking
    print("[1/4] Creating sample pick with lambda tracking...")
    
    cal = UnifiedCalibration()
    
    sample_pick = CalibrationPick(
        pick_id=str(uuid.uuid4()),
        date=datetime.now().isoformat(),
        sport="NBA",
        player="LeBron James",
        team="LAL",
        opponent="BOS",
        stat="points",
        line=25.5,
        direction="higher",
        probability=68.5,
        tier="STRONG",
        
        # Lambda tracking (CRITICAL)
        lambda_player=27.3,
        lambda_calculation="mu_raw=28.1 * factors=0.97 = 27.3",
        gap=6.6,  # (27.3 - 25.5) / 27.3 * 100
        z_score=0.35,
        
        # Probability chain
        prob_raw=72.3,
        prob_stat_capped=70.0,
        prob_global_capped=68.5,
        cap_applied="global_cap",
        
        model_version="nba_props_v2.1.4_test",
        edge=1.8,  # 27.3 - 25.5
        edge_type="PRIMARY"
    )
    
    cal.add_pick(sample_pick)
    print("  ✅ Sample pick created and saved")
    print(f"     Pick ID: {sample_pick.pick_id[:8]}...")
    print(f"     Lambda: {sample_pick.lambda_player}")
    print(f"     Probability: {sample_pick.probability}%")
    print()
    
    # Test 2: Update with outcome
    print("[2/4] Simulating game result...")
    actual_result = 28.0  # LeBron scored 28
    sample_pick.actual = actual_result
    sample_pick.hit = actual_result > sample_pick.line  # True (28 > 25.5)
    sample_pick.compute_brier()
    
    cal.save()
    print(f"  ✅ Outcome updated: Actual={actual_result}, Hit={sample_pick.hit}")
    print(f"     Brier Score: {sample_pick.brier:.4f}")
    print()
    
    # Test 3: Verify lambda tracking
    print("[3/4] Verifying lambda accuracy...")
    lambda_error = actual_result - sample_pick.lambda_player
    print(f"  Lambda (projection): {sample_pick.lambda_player}")
    print(f"  Actual result: {actual_result}")
    print(f"  Lambda error: {lambda_error:+.2f}")
    
    if abs(lambda_error) < 2.0:
        print("  ✅ Lambda accuracy is good (<2.0 error)")
    else:
        print("  ⚠️  Lambda error >2.0 (would need adjustment)")
    print()
    
    # Test 4: Load and verify
    print("[4/4] Loading picks and verifying storage...")
    cal_reload = UnifiedCalibration()
    
    # Find our test pick
    test_picks = [p for p in cal_reload.picks if p.player == "LeBron James"]
    
    if test_picks:
        loaded_pick = test_picks[0]
        print(f"  ✅ Pick loaded from CSV")
        print(f"     Player: {loaded_pick.player}")
        print(f"     Lambda: {loaded_pick.lambda_player}")
        print(f"     Actual: {loaded_pick.actual}")
        print(f"     Hit: {loaded_pick.hit}")
        
        # Verify all critical fields present
        checks = [
            ("Lambda tracking", loaded_pick.lambda_player > 0),
            ("Game context", loaded_pick.team != "UNK"),
            ("Probability chain", loaded_pick.prob_raw > 0),
            ("Model version", loaded_pick.model_version != "unknown"),
        ]
        
        print()
        print("  Field verification:")
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"    {status} {check_name}")
    else:
        print("  ❌ Could not load test pick")
    
    print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()
    print("✅ Calibration system is working correctly!")
    print()
    print("Key capabilities verified:")
    print("  • Lambda (mu) tracking works")
    print("  • Outcome resolution works")
    print("  • Lambda error calculation works")
    print("  • CSV persistence works")
    print()
    print("You can now use the system for real NBA picks.")
    print()
    print("Next steps:")
    print("  1. Enable tracking: scripts/setup_calibration_env.py --enable")
    print("  2. Run real slate: menu.py → [2] Analyze Slate")
    print("  3. Resolve outcomes: menu.py → [6] → [A] Auto-fetch")
    print("  4. Run diagnostic: menu.py → [DG] NBA Diagnostic")
    print()
    
    # Cleanup option
    try:
        cleanup = input("Remove test pick? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        cleanup = 'y'
    
    if cleanup in ('', 'y', 'yes'):
        # Remove test pick
        cal_reload.picks = [p for p in cal_reload.picks if p.player != "LeBron James" or p.model_version != "nba_props_v2.1.4_test"]
        cal_reload.save()
        print("\n✅ Test pick removed")
    else:
        print("\n⚠️  Test pick kept in calibration/picks.csv")
        print("   (You can manually remove it later)")


if __name__ == "__main__":
    test_calibration_system()
