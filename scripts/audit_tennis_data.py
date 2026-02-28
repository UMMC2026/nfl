"""Deep inspection of tennis analysis data completeness."""
import json

a = json.loads(open("tennis/outputs/oddsapi_tennis_dfs_props_analysis_latest.json", "r").read())
edges = a.get("results", [])

print("=" * 70)
print("TENNIS ANALYSIS DATA AUDIT")
print("=" * 70)

# Check what's in each edge
for e in edges[:3]:
    print(f"\n--- {e['player']} | {e['stat']} {e['line']} {e['direction']} ---")
    print(f"  Tier: {e['tier']} | Prob: {e['probability']:.1%} | Conf: {e['confidence']:.1f}%")
    
    sim = e.get("simulation", {})
    print(f"  Simulation: mean={sim.get('mean','?')}, std={sim.get('std','?')}, n={sim.get('n','?')}")
    
    prof = e.get("profile_data", {})
    print(f"  Profile: n_matches={prof.get('n_matches','?')}, hist_mean={prof.get('historical_mean','?')}, hist_std={prof.get('historical_std','?')}")
    
    inj = e.get("injury_gate", {})
    print(f"  Injury: player_pen={inj.get('player_injury_penalty','?')}, opp_pen={inj.get('opponent_injury_penalty','?')}, status={inj.get('player_status','?')}")

# What's MISSING
print("\n" + "=" * 70)
print("WHAT'S MISSING (gaps)")
print("=" * 70)

missing_fields = []
for field in ["opponent", "head_to_head", "surface_stats", "recent_form",
              "matchup_context", "venue", "ranking", "tournament_round",
              "serve_stats", "return_stats", "break_point_stats",
              "fatigue", "travel", "ai_commentary", "narrative"]:
    found = any(field in e for e in edges)
    status = "YES" if found else "NO"
    if not found:
        missing_fields.append(field)
    print(f"  {field:25s}: {status}")

print(f"\n  Missing fields: {len(missing_fields)}")

# Check tiers breakdown
tiers = a.get("tiers", {})
print(f"\n=== TIER BREAKDOWN ===")
for tier, count in tiers.items():
    tier_edges = [e for e in edges if e.get("tier") == tier]
    print(f"  {tier:10s}: {count}")
    for e in tier_edges[:3]:
        print(f"    {e['player']:35s} | {e['stat']:15s} | {e['line']:5.1f} {e['direction']:6s} | {e['probability']:.1%}")
    if len(tier_edges) > 3:
        print(f"    ... +{len(tier_edges)-3} more")
