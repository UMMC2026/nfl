"""
Hydrate 3PTM props with recent NBA game logs.
"""
import json
from pathlib import Path
from ufa.ingest.hydrate import hydrate_recent_values
from datetime import datetime

def main():
    # Load raw props
    input_file = Path("inputs/jan8_3ptm_props.json")
    output_file = Path("picks_hydrated.json")
    
    print(f"Loading props from {input_file}...")
    with open(input_file, encoding='utf-8') as f:
        raw_props = json.load(f)
    
    print(f"Loaded {len(raw_props)} raw 3PTM props")
    
    # Hydrate with recent game logs
    hydrated = []
    errors = []
    
    for i, prop in enumerate(raw_props, 1):
        player = prop["player"]
        team = prop["team"]
        stat = prop["stat"]  # "3pm"
        line = prop["line"]
        direction = prop["direction"]
        
        print(f"[{i}/{len(raw_props)}] Hydrating {player} ({team}) {stat} {line} {direction}...", end=" ")
        
        try:
            # Get recent game logs for 3pm
            recent_values = hydrate_recent_values(
                league="NBA",
                player=player,
                stat_key=stat,
                nba_season="2024-25"
            )
            
            if recent_values and len(recent_values) >= 5:
                hydrated_prop = {
                    "player": player,
                    "team": team,
                    "opponent": prop["opponent"],
                    "stat": stat,
                    "line": line,
                    "direction": direction,
                    "recent_values": recent_values,
                    "game_time": prop["game_time"],
                    "league": "NBA",
                    "hydrated_at": datetime.utcnow().isoformat()
                }
                hydrated.append(hydrated_prop)
                print(f"✓ ({len(recent_values)} games)")
            else:
                print(f"✗ Insufficient data ({len(recent_values) if recent_values else 0} games)")
                errors.append({"player": player, "reason": "insufficient_data", "count": len(recent_values) if recent_values else 0})
        
        except Exception as e:
            print(f"✗ Error: {e}")
            errors.append({"player": player, "reason": str(e)})
    
    # Save hydrated props
    print(f"\n{'='*80}")
    print(f"✓ Successfully hydrated: {len(hydrated)}/{len(raw_props)} props")
    print(f"✗ Failed: {len(errors)}")
    
    if errors:
        print(f"\nFailed props:")
        for err in errors[:10]:  # Show first 10
            print(f"  - {err['player']}: {err['reason']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    
    print(f"\nSaving to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(hydrated, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved {len(hydrated)} hydrated props")
    print(f"\nNext step: Run pipeline with:")
    print(f"  .venv\\Scripts\\python.exe daily_pipeline.py --mode analysis")

if __name__ == "__main__":
    main()
