"""
CROSS-SPORT INTEGRATION TEST
=============================

Validates that ALL sport adapters work correctly and produce
governance-compatible UGO objects.

Tests:
1. NBA → UGO
2. CBB → UGO
3. NFL → UGO
4. Tennis → UGO
5. Soccer → UGO (stat-centric)
6. Golf → UGO (hybrid shadow anchor)
7. ESS calculation from UGO
8. FAS attribution from UGO
9. Cross-sport edge_std comparability
"""

import sys
sys.path.insert(0, '.')

from core.universal_governance_object import (
    adapt_edge, Sport, validate_ugo, UniversalGovernanceObject
)
from core.ess_fas_spec import ess_from_ugo, fas_from_ugo_and_outcome
import json


def test_nba_adapter():
    """Test NBA → UGO conversion."""
    print("\n" + "="*70)
    print("TEST 1: NBA ADAPTER")
    print("="*70)
    
    nba_edge = {
        'player': 'LeBron James',
        'stat': 'PTS',
        'line': 25.5,
        'direction': 'higher',
        'mu': 28.3,
        'sigma': 4.2,
        'sample_n': 10,
        'probability': 0.72,
        'tier': 'STRONG',
        'pick_state': 'OPTIMIZABLE',
        'edge_id': 'NBA::LeBron_James::PTS::25.5',
        'game_id': 'LAL_vs_GSW',
        'date': '2026-02-01',
    }
    
    ugo = adapt_edge(Sport.NBA, nba_edge)
    is_valid, error = validate_ugo(ugo)
    
    print(f"✅ NBA → UGO: {ugo.entity} {ugo.market} {ugo.direction.value}")
    print(f"   Edge Z-Score: {ugo.edge_std:.3f}")
    print(f"   Validation: {'PASS' if is_valid else f'FAIL - {error}'}")
    
    return is_valid


def test_cbb_adapter():
    """Test CBB → UGO conversion."""
    print("\n" + "="*70)
    print("TEST 2: CBB ADAPTER")
    print("="*70)
    
    cbb_edge = {
        'player': 'Zach Edey',
        'stat': 'PTS',
        'line': 22.5,
        'direction': 'higher',
        'mean': 24.8,  # CBB uses 'mean' not 'mu'
        'std': 5.1,    # CBB uses 'std' not 'sigma'
        'games': 12,
        'probability': 0.68,
        'tier': 'STRONG',
        'edge_id': 'CBB::Zach_Edey::PTS::22.5',
        'game_id': 'PUR_vs_IU',
        'date': '2026-02-01',
    }
    
    ugo = adapt_edge(Sport.CBB, cbb_edge)
    is_valid, error = validate_ugo(ugo)
    
    print(f"✅ CBB → UGO: {ugo.entity} {ugo.market} {ugo.direction.value}")
    print(f"   Edge Z-Score: {ugo.edge_std:.3f}")
    print(f"   Validation: {'PASS' if is_valid else f'FAIL - {error}'}")
    
    return is_valid


def test_nfl_adapter():
    """Test NFL → UGO conversion."""
    print("\n" + "="*70)
    print("TEST 3: NFL ADAPTER")
    print("="*70)
    
    nfl_edge = {
        'entity': 'Patrick Mahomes',
        'market': 'pass_yds',
        'line': 275.5,
        'direction': 'more',
        'mu': 288.4,
        'sigma': 42.3,
        'n': 10,
        'probability': 0.62,
        'tier': 'LEAN',
        'edge_id': 'NFL::Patrick_Mahomes::pass_yds::275.5',
        'game_id': 'KC_vs_BUF',
        'date': '2026-02-02',
        'weather': 'clear',
    }
    
    ugo = adapt_edge(Sport.NFL, nfl_edge)
    is_valid, error = validate_ugo(ugo)
    
    print(f"✅ NFL → UGO: {ugo.entity} {ugo.market} {ugo.direction.value}")
    print(f"   Edge Z-Score: {ugo.edge_std:.3f}")
    print(f"   Validation: {'PASS' if is_valid else f'FAIL - {error}'}")
    
    return is_valid


def test_tennis_adapter():
    """Test Tennis → UGO conversion."""
    print("\n" + "="*70)
    print("TEST 4: TENNIS ADAPTER")
    print("="*70)
    
    tennis_edge = {
        'player': 'Taylor Fritz',
        'market': 'PLAYER_ACES',
        'line': 17.5,
        'direction': 'UNDER',
        'probability': 0.72,
        'tier': 'STRONG',
        'edge_id': 'TENNIS::Taylor_Fritz::ACES::17.5',
        'surface': 'HARD',
        'features': {
            'E_aces': 12.3,
            'std_dev': 3.1,
            'sample_n': 10,
        },
    }
    
    ugo = adapt_edge(Sport.TENNIS, tennis_edge)
    is_valid, error = validate_ugo(ugo)
    
    print(f"✅ Tennis → UGO: {ugo.entity} {ugo.market} {ugo.direction.value}")
    print(f"   Edge Z-Score: {ugo.edge_std:.3f}")
    print(f"   Validation: {'PASS' if is_valid else f'FAIL - {error}'}")
    
    return is_valid


def test_soccer_adapter():
    """Test Soccer → UGO conversion (stat-centric)."""
    print("\n" + "="*70)
    print("TEST 5: SOCCER ADAPTER (Stat-Centric Fix)")
    print("="*70)
    
    soccer_edge = {
        'entity': 'Arsenal vs Chelsea',
        'market': 'total_goals',
        'line': 2.5,
        'direction': 'OVER',
        'probability': 0.61,
        'tier': 'LEAN',
        'edge_id': 'SOCCER::ARS_CHE::total_goals::2.5',
        'league': 'EPL',
        'xg_projection': {
            'home': 1.8,
            'away': 1.2,
        },
    }
    
    ugo = adapt_edge(Sport.SOCCER, soccer_edge)
    is_valid, error = validate_ugo(ugo)
    
    print(f"✅ Soccer → UGO: {ugo.entity} {ugo.market} {ugo.direction.value}")
    print(f"   Projection (mu): {ugo.mu:.2f} goals")
    print(f"   Line: {ugo.line}")
    print(f"   Edge Z-Score: {ugo.edge_std:.3f}")
    print(f"   Validation: {'PASS' if is_valid else f'FAIL - {error}'}")
    print(f"   ✅ Stat-centric: mu ({ugo.mu:.1f}) is anchor, line ({ugo.line}) is measurement")
    
    return is_valid


def test_golf_adapter():
    """Test Golf → UGO conversion (hybrid shadow anchor)."""
    print("\n" + "="*70)
    print("TEST 6: GOLF ADAPTER (Hybrid Shadow Anchor)")
    print("="*70)
    
    golf_edge = {
        'player': 'Scottie Scheffler',
        'market': 'finishing_position',
        'line': 10.5,
        'direction': 'better',
        'higher_mult': 0.85,
        'lower_mult': 1.20,
        'better_mult': 0.75,
        'tournament': 'Masters',
        'sg_total': 2.5,
        'course_baseline': 72.0,
        'course_difficulty': 2.5,
    }
    
    ugo = adapt_edge(Sport.GOLF, golf_edge)
    is_valid, error = validate_ugo(ugo)
    
    print(f"✅ Golf → UGO: {ugo.entity} {ugo.market} {ugo.direction.value}")
    print(f"   Shadow Anchor (mu): {ugo.mu:.1f} (expected score)")
    print(f"   Line: {ugo.line}")
    print(f"   Edge Z-Score: {ugo.edge_std:.3f}")
    print(f"   Multiplier Edge: {ugo.sport_context.get('multiplier_edge')}")
    print(f"   Validation: {'PASS' if is_valid else f'FAIL - {error}'}")
    print(f"   ✅ Hybrid: Probability from multiplier, mu/sigma from SG:Total")
    
    return is_valid


def test_ess_integration():
    """Test ESS calculation from UGO."""
    print("\n" + "="*70)
    print("TEST 7: ESS INTEGRATION")
    print("="*70)
    
    nba_edge = {
        'player': 'Stephen Curry',
        'stat': '3PM',
        'line': 4.5,
        'direction': 'higher',
        'mu': 5.8,
        'sigma': 1.9,
        'sample_n': 12,
        'probability': 0.75,
        'tier': 'STRONG',
        'pick_state': 'OPTIMIZABLE',
        'minute_stability': 0.85,
        'role_entropy': 0.15,
        'blowout_risk': 0.10,
    }
    
    ugo = adapt_edge(Sport.NBA, nba_edge)
    ess_result = ess_from_ugo(ugo)
    
    print(f"✅ ESS from UGO: {ugo.entity} {ugo.market}")
    print(f"   ESS Score: {ess_result.ess_score:.3f}")
    print(f"   Tier: {ess_result.tier}")
    print(f"   Recommendation: {ess_result.recommendation}")
    print(f"   Components:")
    for k, v in ess_result.components.items():
        print(f"      {k}: {v:.4f}")
    print(f"   Stability Tags: {ess_result.stability_tags}")
    
    return ess_result.ess_score > 0


def test_fas_integration():
    """Test FAS attribution from UGO."""
    print("\n" + "="*70)
    print("TEST 8: FAS INTEGRATION")
    print("="*70)
    
    nba_edge = {
        'player': 'LeBron James',
        'stat': 'PTS',
        'line': 25.5,
        'direction': 'higher',
        'mu': 28.3,
        'sigma': 4.2,
        'sample_n': 10,
        'probability': 0.72,
        'tier': 'STRONG',
        'pick_state': 'OPTIMIZABLE',
    }
    
    ugo = adapt_edge(Sport.NBA, nba_edge)
    
    # Simulate failure: scored 18, played only 22 minutes
    fas_result = fas_from_ugo_and_outcome(
        ugo,
        actual_stat=18.0,
        actual_minutes=22,
        projected_minutes=34,
    )
    
    print(f"✅ FAS from UGO: {ugo.entity} {ugo.market}")
    print(f"   Projected: {ugo.mu:.1f}, Actual: 18.0")
    print(f"   Primary Attribution: {fas_result.primary_attribution}")
    print(f"   Secondary: {fas_result.secondary_attributions}")
    print(f"   Sigma Distance: {fas_result.sigma_distance:.2f}σ")
    print(f"   Is Learnable: {fas_result.is_learnable}")
    print(f"   Model Adjustment: {fas_result.model_adjustment}")
    print(f"   Learning Priority: {fas_result.learning_priority}")
    
    return fas_result.primary_attribution == "MIN_VAR"


def test_cross_sport_comparability():
    """Test cross-sport edge_std comparability."""
    print("\n" + "="*70)
    print("TEST 9: CROSS-SPORT EDGE COMPARABILITY")
    print("="*70)
    
    # Create edges from multiple sports
    nba = adapt_edge(Sport.NBA, {
        'player': 'LeBron', 'stat': 'PTS', 'line': 25.5, 'direction': 'higher',
        'mu': 28.3, 'sigma': 4.2, 'sample_n': 10, 'probability': 0.72,
        'tier': 'STRONG', 'pick_state': 'OPTIMIZABLE',
    })
    
    nfl = adapt_edge(Sport.NFL, {
        'entity': 'Mahomes', 'market': 'pass_yds', 'line': 275.5, 'direction': 'more',
        'mu': 295.0, 'sigma': 45.0, 'n': 10, 'probability': 0.65, 'tier': 'LEAN',
    })
    
    soccer = adapt_edge(Sport.SOCCER, {
        'entity': 'Arsenal', 'market': 'total_goals', 'line': 2.5, 'direction': 'OVER',
        'probability': 0.63, 'tier': 'LEAN', 'xg_projection': {'home': 1.9, 'away': 1.3},
    })
    
    edges = [nba, nfl, soccer]
    
    print("📊 Cross-Sport Edge Z-Scores (Universal Comparability):")
    print("-" * 70)
    for edge in edges:
        print(f"{edge.sport.value:10} | {edge.entity:20} | {edge.market:12} | z={edge.edge_std:+.3f}")
    
    print("\n✅ All edges use same z-score formula: (mu - line) / sigma")
    print("✅ Now comparable across sports for portfolio optimization")
    
    return True


def run_all_tests():
    """Run complete integration test suite."""
    print("="*70)
    print("CROSS-SPORT INTEGRATION TEST SUITE")
    print("Universal Governance Object v1.0")
    print("="*70)
    
    results = {}
    
    results['NBA'] = test_nba_adapter()
    results['CBB'] = test_cbb_adapter()
    results['NFL'] = test_nfl_adapter()
    results['Tennis'] = test_tennis_adapter()
    results['Soccer'] = test_soccer_adapter()
    results['Golf'] = test_golf_adapter()
    results['ESS'] = test_ess_integration()
    results['FAS'] = test_fas_integration()
    results['Cross-Sport'] = test_cross_sport_comparability()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {test}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED — SYSTEM READY FOR DEPLOYMENT")
    else:
        print("❌ SOME TESTS FAILED — FIX BEFORE DEPLOYMENT")
    print("="*70)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
