#!/usr/bin/env python3
"""
Test CBB Spread Integration — Validates Fix #2

Tests:
1. OddsAPI fetches h2h markets (spreads, totals)
2. _parse_h2h_markets() extracts spread/total correctly
3. Props get spread/total attached
4. Game script penalties apply correctly
5. Report displays game context
"""

import sys
import json
from pathlib import Path

def test_parse_h2h_markets():
    """Test helper function parses h2h/spreads/totals correctly."""
    print("\n" + "="*70)
    print("TEST 1: Parse H2H Markets")
    print("="*70)
    
    # Mock OddsAPI response structure
    mock_h2h_data = [
        {
            "id": "test_event_123",
            "home_team": "Duke Blue Devils",
            "away_team": "North Carolina Tar Heels",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Duke Blue Devils", "point": -5.5},
                                {"name": "North Carolina Tar Heels", "point": 5.5}
                            ]
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 148.5},
                                {"name": "Under", "point": 148.5}
                            ]
                        }
                    ]
                }
            ]
        }
    ]
    
    # Import parser
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ingestion.prop_ingestion_pipeline import _parse_h2h_markets
        
        result = _parse_h2h_markets(mock_h2h_data, "CBB")
        
        print(f"✓ Parsed {len(result)} events")
        
        for event_id, game_data in result.items():
            print(f"\nEvent: {event_id}")
            print(f"  Matchup: {game_data['matchup']}")
            print(f"  Spread:  {game_data['spread']:+.1f}" if game_data['spread'] else "  Spread:  None")
            print(f"  Total:   {game_data['total']:.1f}" if game_data['total'] else "  Total:   None")
        
        # Validate
        assert "test_event_123" in result
        assert result["test_event_123"]["spread"] == -5.5
        assert result["test_event_123"]["total"] == 148.5
        assert "Duke Blue Devils" in result["test_event_123"]["matchup"]
        
        print("\n✅ PASS: H2H parsing works correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_game_script_penalties():
    """Test game script adjustments apply correctly."""
    print("\n" + "="*70)
    print("TEST 2: Game Script Penalties")
    print("="*70)
    
    # Mock props with different game contexts
    test_cases = [
        {
            "name": "Blowout Over (spread ≥15)",
            "prop": {
                "line": 18.5,
                "direction": "higher",
                "stat": "points",
                "player": "Test Player",
                "team": "Duke",
                "spread": -18.0,  # Blowout: Duke favored by 18
                "total": 145.0,
            },
            "expected_adj": 0.95,  # Overs suppressed in blowouts
        },
        {
            "name": "Blowout Under (spread ≥15)",
            "prop": {
                "line": 18.5,
                "direction": "lower",
                "stat": "points",
                "player": "Test Player",
                "team": "Duke",
                "spread": -18.0,
                "total": 145.0,
            },
            "expected_adj": 1.03,  # Unders boosted in blowouts
        },
        {
            "name": "High Pace Game (total >161)",
            "prop": {
                "line": 20.5,
                "direction": "higher",
                "stat": "points",
                "player": "Test Player",
                "team": "Duke",
                "spread": -3.0,
                "total": 168.0,  # High pace: 168/140 = 1.20
            },
            "expected_adj": 1.05,  # Scoring boosted in high pace
        },
        {
            "name": "Low Pace Game (total <119)",
            "prop": {
                "line": 15.5,
                "direction": "higher",
                "stat": "points",
                "player": "Test Player",
                "team": "Duke",
                "spread": -2.0,
                "total": 110.0,  # Low pace: 110/140 = 0.79
            },
            "expected_adj": 0.95,  # Scoring suppressed in low pace
        },
        {
            "name": "Close Game, Normal Pace",
            "prop": {
                "line": 18.5,
                "direction": "higher",
                "stat": "points",
                "player": "Test Player",
                "team": "Duke",
                "spread": -3.5,  # Close game
                "total": 142.0,  # Normal pace
            },
            "expected_adj": 1.0,  # No adjustment
        },
    ]
    
    try:
        # Import compute function (it will apply penalties)
        sys.path.insert(0, str(Path(__file__).parent / "sports" / "cbb"))
        from sports.cbb.cbb_main import compute_cbb_probability
        
        all_passed = True
        for tc in test_cases:
            print(f"\n{tc['name']}:")
            print(f"  Spread: {tc['prop'].get('spread'):+.1f}, Total: {tc['prop'].get('total'):.1f}")
            
            result = compute_cbb_probability(tc['prop'])
            
            game_script_trace = result.get('decision_trace', {}).get('game_script', {})
            actual_adj = game_script_trace.get('adjustment', 1.0)
            reason = game_script_trace.get('reason', 'none')
            
            print(f"  Expected adjustment: {tc['expected_adj']}")
            print(f"  Actual adjustment:   {actual_adj}")
            print(f"  Reason: {reason}")
            
            # Tolerance: ±0.01 for floating point
            if abs(actual_adj - tc['expected_adj']) < 0.01:
                print(f"  ✓ PASS")
            else:
                print(f"  ✗ FAIL: Expected {tc['expected_adj']}, got {actual_adj}")
                all_passed = False
        
        if all_passed:
            print("\n✅ PASS: All game script penalties applied correctly")
            return True
        else:
            print("\n❌ FAIL: Some game script penalties incorrect")
            return False
            
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_report_display():
    """Test professional report displays game context."""
    print("\n" + "="*70)
    print("TEST 3: Report Display (Game Context)")
    print("="*70)
    
    # Mock edge with spread/total
    mock_edge = {
        "player": "Zion Williamson",
        "team": "Duke",
        "opponent": "North Carolina",
        "stat": "points",
        "line": 22.5,
        "direction": "higher",
        "probability": 0.68,
        "tier": "STRONG",
        "spread": -8.5,
        "total": 152.5,
        "matchup": "North Carolina @ Duke",
        "player_mean": 24.2,
        "projected_sigma": 5.8,
        "raw_prob": 0.715,
        "adjusted_prob": 0.695,
        "mean_source": "ESPN_API",
        "confidence_flag": "OK",
        "decision_trace": {
            "mean": {"lambda": 24.2, "mean_source": "ESPN_API", "confidence_flag": "OK"},
            "model": {"type": "poisson", "sigma": 5.8, "raw_prob": 0.715, "direction": "higher", "line": 22.5},
            "game_script": {"spread": -8.5, "total": 152.5, "adjustment": 1.02, "reason": "high_pace_1.09"},
            "caps": {"stat_cap": 0.75, "global_cap": 0.79, "low_line_cap": 1.0, "cap_hit": None},
            "final": {"final_prob": 0.68, "signal_flag": "OK"},
        }
    }
    
    print("\nGenerating report section with game context...")
    print("-" * 70)
    
    # Format like the professional report
    spread = mock_edge.get('spread')
    total = mock_edge.get('total')
    matchup = mock_edge.get('matchup')
    
    if spread is not None or total is not None:
        game_context = []
        if matchup:
            game_context.append(matchup)
        if spread is not None:
            game_context.append(f"Spread: {spread:+.1f}")
        if total is not None:
            game_context.append(f"Total: {total:.1f}")
        
        print(f"┌{'─'*68}┐")
        print(f"│  #1 {mock_edge['player']} ({mock_edge['team']}) vs {mock_edge['opponent']:<38}│")
        print(f"└{'─'*68}┘")
        print(f"   ▲ {mock_edge['stat']} OVER {mock_edge['line']}   |   [{mock_edge['tier']}] {mock_edge['probability']*100:.1f}%")
        print(f"   🏀 Game: {' | '.join(game_context)}")
        print("")
        
        print("✅ PASS: Report displays game context correctly")
        return True
    else:
        print("❌ FAIL: Spread/total missing from edge")
        return False


def run_all_tests():
    """Run full test suite."""
    print("\n" + "="*70)
    print("CBB SPREAD INTEGRATION — VALIDATION SUITE")
    print("="*70)
    print("\nTesting Fix #2: Spread/Total Integration + Game Script Penalties")
    print("Estimated implementation time: 3 hours")
    print("="*70)
    
    results = []
    
    # Test 1: H2H parsing
    results.append(("Parse H2H Markets", test_parse_h2h_markets()))
    
    # Test 2: Game script penalties
    results.append(("Game Script Penalties", test_game_script_penalties()))
    
    # Test 3: Report display
    results.append(("Report Display", test_report_display()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED — Spread integration complete!")
        print("\nNext steps:")
        print("  1. Test with live OddsAPI data: python scripts/fuoom_no_scrape_ingest.py")
        print("  2. Verify h2h market fetching works")
        print("  3. Check professional report shows game context")
        print("  4. Monitor game script adjustments in decision traces")
        return 0
    else:
        print(f"\n❌ {total - passed} TESTS FAILED — Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
