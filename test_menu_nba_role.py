"""
Quick test: NBA Role Layer through menu analysis path
"""

# NOTE: This file is a local smoke-test script that depends on a specific slate
# JSON existing on disk. When running under pytest collection, skip the module
# to avoid hard failures in CI or clean environments.
if __name__ != "__main__":
    import pytest

    pytest.skip("local smoke-test script (requires a local slate file)", allow_module_level=True)

import json
from pathlib import Path

# Load IND vs ATL slate
slate_file = Path("outputs/IND_ATL1262026_USERPASTE_20260126.json")
if not slate_file.exists():
    print(f"❌ Slate file not found: {slate_file}")
    exit(1)

slate_data = json.loads(slate_file.read_text())
props = slate_data.get("plays", [])
print(f"📄 Loaded {len(props)} props from {slate_file.name}")

# Run enrichment
from engine.enrich_nba_simple import enrich_nba_usage_minutes_simple
enriched_props = enrich_nba_usage_minutes_simple(props)
print(f"📊 Enriched {len(enriched_props)} props")

# Check what fields were added
sample = enriched_props[0]
print(f"\n🔍 Sample prop fields:")
print(f"   Player: {sample.get('player')}")
print(f"   Stat: {sample.get('stat')}")
print(f"   usage_rate: {sample.get('usage_rate')}")
print(f"   minutes_projected: {sample.get('minutes_projected')}")
print(f"   recent_values: {sample.get('recent_values', [])[:3] if sample.get('recent_values') else 'None'}...")

# Run NBA Role Layer normalization
from nba.role_scheme_normalizer import RoleSchemeNormalizer
normalizer = RoleSchemeNormalizer()

normalized_count = 0
for prop in enriched_props:
    player_name = prop.get("player", "")
    team = prop.get("team", "")
    opponent = prop.get("opponent", "")
    usage_rate_l10 = prop.get("usage_rate", 0.0)
    minutes_l10_avg = prop.get("minutes_projected", 0.0)
    minutes_l10_std = minutes_l10_avg * 0.15
    
    if not player_name or minutes_l10_avg == 0.0:
        continue
    
    game_context = {}
    if "spread" in prop:
        game_context["spread"] = prop["spread"]
    
    norm_result = normalizer.normalize(
        player_name=player_name,
        team=team,
        opponent=opponent,
        minutes_l10_avg=minutes_l10_avg,
        minutes_l10_std=minutes_l10_std,
        usage_rate_l10=usage_rate_l10,
        game_context=game_context
    )
    
    prop["nba_role_archetype"] = norm_result.archetype
    prop["nba_confidence_cap_adjustment"] = norm_result.confidence_cap_adjustment
    prop["nba_role_flags"] = norm_result.flags
    prop["nba_role_metadata"] = norm_result.metadata
    normalized_count += 1

print(f"\n✅ Normalized {normalized_count} NBA picks")

# Show results for key players
key_players = ["Pascal Siakam", "CJ McCollum", "Andrew Nembhard", "Onyeka Okongwu", "Jalen Johnson"]
print(f"\n🎯 NBA Role Classifications:")
for prop in enriched_props:
    player = prop.get("player", "")
    if player in key_players:
        archetype = prop.get("nba_role_archetype", "NONE")
        cap_adj = prop.get("nba_confidence_cap_adjustment", 0.0)
        flags = prop.get("nba_role_flags", [])
        usage = prop.get("usage_rate", 0.0)
        minutes = prop.get("minutes_projected", 0.0)
        
        print(f"\n{player}:")
        print(f"   Archetype: {archetype}")
        print(f"   Cap Adjustment: {cap_adj:+.1f}%")
        print(f"   Flags: {', '.join(flags) if flags else 'None'}")
        print(f"   Usage: {usage:.1f}%")
        print(f"   Minutes: {minutes:.1f}")
        
        # Remove from list once found
        if player in key_players:
            key_players.remove(player)
        
        if not key_players:
            break

print("\n✅ Test complete!")
