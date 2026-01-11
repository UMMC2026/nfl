"""Combine 3PM and rebounds picks for unified analysis."""
import json

# Re-hydrate 3PM picks
print("Re-hydrating 3PM picks...")
from datetime import datetime
from ufa.ingest.hydrate import hydrate_recent_values

with open('inputs/jan8_3ptm_props.json', encoding='utf-8') as f:
    threepm_picks = json.load(f)

hydrated_3pm = []
for i, pick in enumerate(threepm_picks, 1):
    player = pick["player"]
    print(f"[{i}/{len(threepm_picks)}] {player} 3pm {pick['line']} {pick['direction']}...", end=" ")
    
    try:
        recent_values = hydrate_recent_values(
            league="NBA",
            player=player,
            stat_key="3pm",
            nba_season="2024-25"
        )
        
        if recent_values and len(recent_values) >= 5:
            pick["recent_values"] = recent_values
            pick["league"] = "NBA"
            pick["hydrated_at"] = datetime.now().isoformat()
            hydrated_3pm.append(pick)
            print("OK")
        else:
            print("SKIP")
    except Exception as e:
        print("FAIL")

# Load rebounds picks
print(f"\nLoading rebounds picks...")
with open('inputs/jan8_rebounds_props.json', encoding='utf-8') as f:
    rebounds_picks = json.load(f)

hydrated_rebounds = []
for i, pick in enumerate(rebounds_picks, 1):
    player = pick["player"]
    print(f"[{i}/{len(rebounds_picks)}] {player} rebounds {pick['line']} {pick['direction']}...", end=" ")
    
    try:
        recent_values = hydrate_recent_values(
            league="NBA",
            player=player,
            stat_key="rebounds",
            nba_season="2024-25"
        )
        
        if recent_values and len(recent_values) >= 5:
            pick["recent_values"] = recent_values
            pick["league"] = "NBA"
            pick["hydrated_at"] = datetime.now().isoformat()
            hydrated_rebounds.append(pick)
            print("OK")
        else:
            print("SKIP")
    except Exception as e:
        print("FAIL")

# Combine
combined = hydrated_3pm + hydrated_rebounds

print(f"\n{'='*60}")
print(f"Combined picks: {len(combined)}")
print(f"  - 3PM: {len(hydrated_3pm)}")
print(f"  - Rebounds: {len(hydrated_rebounds)}")

# Save combined
with open('picks_hydrated.json', 'w', encoding='utf-8') as f:
    json.dump(combined, f, indent=2, ensure_ascii=False)

print(f"Saved to: picks_hydrated.json")
