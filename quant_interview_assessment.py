"""
QUANT FIRM INTERVIEW PREPARATION ANALYSIS
==========================================
Critical assessment of what you have vs. what quant firms expect.

Run this to see your current gaps and action items.
"""

from pathlib import Path
import csv
import json
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent

def assess_quant_readiness():
    """Comprehensive assessment of quant firm interview readiness."""
    
    print("=" * 80)
    print("  🎯 QUANT FIRM INTERVIEW READINESS ASSESSMENT")
    print("=" * 80)
    print()
    
    assessment = {
        "calibration_plot": {"status": "CRITICAL_GAP", "details": []},
        "brier_score": {"status": "CRITICAL_GAP", "details": []},
        "opponent_adjustment": {"status": "PARTIAL", "details": []},
        "penalty_validation": {"status": "PARTIAL", "details": []},
    }
    
    # ═══════════════════════════════════════════════════════════════════
    # 1. CALIBRATION PLOT CHECK
    # ═══════════════════════════════════════════════════════════════════
    print("┌" + "─" * 78 + "┐")
    print("│  Q1: 'Show me your calibration plot'                                      │")
    print("├" + "─" * 78 + "┤")
    
    history_path = PROJECT_ROOT / "calibration_history.csv"
    scorable_picks = 0
    total_picks = 0
    
    if history_path.exists():
        with open(history_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_picks += 1
                prob = row.get('probability', '')
                outcome = row.get('outcome', '').upper()
                if prob and prob.strip() and outcome in ('HIT', 'MISS'):
                    scorable_picks += 1
    
    print(f"│  📊 Total picks in history:     {total_picks:<5}                                    │")
    print(f"│  📊 With BOTH prob + outcome:   {scorable_picks:<5}  ← NEEDED FOR CALIBRATION PLOT     │")
    print("│                                                                              │")
    
    if scorable_picks < 50:
        assessment["calibration_plot"]["status"] = "CRITICAL_GAP"
        print("│  ❌ STATUS: CRITICAL GAP                                                   │")
        print("│                                                                              │")
        print("│  PROBLEM: Calibration plots require picks with BOTH:                       │")
        print("│    1. Predicted probability (model output)                                 │")
        print("│    2. Resolved outcome (HIT/MISS)                                          │")
        print("│                                                                              │")
        print("│  YOUR DATA: Has outcomes but NO predicted probabilities!                   │")
        print("│                                                                              │")
        print("│  FIX REQUIRED:                                                              │")
        print("│    → Modify risk_first_analyzer.py to SAVE probability to history          │")
        print("│    → Run menu.py [6] to resolve picks WITH probability backfill           │")
        print("│    → Need 50+ scorable picks minimum                                       │")
    else:
        assessment["calibration_plot"]["status"] = "OK"
        print(f"│  ✅ STATUS: OK ({scorable_picks} scorable picks)                                │")
    
    print("└" + "─" * 78 + "┘")
    print()
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. BRIER SCORE CHECK
    # ═══════════════════════════════════════════════════════════════════
    print("┌" + "─" * 78 + "┐")
    print("│  Q2: 'What's your out-of-sample Brier score?'                             │")
    print("├" + "─" * 78 + "┤")
    
    if scorable_picks < 50:
        assessment["brier_score"]["status"] = "CRITICAL_GAP"
        print("│  ❌ STATUS: CANNOT COMPUTE                                                 │")
        print("│                                                                              │")
        print("│  PROBLEM: Same as calibration - need predicted probabilities               │")
        print("│                                                                              │")
        print("│  WHAT QUANTS EXPECT:                                                        │")
        print("│    - Brier score < 0.22 is good (0.25 = random)                           │")
        print("│    - Out-of-sample via k-fold cross-validation                             │")
        print("│    - Decomposition: reliability + resolution + uncertainty                 │")
        print("│                                                                              │")
        print("│  YOU HAVE:                                                                  │")
        print("│    - Win rate by stat (empirical, no probabilities)                        │")
        print("│    - 97 resolved outcomes without probabilities                            │")
    else:
        assessment["brier_score"]["status"] = "OK"
        print(f"│  ✅ Can compute from {scorable_picks} picks                                     │")
    
    print("└" + "─" * 78 + "┘")
    print()
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. OPPONENT ADJUSTMENT CHECK
    # ═══════════════════════════════════════════════════════════════════
    print("┌" + "─" * 78 + "┐")
    print("│  Q3: 'How do you adjust for opponent?'                                    │")
    print("├" + "─" * 78 + "┤")
    
    opp_db_path = PROJECT_ROOT / "cache" / "opponent_defense.db"
    opp_py_path = PROJECT_ROOT / "opponent_defense_db.py"
    matchup_path = PROJECT_ROOT / "matchup_analytics.py"
    
    has_opp_system = opp_py_path.exists() and matchup_path.exists()
    has_db = opp_db_path.exists()
    
    if has_opp_system:
        assessment["opponent_adjustment"]["status"] = "PARTIAL"
        print("│  🟡 STATUS: PARTIAL (system exists but needs integration proof)            │")
        print("│                                                                              │")
        print("│  YOU HAVE:                                                                  │")
        print(f"│    ✅ opponent_defense_db.py exists                                         │")
        print(f"│    ✅ matchup_analytics.py exists                                           │")
        print(f"│    {'✅' if has_db else '❌'} SQLite cache exists: {str(opp_db_path)[-40:]:<40} │")
        print("│    ✅ Defensive rankings (hardcoded, updated weekly)                        │")
        print("│    ✅ Multipliers: Elite 0.92, Good 0.96, Avg 1.00, Weak 1.04, Terrible 1.08│")
        print("│                                                                              │")
        print("│  GAPS:                                                                      │")
        print("│    ❌ No A/B test proving opponent adjustment improves predictions         │")
        print("│    ❌ No regression analysis: actual vs predicted with/without opp adj    │")
        print("│    ❌ Multipliers are heuristic, not empirically derived                   │")
    else:
        assessment["opponent_adjustment"]["status"] = "MISSING"
        print("│  ❌ STATUS: MISSING                                                         │")
    
    print("└" + "─" * 78 + "┘")
    print()
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. PENALTY COEFFICIENT VALIDATION
    # ═══════════════════════════════════════════════════════════════════
    print("┌" + "─" * 78 + "┐")
    print("│  Q4: 'Prove these penalty coefficients aren't overfitted'                 │")
    print("├" + "─" * 78 + "┤")
    
    penalties_path = PROJECT_ROOT / "config" / "data_driven_penalties.py"
    
    if penalties_path.exists():
        # Count coefficients with small samples
        stat_outcomes = defaultdict(list)
        if history_path.exists():
            with open(history_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    outcome = row.get('outcome', '').upper()
                    if outcome in ('HIT', 'MISS'):
                        stat = row.get('stat', '').lower()
                        stat_outcomes[stat].append(1 if outcome == 'HIT' else 0)
        
        small_sample_stats = [s for s, outcomes in stat_outcomes.items() if len(outcomes) < 10]
        
        assessment["penalty_validation"]["status"] = "PARTIAL"
        print("│  🟡 STATUS: PARTIAL                                                         │")
        print("│                                                                              │")
        print("│  YOU HAVE:                                                                  │")
        print("│    ✅ data_driven_penalties.py with empirical multipliers                  │")
        print("│    ✅ Formula: multiplier = observed_win_rate / 0.50                       │")
        print(f"│    ✅ 97 resolved picks for validation                                      │")
        print("│                                                                              │")
        print("│  PROBLEMS:                                                                  │")
        print(f"│    ⚠️  Small sample sizes: {len(small_sample_stats)} stats with n<10           │")
        for stat in small_sample_stats[:3]:
            n = len(stat_outcomes[stat])
            wr = sum(stat_outcomes[stat])/n if n > 0 else 0
            print(f"│       - {stat}: n={n}, win_rate={wr:.1%}                                     │")
        print("│    ⚠️  Wide confidence intervals (see CIs in report)                       │")
        print("│    ❌ No holdout set - all data used to derive AND validate               │")
        print("│    ❌ No bootstrap stability test                                          │")
        print("│    ❌ No temporal validation (train on Jan, test on Feb)                  │")
    
    print("└" + "─" * 78 + "┘")
    print()
    
    # ═══════════════════════════════════════════════════════════════════
    # SUMMARY & ACTION ITEMS
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  📋 ACTION ITEMS FOR QUANT FIRM READINESS")
    print("=" * 80)
    print()
    
    print("  IMMEDIATE (Critical Gaps):")
    print("  ────────────────────────────────────────────────────────────────────────")
    print("  [ ] 1. SAVE PROBABILITIES: Modify risk_first_analyzer.py to record")
    print("         predicted_probability to calibration_history.csv when picks resolve")
    print()
    print("  [ ] 2. BACKFILL PROBABILITIES: For existing 97 resolved picks, try to")
    print("         recover probabilities from outputs/*RISK_FIRST*.json files")
    print()
    print("  [ ] 3. COLLECT MORE DATA: Run system for 2-4 weeks, resolve picks daily")
    print("         Target: 200+ scorable picks with probabilities")
    print()
    
    print("  SHORT-TERM (Fill Gaps):")
    print("  ────────────────────────────────────────────────────────────────────────")
    print("  [ ] 4. OPPONENT A/B TEST: Run predictions with/without opponent adjustment")
    print("         Compare MSE/Brier on holdout set")
    print()
    print("  [ ] 5. TEMPORAL VALIDATION: Hold out most recent week's picks as test set")
    print("         Train coefficients on older data only")
    print()
    print("  [ ] 6. BOOTSTRAP COEFFICIENTS: Resample 1000x, show multiplier distributions")
    print("         Prove stability: most resamples yield similar multipliers")
    print()
    
    print("  PRESENTATION (For Interview):")
    print("  ────────────────────────────────────────────────────────────────────────")
    print("  [ ] 7. Generate matplotlib calibration plot (reliability diagram)")
    print("  [ ] 8. Prepare Brier decomposition (reliability + resolution + uncertainty)")
    print("  [ ] 9. Document opponent methodology with validation results")
    print("  [ ] 10. Show coefficient derivation with confidence intervals")
    print()
    
    # Final assessment
    critical = sum(1 for a in assessment.values() if a["status"] == "CRITICAL_GAP")
    partial = sum(1 for a in assessment.values() if a["status"] == "PARTIAL")
    ok = sum(1 for a in assessment.values() if a["status"] == "OK")
    
    print("=" * 80)
    print(f"  OVERALL: {critical} Critical Gaps | {partial} Partial | {ok} OK")
    if critical > 0:
        print("  ❌ NOT READY for quant firm interview - fix critical gaps first")
    elif partial > 0:
        print("  🟡 PARTIALLY READY - can explain gaps, need more data for proof")
    else:
        print("  ✅ READY for quant firm interview")
    print("=" * 80)
    
    return assessment


def main():
    assess_quant_readiness()


if __name__ == "__main__":
    main()
