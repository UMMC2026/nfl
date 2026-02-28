#!/usr/bin/env python3
"""
EDGE DIAGNOSTICS SYSTEM DIAGNOSTIC CHECK

Verifies all components are correctly integrated:
1. edge_diagnostics.py module
2. risk_first_analyzer.py integration
3. ai_commentary.py integration
4. menu.py report rendering
5. Latest analysis files
"""

import json
from pathlib import Path

def run_diagnostics():
    print("=" * 70)
    print("EDGE DIAGNOSTICS INTEGRATION CHECK")
    print("=" * 70)

    # 1. Check edge_diagnostics module
    print("\n[1] edge_diagnostics.py module...")
    try:
        from edge_diagnostics import (
            generate_edge_diagnostic,
            get_tier_label,
            calculate_z_score,
            calculate_penalty_attribution,
            format_diagnostic_block
        )
        print("    ✅ All exports available")
    except ImportError as e:
        print(f"    ❌ Import error: {e}")
        return

    # 2. Check risk_first_analyzer integration
    print("\n[2] risk_first_analyzer.py integration...")
    try:
        from risk_first_analyzer import HAS_EDGE_DIAGNOSTICS
        if HAS_EDGE_DIAGNOSTICS:
            print("    ✅ HAS_EDGE_DIAGNOSTICS = True")
        else:
            print("    ⚠️ HAS_EDGE_DIAGNOSTICS = False (fallback mode)")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    # 3. Check ai_commentary integration
    print("\n[3] ai_commentary.py integration...")
    try:
        from ai_commentary import generate_pick_commentary, generate_distributional_context
        print("    ✅ Functions available")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    # 4. Test edge diagnostic generation
    print("\n[4] Testing edge diagnostic generation...")
    try:
        # Test case: Brunson UNDER 28.5
        diag = generate_edge_diagnostic(
            line=28.5,
            mu=22.1,
            sigma=12.18,
            direction="lower",
            raw_probability=68.4,
            final_probability=55.2,
            stat="points",
            sport="nba"
        )
        print(f"    ✅ Generated diagnostic: {diag.diagnostic_summary}")
        print(f"    ✅ Z-score: {diag.z_score_diagnostic.z_score:+.2f}σ")
        print(f"    ✅ Tier: {diag.tier_label.tier}")
        print(f"    ✅ Penalty: -{diag.penalty_attribution.total_penalty_pct:.1f}%")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    # 5. Test tier labeling
    print("\n[5] Testing tier labeling...")
    try:
        test_cases = [(85, "SLAM"), (72, "STRONG"), (58, "LEAN"), (45, "NO_PLAY")]
        for conf, expected in test_cases:
            tier = get_tier_label(conf, "nba")
            status = "✅" if tier.tier == expected else "❌"
            print(f"    {status} {conf}% → {tier.tier} (expected: {expected})")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    # 6. Test z-score calculation for various scenarios
    print("\n[6] Testing z-score calculations...")
    try:
        test_cases = [
            # (line, mu, sigma, direction, expected_favorable)
            (28.5, 22.1, 12.18, "lower", True),    # Line above mean → favorable for UNDER
            (15.5, 21.4, 9.28, "higher", True),    # Line below mean → favorable for OVER
            (25.0, 25.0, 5.0, "higher", False),    # Line at mean → coin flip
            (30.0, 22.0, 4.0, "lower", True),      # Line 2σ above mean → very favorable for UNDER
        ]
        for line, mu, sigma, direction, expected_fav in test_cases:
            z = calculate_z_score(line, mu, sigma, direction)
            is_favorable = (direction == "higher" and z.z_score < 0) or (direction == "lower" and z.z_score > 0)
            status = "✅" if is_favorable == expected_fav else "❌"
            dir_word = "OVER" if direction == "higher" else "UNDER"
            print(f"    {status} Line {line} vs μ={mu:.1f}, σ={sigma:.1f} {dir_word}: z={z.z_score:+.2f}σ ({z.edge_quality})")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    # 7. Check latest analysis file for edge_diagnostics field
    print("\n[7] Checking latest analysis JSON for edge_diagnostics...")
    try:
        results_files = sorted(
            Path("outputs").glob("*_RISK_FIRST_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if results_files:
            latest = results_files[0]
            data = json.loads(latest.read_text())
            results = data.get("results", [])
            has_diag = sum(1 for r in results if r.get("edge_diagnostics"))
            total = len(results)
            print(f"    File: {latest.name}")
            print(f"    Total picks: {total}")
            print(f"    With edge_diagnostics: {has_diag}")
            if has_diag > 0:
                print("    ✅ edge_diagnostics present in results")
                # Show sample
                sample = next((r for r in results if r.get("edge_diagnostics")), None)
                if sample:
                    diag = sample["edge_diagnostics"]
                    player = sample.get("player", "Unknown")
                    stat = sample.get("stat", "?")
                    print(f"    Sample: {player} {stat}")
                    z_info = diag.get("z_score", {})
                    tier_info = diag.get("tier", {})
                    pen_info = diag.get("penalties", {})
                    print(f"      z_score: {z_info.get('z_score', 'N/A')}")
                    print(f"      tier: {tier_info.get('tier', 'N/A')}")
                    print(f"      total_penalty: {pen_info.get('total_penalty_pct', 'N/A')}%")
            else:
                print("    ⚠️ No edge_diagnostics in results (need to re-run analysis)")
        else:
            print("    ⚠️ No analysis files found")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSIS COMPLETE")
    print("=" * 70)
    print("\nTo populate edge_diagnostics in results, re-run analysis:")
    print("  python analyze_from_underdog_json.py --slate <your_slate.json>")
    print("\nThe new FULL_REPORT will include:")
    print("  • σ-Distance with interpretation")
    print("  • Penalty Breakdown (Stat Tax, Variance, Market, Context)")
    print("  • Tier Label (SLAM/STRONG/LEAN/NO_PLAY)")


if __name__ == "__main__":
    run_diagnostics()
