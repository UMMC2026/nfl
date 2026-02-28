"""Test enriched tennis output with match context + narrative."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tennis.oddsapi_dfs_props import (
    ingest_oddsapi_tennis_match_markets,
    analyze_ingested_props,
)

# Ingest 2 matches
props, meta, _ = ingest_oddsapi_tennis_match_markets(tour="WTA", max_events=2)
print(f"Props ingested: {len(props)}")

# Analyze
results = analyze_ingested_props(props, surface="Hard", source_label="oddsapi_test")
edges = results.get("results", [])
print(f"Edges analyzed: {len(edges)}")

# Show enriched output
for e in edges[:4]:
    print(f"\n{'='*70}")
    print(f"  {e['player']} | {e['stat']} {e['line']} {e['direction']}")
    print(f"  Tier: {e['tier']} | Prob: {e['probability']:.1%}")
    
    ctx = e.get("match_context")
    if ctx:
        p = ctx.get("player", {})
        o = ctx.get("opponent", {})
        h2h = ctx.get("head_to_head", {})
        
        print(f"  --- CONTEXT ---")
        print(f"  Player: ranking={p.get('ranking')}, elo={p.get('elo_surface')}, style={p.get('player_style')}")
        print(f"  Win rate: {p.get('win_rate')}, hold: {p.get('serve_hold_rate')}, BP save: {p.get('bp_save_rate')}")
        print(f"  L10 form: {p.get('recent_form_l10')}")
        if o:
            print(f"  Opponent: {o.get('name')}, ranking={o.get('ranking')}, elo={o.get('elo_surface')}")
        if h2h and h2h.get("total_matches", 0) > 0:
            print(f"  H2H: {h2h['p1_wins']}-{h2h['p2_wins']} ({h2h['total_matches']} matches)")
        print(f"  Matchup: {ctx.get('matchup_edge')}")
        print(f"  Narrative seed: {ctx.get('narrative_seed')}")
    else:
        print(f"  [no match_context]")
    
    narrative = e.get("narrative")
    if narrative:
        print(f"  NARRATIVE: {narrative}")

# Check memory file
mem_path = os.path.join("tennis", "data", "player_context_memory.json")
if os.path.exists(mem_path):
    mem = json.loads(open(mem_path).read())
    players = mem.get("players", {})
    print(f"\n{'='*70}")
    print(f"PLAYER MEMORY: {len(players)} players stored")
    for name, data in list(players.items())[:3]:
        print(f"  {name}: {data}")
