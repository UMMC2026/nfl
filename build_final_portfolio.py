#!/usr/bin/env python3
"""
Final Portfolio Builder for January 8, 2026
Uses primary edges to build 3-5 optimal entries with proper structure
"""

import json
from pathlib import Path
from itertools import combinations

# Payout multipliers (Underdog power format)
POWER_PAYOUTS = {
    2: 3.0,   # 2-pick: 3x
    3: 6.0,   # 3-pick: 6x
    4: 10.0,  # 4-pick: 10x
    5: 15.0,  # 5-pick: 15x
}

def calculate_entry_ev(picks, legs):
    """Calculate expected value for an entry"""
    # Joint probability (all legs hit)
    p_all_hit = 1.0
    for pick in picks:
        p_all_hit *= pick["prob_final"]
    
    # EV calculation
    payout_multiplier = POWER_PAYOUTS.get(legs, 0)
    ev_units = (p_all_hit * payout_multiplier) - 1.0
    ev_roi = ev_units * 100
    
    return {
        "p_all_hit": round(p_all_hit, 3),
        "payout_multiplier": payout_multiplier,
        "ev_units": round(ev_units, 3),
        "ev_roi": round(ev_roi, 1)
    }

def check_different_teams(picks):
    """Ensure all picks are from different teams"""
    teams = [p["team"] for p in picks]
    return len(teams) == len(set(teams))

def build_entries(primary_edges):
    """Build 3-5 optimal entries with structural constraints"""
    
    # Separate by tier
    slam_picks = [p for p in primary_edges if p["tier"] == "SLAM"]
    strong_picks = [p for p in primary_edges if p["tier"] == "STRONG"]
    
    all_entries = []
    
    # ENTRY 1: SLAM-only 2-pick (highest confidence)
    if len(slam_picks) >= 2:
        for combo in combinations(slam_picks, 2):
            if check_different_teams(combo):
                ev_info = calculate_entry_ev(combo, 2)
                all_entries.append({
                    "entry_type": "SLAM-2",
                    "legs": 2,
                    "picks": list(combo),
                    **ev_info
                })
    
    # ENTRY 2: SLAM + STRONG 2-pick (moderate confidence)
    if len(slam_picks) >= 1 and len(strong_picks) >= 1:
        for slam_pick in slam_picks:
            for strong_pick in strong_picks:
                combo = [slam_pick, strong_pick]
                if check_different_teams(combo):
                    ev_info = calculate_entry_ev(combo, 2)
                    all_entries.append({
                        "entry_type": "SLAM+STRONG-2",
                        "legs": 2,
                        "picks": combo,
                        **ev_info
                    })
    
    # ENTRY 3: STRONG-only 2-pick
    if len(strong_picks) >= 2:
        for combo in combinations(strong_picks, 2):
            if check_different_teams(combo):
                ev_info = calculate_entry_ev(combo, 2)
                all_entries.append({
                    "entry_type": "STRONG-2",
                    "legs": 2,
                    "picks": list(combo),
                    **ev_info
                })
    
    # ENTRY 4: SLAM-only 3-pick (aggressive)
    if len(slam_picks) >= 3:
        for combo in combinations(slam_picks, 3):
            if check_different_teams(combo):
                ev_info = calculate_entry_ev(combo, 3)
                all_entries.append({
                    "entry_type": "SLAM-3",
                    "legs": 3,
                    "picks": list(combo),
                    **ev_info
                })
    
    # ENTRY 5: SLAM + STRONG 3-pick
    if len(slam_picks) >= 2 and len(strong_picks) >= 1:
        for slam_combo in combinations(slam_picks, 2):
            for strong_pick in strong_picks:
                combo = list(slam_combo) + [strong_pick]
                if check_different_teams(combo):
                    ev_info = calculate_entry_ev(combo, 3)
                    all_entries.append({
                        "entry_type": "SLAM+STRONG-3",
                        "legs": 3,
                        "picks": combo,
                        **ev_info
                    })
    
    # Sort by EV (descending)
    all_entries.sort(key=lambda e: e["ev_roi"], reverse=True)
    
    return all_entries

def format_pick_display(pick):
    """Format pick for display"""
    player = pick["player"]
    team = pick["team"]
    stat = pick["stat"]
    line = pick["line"]
    direction = pick["direction"]
    prob = pick["prob_final"]
    variance = pick["variance"]
    
    dir_symbol = "+" if direction == "higher" else "-"
    return f"{player} ({team}): {stat} {line}{dir_symbol} [{prob:.1%}, {variance} variance]"

def main():
    print("\n" + "="*80)
    print("📋 FINAL PORTFOLIO BUILDER - JANUARY 8, 2026")
    print("="*80)
    
    # Load enhanced picks
    enhanced_file = Path("outputs/jan8_final_enhanced.json")
    if not enhanced_file.exists():
        print("❌ ERROR: jan8_final_enhanced.json not found. Run run_full_enhancement.py first.")
        return
    
    with open(enhanced_file, "r") as f:
        data = json.load(f)
    
    primary_edges = data["primary_edges"]
    print(f"📥 Loaded {len(primary_edges)} primary edges")
    
    # Build entries
    print("\n🔨 Building optimal entries...")
    all_entries = build_entries(primary_edges)
    
    print(f"✅ Generated {len(all_entries)} possible entries")
    
    # Select top 5
    top_entries = all_entries[:5]
    
    print("\n" + "="*80)
    print("🏆 TOP 5 RECOMMENDED ENTRIES")
    print("="*80)
    
    for i, entry in enumerate(top_entries, 1):
        entry_type = entry["entry_type"]
        legs = entry["legs"]
        p_all_hit = entry["p_all_hit"]
        ev_roi = entry["ev_roi"]
        
        print(f"\n{'='*80}")
        print(f"ENTRY {i}: {entry_type} ({legs} picks)")
        print(f"{'='*80}")
        print(f"P(All Hit): {p_all_hit:.1%} | E[ROI]: {ev_roi:+.1f}%")
        print()
        
        for pick in entry["picks"]:
            print(f"  • {format_pick_display(pick)}")
    
    # Save portfolio
    portfolio = {
        "date": "2026-01-08",
        "generated_at": "2026-01-08T17:00:00Z",
        "primary_edges_count": len(primary_edges),
        "total_entries_generated": len(all_entries),
        "top_5_entries": top_entries
    }
    
    output_file = Path("outputs/jan8_final_portfolio.json")
    with open(output_file, "w") as f:
        json.dump(portfolio, f, indent=2)
    
    print("\n" + "="*80)
    print(f"💾 Saved to: {output_file}")
    print("="*80)
    
    # Summary stats
    print("\n📊 PORTFOLIO SUMMARY")
    print("="*80)
    print(f"Total primary edges: {len(primary_edges)}")
    print(f"Total entries generated: {len(all_entries)}")
    print(f"Top 5 entries selected")
    print(f"Avg E[ROI] (top 5): {sum(e['ev_roi'] for e in top_entries) / len(top_entries):+.1f}%")
    print(f"Best E[ROI]: {top_entries[0]['ev_roi']:+.1f}%")
    print()
    
    print("✅ PORTFOLIO COMPLETE - READY FOR TONIGHT")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
