"""
Test Contextual Adjustments - LeBron with Luka Out
Demonstrates how the system adjusts projections based on key player absences
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.contextual_adjustments import ContextualAdjuster, apply_contextual_adjustment


def test_lebron_luka_scenario():
    """Test: Luka out → LeBron assists boost"""
    
    print("\n" + "=" * 70)
    print("CONTEXTUAL ADJUSTMENT TEST: LUKA OUT → LEBRON AST BOOST")
    print("=" * 70)
    print()
    
    # Setup
    adjuster = ContextualAdjuster()
    
    # Manually flag Luka as out
    print("[SETUP] Flagging Luka Doncic as OUT (ankle injury)")
    adjuster.set_manual_absence("Luka Doncic", "DAL", "ankle injury")
    print("✓ Luka marked as OUT\n")
    
    # LeBron's baseline projection
    player = "LeBron James"
    team = "DAL"  # Assuming LeBron is on DAL for this test
    stat = "assists"
    mu_baseline = 7.2  # LeBron's 10-game avg
    sigma_baseline = 2.1
    line = 10.5  # Over 10.5 assists
    
    print(f"[BASELINE] {player} - {stat.upper()}")
    print(f"  Historical Average: {mu_baseline} AST")
    print(f"  Std Deviation: {sigma_baseline}")
    print(f"  Line: {line}")
    print(f"  Gap: {mu_baseline - line:.1f} (below line)")
    print()
    
    # Check for contextual adjustment
    print("[CHECKING] Looking for affected teammates...")
    evidence = adjuster.check_and_adjust(
        player=player,
        team=team,
        opponent="BOS",  # Example opponent
        stat=stat,
        mu=mu_baseline,
        sigma=sigma_baseline
    )
    
    if evidence:
        print(f"✓ CONTEXT DETECTED: {evidence.reasoning}")
        print()
        print(f"[ADJUSTMENT]")
        print(f"  Mu Delta: +{evidence.mu_adjustment:.2f} AST")
        print(f"  Sigma Delta: {evidence.sigma_adjustment:.2f}")
        print(f"  Confidence Delta: +{evidence.confidence_delta:.1f}%")
        print()
        
        # Apply adjustment
        mu_adjusted, sigma_adjusted, reasoning = apply_contextual_adjustment(
            mu=mu_baseline,
            sigma=sigma_baseline,
            evidence=evidence
        )
        
        print(f"[ADJUSTED] {player} - {stat.upper()}")
        print(f"  New Projection: {mu_adjusted:.2f} AST (was {mu_baseline})")
        print(f"  New Std Dev: {sigma_adjusted:.2f} (was {sigma_baseline})")
        print(f"  New Gap: {mu_adjusted - line:.1f} (now {'ABOVE' if mu_adjusted > line else 'below'} line)")
        print()
        
        # Calculate probability improvement
        from scipy.stats import norm
        prob_baseline = 100 * (1 - norm.cdf(line, mu_baseline, sigma_baseline))
        prob_adjusted = 100 * (1 - norm.cdf(line, mu_adjusted, sigma_adjusted))
        
        print(f"[PROBABILITY IMPACT]")
        print(f"  Before: {prob_baseline:.1f}% (UNDER 55% threshold - REJECTED)")
        print(f"  After: {prob_adjusted:.1f}% ({'OPTIMIZABLE' if prob_adjusted >= 55 else 'STILL REJECTED'})")
        print(f"  Delta: +{prob_adjusted - prob_baseline:.1f}%")
        print()
        
        if prob_adjusted >= 55:
            print("✅ RESULT: Pick now passes governance threshold!")
        else:
            print("⚠️ RESULT: Pick improved but still below 55% threshold")
        
    else:
        print("❌ NO ADJUSTMENT: No contextual evidence found")
    
    print()
    print("=" * 70)
    print()
    
    # Cleanup
    print("[CLEANUP] Clearing manual absences...")
    adjuster.clear_manual_absences()
    print("✓ Absences cleared")
    print()


if __name__ == "__main__":
    test_lebron_luka_scenario()
