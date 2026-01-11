"""Hydrate rebounds props with recent NBA game logs."""
import json
from datetime import datetime
from ufa.ingest.hydrate import hydrate_recent_values

def main():
    input_file = "inputs/jan8_rebounds_props.json"
    output_file = "picks_hydrated.json"
    
    with open(input_file, encoding='utf-8') as f:
        picks = json.load(f)
    
    print(f"Hydrating {len(picks)} rebounds props...\n")
    
    hydrated = []
    failed = []
    
    for i, pick in enumerate(picks, 1):
        player = pick["player"]
        print(f"[{i}/{len(picks)}] {player} {pick['stat']} {pick['line']} {pick['direction']}...", end=" ")
        
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
                hydrated.append(pick)
                print(f"✓ ({len(recent_values)} games)")
            else:
                print(f"✗ (insufficient data: {len(recent_values) if recent_values else 0} games)")
                failed.append({"player": player, "reason": "insufficient_data"})
                
        except Exception as e:
            print(f"✗ ({str(e)})")
            failed.append({"player": player, "reason": str(e)})
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(hydrated, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✓ Successfully hydrated: {len(hydrated)}/{len(picks)}")
    print(f"✗ Failed: {len(failed)}")
    print(f"Output: {output_file}")
    
    if failed:
        print(f"\nFailed props: {', '.join([f['player'] for f in failed])}")

if __name__ == "__main__":
    main()
