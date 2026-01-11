"""Hydrate points props with recent NBA game logs."""
import json
from datetime import datetime
from ufa.ingest.hydrate import hydrate_recent_values

def main():
    input_file = "inputs/jan8_points_props.json"
    output_file = "picks_hydrated_points.json"
    
    with open(input_file, encoding='utf-8') as f:
        picks = json.load(f)
    
    print(f"Hydrating {len(picks)} points props...")
    
    hydrated = []
    failed = []
    
    for i, pick in enumerate(picks, 1):
        player = pick["player"]
        print(f"[{i}/{len(picks)}] {player} points {pick['line']} {pick['direction']}...", end=" ")
        
        try:
            recent_values = hydrate_recent_values(
                league="NBA",
                player=player,
                stat_key="points",
                nba_season="2024-25"
            )
            
            if recent_values and len(recent_values) >= 5:
                pick["recent_values"] = recent_values
                pick["league"] = "NBA"
                pick["hydrated_at"] = datetime.now().isoformat()
                hydrated.append(pick)
                print("OK")
            else:
                print("SKIP")
                failed.append({"player": player, "reason": "insufficient_data"})
                
        except Exception as e:
            print("FAIL")
            failed.append({"player": player, "reason": str(e)[:50]})
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(hydrated, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"Successfully hydrated: {len(hydrated)}/{len(picks)}")
    print(f"Failed: {len(failed)}")
    print(f"Output: {output_file}")
    
    if failed:
        print(f"\nFailed: {', '.join([f['player'] for f in failed])}")

if __name__ == "__main__":
    main()
