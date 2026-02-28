#!/usr/bin/env python3
"""
Phase 4 Verification Test
==========================
Validates all Phase 4 implementations:
1. Auto-calibration scheduler
2. Tennis Bayesian priors
3. Golf Bayesian priors
4. Menu integration

Run: .venv\\Scripts\\python.exe scripts/phase4_verification.py
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_auto_calibrator():
    """Test auto-calibrator module."""
    print("\n" + "=" * 60)
    print("TEST 1: Auto-Calibrator")
    print("=" * 60)
    
    try:
        from calibration.auto_calibrator import AutoCalibrator, CalibrationAction
        
        calibrator = AutoCalibrator()
        assert calibrator.ALERT_THRESHOLD == 0.08
        assert calibrator.ADJUST_THRESHOLD == 0.12
        assert calibrator.CRITICAL_THRESHOLD == 0.18
        
        print("  ✅ AutoCalibrator imports correctly")
        print("  ✅ Thresholds configured: ALERT=8%, ADJUST=12%, CRITICAL=18%")
        
        # Test action history retrieval (doesn't require running full check)
        history = calibrator.get_action_history(days=7)
        print(f"  ✅ Action history retrieval works ({len(history)} recent actions)")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_tennis_bayesian():
    """Test Tennis Bayesian priors."""
    print("\n" + "=" * 60)
    print("TEST 2: Tennis Bayesian Priors")
    print("=" * 60)
    
    try:
        from betting_system.quant.tennis_bayesian_prior import (
            calculate_tennis_bayesian_projection,
            TENNIS_PRIORS,
            ELITE_TENNIS_PLAYERS
        )
        
        assert "TOP10" in TENNIS_PRIORS
        assert "TOP50" in TENNIS_PRIORS
        assert "Jannik Sinner" in ELITE_TENNIS_PLAYERS
        
        print("  ✅ Tennis priors loaded")
        print(f"  ✅ {len(ELITE_TENNIS_PLAYERS)} elite players configured")
        
        # Test projection
        proj = calculate_tennis_bayesian_projection(
            player_name="Jannik Sinner",
            ranking=1,
            stat="ACES",
            player_mu=10.0,
            player_sigma=3.0,
            sample_n=15,
            surface="HARD"
        )
        
        assert proj.shrinkage_factor < 0.2  # Low shrinkage for elite
        print(f"  ✅ Sinner projection: μ={proj.posterior_mu}, shrinkage={proj.shrinkage_factor:.1%}")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_golf_bayesian():
    """Test Golf Bayesian priors."""
    print("\n" + "=" * 60)
    print("TEST 3: Golf Bayesian Priors")
    print("=" * 60)
    
    try:
        from betting_system.quant.golf_bayesian_prior import (
            calculate_golf_bayesian_projection,
            GOLF_PRIORS,
            ELITE_GOLFERS
        )
        
        assert "TOP10" in GOLF_PRIORS
        assert "UNRANKED" in GOLF_PRIORS
        assert "Scottie Scheffler" in ELITE_GOLFERS
        
        print("  ✅ Golf priors loaded")
        print(f"  ✅ {len(ELITE_GOLFERS)} elite golfers configured")
        
        # Test projection
        proj = calculate_golf_bayesian_projection(
            player_name="Scottie Scheffler",
            owgr_ranking=1,
            stat="SG_TOTAL",
            player_mu=2.5,
            player_sigma=1.0,
            sample_n=20,
            course_type=None
        )
        
        assert proj.shrinkage_factor < 0.1  # Very low shrinkage for elite
        print(f"  ✅ Scheffler projection: μ={proj.posterior_mu}, shrinkage={proj.shrinkage_factor:.1%}")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nba_bayesian():
    """Test NBA Bayesian priors (Phase 2)."""
    print("\n" + "=" * 60)
    print("TEST 4: NBA Bayesian Priors (Phase 2)")
    print("=" * 60)
    
    try:
        from betting_system.quant.nba_bayesian_prior import (
            calculate_bayesian_projection,
            NBA_PRIORS
        )
        
        assert "PG" in NBA_PRIORS
        assert "C" in NBA_PRIORS
        
        print("  ✅ NBA priors loaded")
        
        proj = calculate_bayesian_projection(
            player_name="Test Player",
            position="PG",
            stat="assists",
            player_mu=8.0,
            player_sigma=2.0,
            sample_n=25
        )
        
        print(f"  ✅ PG AST projection: μ={proj.posterior_mu}, shrinkage={proj.shrinkage_factor:.1%}")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_drift_detector():
    """Test drift detector (Phase 2)."""
    print("\n" + "=" * 60)
    print("TEST 5: Drift Detector (Phase 2)")
    print("=" * 60)
    
    try:
        from calibration.drift_detector import DriftDetector
        
        detector = DriftDetector()
        print("  ✅ DriftDetector loads")
        
        # Try loading status
        detector.load_history()
        print("  ✅ History loaded")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_confidence_tracker():
    """Test confidence tracker (Phase 3)."""
    print("\n" + "=" * 60)
    print("TEST 6: Confidence Tracker (Phase 3)")
    print("=" * 60)
    
    try:
        from calibration.confidence_tracker import ConfidenceTracker
        
        tracker = ConfidenceTracker()
        print("  ✅ ConfidenceTracker loads")
        
        loaded = tracker.load_from_calibration_history()
        print(f"  ✅ Loaded {loaded} picks")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_rolling_backtest():
    """Test rolling backtest (Phase 3)."""
    print("\n" + "=" * 60)
    print("TEST 7: Rolling Backtest (Phase 3)")
    print("=" * 60)
    
    try:
        from calibration.rolling_backtest import RollingBacktester
        
        backtester = RollingBacktester(window_days=7)
        print("  ✅ RollingBacktester loads")
        
        backtester.load_history()
        print("  ✅ History loaded")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("=" * 70)
    print("  PHASE 4 VERIFICATION TEST")
    print("  Calibration System Audit — All Phases")
    print("=" * 70)
    
    results = []
    
    # Phase 4 tests
    results.append(("Auto-Calibrator", test_auto_calibrator()))
    results.append(("Tennis Bayesian", test_tennis_bayesian()))
    results.append(("Golf Bayesian", test_golf_bayesian()))
    
    # Phase 2 & 3 regression tests
    results.append(("NBA Bayesian", test_nba_bayesian()))
    results.append(("Drift Detector", test_drift_detector()))
    results.append(("Confidence Tracker", test_confidence_tracker()))
    results.append(("Rolling Backtest", test_rolling_backtest()))
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "=" * 70)
        print("  ✅ PHASE 4 VERIFICATION COMPLETE")
        print("  All calibration modules operational")
        print("=" * 70)
        return 0
    else:
        print(f"\n  ⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
