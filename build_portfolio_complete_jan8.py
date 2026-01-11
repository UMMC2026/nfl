# -*- coding: utf-8 -*-
"""
BUILD FINAL PORTFOLIO WITH ANALYTICAL INSIGHTS
Construct 2-3 pick entries with structural validation and analytical reasoning
"""

import json
from pathlib import Path
from itertools import combinations
from datetime import datetime

# Underdog payout tables
POWER_PAYOUTS = {
    2: 3.0,
    3: 6.0,
    4: 10.0,
    5: 20.0
}

def calculate_entry_ev(picks, payout_multiplier):
    """Calculate E[ROI] for an entry"""
    # P(all hit)
    p_win = 1.0
    for pick in picks:
        p_win *= pick["final_prob"]
    
    # E[ROI] = (P(win) * payout) - 1
    ev_roi = (p_win * payout_multiplier) - 1.0
    
    return {
        "p_win": round(p_win, 4),
        "ev_roi": round(ev_roi, 4),
        "ev_units": round(ev_roi, 2)
    }

def check_structural_constraints(picks):
    """Check if entry meets structural constraints"""
    # Different teams
    teams = [p["team"] for p in picks]
    unique_teams = len(set(teams))
    
    # Check variance (high variance stats)
    high_var_stats = ["3pm", "blocks", "steals"]
    high_var_count = sum(1 for p in picks if p["stat"] in high_var_stats)
    
    return {
        "teams": teams,
        "unique_teams": unique_teams,
        "meets_team_constraint": unique_teams >= 2 if len(picks) >= 2 else True,
        "high_var_count": high_var_count,
        "variance_ok": high_var_count <= 1
    }

def format_analytical_pick(pick):
    """Format pick with analytical reasoning"""
    output = []
    output.append(f"   {pick['player']:20} ({pick['team']}) {pick['stat']:10} {pick['line']:5}+ [{pick['final_prob']:.0%}]")
    
    # Matchup reason
    if pick.get('matchup_reason'):
        output.append(f"   {'':23} Edge: {pick['matchup_reason']}")
    
    # Stats
    output.append(f"   {'':23} 10-game avg: {pick['sample_mean']:.1f} vs {pick['line']} line (+{pick['sample_mean']-pick['line']:.1f})")
    
    # Probability progression
    output.append(f"   {'':23} Prob: {pick['empirical']:.0%} empirical -> {pick['bayesian']:.0%} Bayesian -> {pick['final_prob']:.0%} final")
    
    return "\n".join(output)

def main():
    print("\n" + "="*80)
    print("BUILD FINAL PORTFOLIO WITH ANALYTICAL INSIGHTS")
    print("="*80 + "\n")
    
    # Load primary edges
    edges_file = Path("outputs/jan8_primary_edges_complete.json")
    with open(edges_file) as f:
        data = json.load(f)
    
    primary_edges = data["primary_edges"]
    
    print(f"Primary edges available: {len(primary_edges)}")
    print(f"Building 2-pick and 3-pick power entries...\n")
    
    # Tier classification
    SLAM_TIER = [p for p in primary_edges if p["final_prob"] >= 0.80]
    STRONG_TIER = [p for p in primary_edges if 0.70 <= p["final_prob"] < 0.80]
    LEAN_TIER = [p for p in primary_edges if 0.65 <= p["final_prob"] < 0.70]
    
    print(f"SLAM tier (80%+): {len(SLAM_TIER)} picks")
    print(f"STRONG tier (70-79%): {len(STRONG_TIER)} picks")
    print(f"LEAN tier (65-69%): {len(LEAN_TIER)} picks\n")
    
    all_entries = []
    
    # Build 3-pick SLAM entries
    print("Building 3-pick SLAM entries...")
    for combo in combinations(SLAM_TIER, 3):
        constraints = check_structural_constraints(combo)
        if constraints["meets_team_constraint"] and constraints["variance_ok"]:
            stats = calculate_entry_ev(combo, POWER_PAYOUTS[3])
            all_entries.append({
                "leg_count": 3,
                "picks": list(combo),
                "constraints": constraints,
                "stats": stats,
                "tier": "SLAM-only"
            })
    
    # Build 2-pick SLAM entries
    print("Building 2-pick SLAM entries...")
    for combo in combinations(SLAM_TIER, 2):
        constraints = check_structural_constraints(combo)
        if constraints["meets_team_constraint"] and constraints["variance_ok"]:
            stats = calculate_entry_ev(combo, POWER_PAYOUTS[2])
            all_entries.append({
                "leg_count": 2,
                "picks": list(combo),
                "constraints": constraints,
                "stats": stats,
                "tier": "SLAM-only"
            })
    
    # Build 2-pick SLAM+STRONG entries
    print("Building 2-pick SLAM+STRONG entries...")
    for slam in SLAM_TIER:
        for strong in STRONG_TIER:
            combo = [slam, strong]
            constraints = check_structural_constraints(combo)
            if constraints["meets_team_constraint"] and constraints["variance_ok"]:
                stats = calculate_entry_ev(combo, POWER_PAYOUTS[2])
                all_entries.append({
                    "leg_count": 2,
                    "picks": combo,
                    "constraints": constraints,
                    "stats": stats,
                    "tier": "SLAM+STRONG"
                })
    
    # Sort by EV
    all_entries.sort(key=lambda x: -x["stats"]["ev_roi"])
    
    # Take top 5
    top_entries = all_entries[:5]
    
    print(f"\nTotal valid entries: {len(all_entries)}")
    print(f"Selecting top 5 by E[ROI]...\n")
    
    # Save portfolio
    output = {
        "date": data["date"],
        "games": data["games"],
        "total_primary_edges": len(primary_edges),
        "entries": top_entries,
        "total_entries": len(top_entries)
    }
    
    output_path = Path("outputs/jan8_complete_portfolio.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print("="*80)
    print(f"PORTFOLIO COMPLETE!")
    print(f"Total entries: {len(top_entries)}")
    print(f"Saved to: {output_path}\n")
    
    # Print portfolio
    print("="*80)
    print("TOP 5 ENTRIES WITH ANALYTICAL REASONING")
    print("="*80 + "\n")
    
    for i, entry in enumerate(top_entries, 1):
        print(f"\n{'='*80}")
        print(f"ENTRY #{i} ({entry['leg_count']}-PICK {entry['tier'].upper()})")
        print(f"{'='*80}\n")
        
        for pick in entry["picks"]:
            print(format_analytical_pick(pick))
            print()
        
        print(f"PORTFOLIO METRICS:")
        print(f"   P(All Hit): {entry['stats']['p_win']:.2%}")
        print(f"   Payout: {POWER_PAYOUTS[entry['leg_count']]}x")
        print(f"   E[ROI]: {entry['stats']['ev_roi']:+.1%} ({entry['stats']['ev_units']:+.2f} units)")
        print(f"   Teams: {', '.join(entry['constraints']['teams'])} ({entry['constraints']['unique_teams']} different)")
        print(f"   High Variance Stats: {entry['constraints']['high_var_count']}")
    
    # Save formatted report
    report_path = Path("outputs/JAN8_COMPLETE_FINAL_PICKS.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write("COMPREHENSIVE PORTFOLIO - JANUARY 8, 2026\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p CST')}\n")
        f.write("="*80 + "\n\n")
        
        for i, entry in enumerate(top_entries, 1):
            f.write("\n" + "="*80 + "\n")
            f.write(f"ENTRY #{i} ({entry['leg_count']}-PICK {entry['tier'].upper()})\n")
            f.write("="*80 + "\n\n")
            
            for pick in entry["picks"]:
                f.write(format_analytical_pick(pick) + "\n\n")
            
            f.write(f"PORTFOLIO METRICS:\n")
            f.write(f"   P(All Hit): {entry['stats']['p_win']:.2%}\n")
            f.write(f"   Payout: {POWER_PAYOUTS[entry['leg_count']]}x\n")
            f.write(f"   E[ROI]: {entry['stats']['ev_roi']:+.1%} ({entry['stats']['ev_units']:+.2f} units)\n")
            f.write(f"   Teams: {', '.join(entry['constraints']['teams'])} ({entry['constraints']['unique_teams']} different)\n")
            f.write(f"   High Variance Stats: {entry['constraints']['high_var_count']}\n")
    
    print(f"\n{'='*80}")
    print(f"FINAL REPORT SAVED!")
    print(f"Report: {report_path}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
