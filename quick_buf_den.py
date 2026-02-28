"""Quick NFL props ingester - bypasses menu for direct analysis."""
import json
from pathlib import Path
from datetime import datetime

# Props extracted from Underdog paste - BUF @ DEN
PROPS = [
    # Nik Bonitto (DEN DEF)
    {"player": "Nik Bonitto", "team": "DEN", "position": "DEF", "stat": "sacks", "line": 0.5, "direction": "higher"},
    
    # Josh Allen (BUF QB)
    {"player": "Josh Allen", "team": "BUF", "position": "QB", "stat": "pass_yds", "line": 195.5, "direction": "higher"},
    {"player": "Josh Allen", "team": "BUF", "position": "QB", "stat": "rush_yds", "line": 34.5, "direction": "higher"},
    {"player": "Josh Allen", "team": "BUF", "position": "QB", "stat": "pass_tds", "line": 1.5, "direction": "higher"},
    
    # Khalil Shakir (BUF WR)
    {"player": "Khalil Shakir", "team": "BUF", "position": "WR", "stat": "rec_yds", "line": 45.5, "direction": "higher"},
    {"player": "Khalil Shakir", "team": "BUF", "position": "WR", "stat": "receptions", "line": 5.5, "direction": "higher"},
    
    # Evan Engram (DEN TE) - Note: He's listed as JAX in mapping, may need to update
    {"player": "Evan Engram", "team": "DEN", "position": "TE", "stat": "rec_yds", "line": 17.5, "direction": "higher"},
    {"player": "Evan Engram", "team": "DEN", "position": "TE", "stat": "receptions", "line": 2.5, "direction": "higher"},
    
    # RJ Harvey (DEN RB)
    {"player": "RJ Harvey", "team": "DEN", "position": "RB", "stat": "rush_yds", "line": 41.5, "direction": "higher"},
    {"player": "RJ Harvey", "team": "DEN", "position": "RB", "stat": "rec_yds", "line": 23.5, "direction": "higher"},
    {"player": "RJ Harvey", "team": "DEN", "position": "RB", "stat": "receptions", "line": 3.5, "direction": "higher"},
    
    # Bo Nix (DEN QB)
    {"player": "Bo Nix", "team": "DEN", "position": "QB", "stat": "pass_yds", "line": 222.5, "direction": "higher"},
    {"player": "Bo Nix", "team": "DEN", "position": "QB", "stat": "rush_yds", "line": 33.5, "direction": "higher"},
    {"player": "Bo Nix", "team": "DEN", "position": "QB", "stat": "pass_tds", "line": 1.5, "direction": "higher"},
    
    # Ray Davis (BUF RB)
    {"player": "Ray Davis", "team": "BUF", "position": "RB", "stat": "rush_yds", "line": 3.5, "direction": "higher"},
    {"player": "Ray Davis", "team": "BUF", "position": "RB", "stat": "rec_yds", "line": 2.5, "direction": "higher"},
    
    # Dawson Knox (BUF TE)
    {"player": "Dawson Knox", "team": "BUF", "position": "TE", "stat": "rec_yds", "line": 18.5, "direction": "higher"},
    {"player": "Dawson Knox", "team": "BUF", "position": "TE", "stat": "receptions", "line": 1.5, "direction": "higher"},
    
    # Curtis Samuel (BUF WR)
    {"player": "Curtis Samuel", "team": "BUF", "position": "WR", "stat": "rec_yds", "line": 4.5, "direction": "higher"},
    
    # Wil Lutz (DEN K)
    {"player": "Wil Lutz", "team": "DEN", "position": "K", "stat": "fg_made", "line": 2.5, "direction": "higher"},
    {"player": "Wil Lutz", "team": "DEN", "position": "K", "stat": "kicking_pts", "line": 9.5, "direction": "higher"},
    
    # Joey Bosa (now on BUF)
    {"player": "Joey Bosa", "team": "BUF", "position": "DEF", "stat": "sacks", "line": 0.5, "direction": "higher"},
    
    # Pat Surtain II (DEN DEF)
    {"player": "Pat Surtain II", "team": "DEN", "position": "DEF", "stat": "tackles", "line": 3.5, "direction": "higher"},
    
    # James Cook (BUF RB)
    {"player": "James Cook", "team": "BUF", "position": "RB", "stat": "rush_yds", "line": 93.5, "direction": "higher"},
    {"player": "James Cook", "team": "BUF", "position": "RB", "stat": "rec_yds", "line": 12.5, "direction": "higher"},
    {"player": "James Cook", "team": "BUF", "position": "RB", "stat": "receptions", "line": 1.5, "direction": "higher"},
    
    # Courtland Sutton (DEN WR)
    {"player": "Courtland Sutton", "team": "DEN", "position": "WR", "stat": "rec_yds", "line": 52.5, "direction": "higher"},
    {"player": "Courtland Sutton", "team": "DEN", "position": "WR", "stat": "receptions", "line": 4.5, "direction": "higher"},
    
    # Keon Coleman (BUF WR)
    {"player": "Keon Coleman", "team": "BUF", "position": "WR", "stat": "rec_yds", "line": 17.5, "direction": "higher"},
    {"player": "Keon Coleman", "team": "BUF", "position": "WR", "stat": "receptions", "line": 1.5, "direction": "higher"},
    
    # Marvin Mims Jr. (DEN WR)
    {"player": "Marvin Mims Jr.", "team": "DEN", "position": "WR", "stat": "rec_yds", "line": 16.5, "direction": "higher"},
    {"player": "Marvin Mims Jr.", "team": "DEN", "position": "WR", "stat": "receptions", "line": 1.5, "direction": "higher"},
    
    # Dalton Kincaid (BUF TE)
    {"player": "Dalton Kincaid", "team": "BUF", "position": "TE", "stat": "rec_yds", "line": 34.5, "direction": "higher"},
    {"player": "Dalton Kincaid", "team": "BUF", "position": "TE", "stat": "receptions", "line": 3.5, "direction": "higher"},
    
    # Jaleel McLaughlin (DEN RB)
    {"player": "Jaleel McLaughlin", "team": "DEN", "position": "RB", "stat": "rush_yds", "line": 25.5, "direction": "higher"},
    
    # Troy Franklin (DEN WR)
    {"player": "Troy Franklin", "team": "DEN", "position": "WR", "stat": "rec_yds", "line": 25.5, "direction": "higher"},
    {"player": "Troy Franklin", "team": "DEN", "position": "WR", "stat": "receptions", "line": 2.5, "direction": "higher"},
    
    # Brandin Cooks (BUF WR)
    {"player": "Brandin Cooks", "team": "BUF", "position": "WR", "stat": "rec_yds", "line": 24.5, "direction": "higher"},
    {"player": "Brandin Cooks", "team": "BUF", "position": "WR", "stat": "receptions", "line": 1.5, "direction": "higher"},
    
    # Adam Trautman (DEN TE)
    {"player": "Adam Trautman", "team": "DEN", "position": "TE", "stat": "rec_yds", "line": 4.5, "direction": "higher"},
    
    # Tyler Badie (DEN RB)
    {"player": "Tyler Badie", "team": "DEN", "position": "RB", "stat": "rec_yds", "line": 1.5, "direction": "higher"},
    
    # Matt Prater (BUF K - on BUF now)
    {"player": "Matt Prater", "team": "BUF", "position": "K", "stat": "fg_made", "line": 1.5, "direction": "higher"},
    {"player": "Matt Prater", "team": "BUF", "position": "K", "stat": "kicking_pts", "line": 6.5, "direction": "higher"},
    
    # Talanoa Hufanga (DEN DEF)
    {"player": "Talanoa Hufanga", "team": "DEN", "position": "DEF", "stat": "sacks", "line": 0.5, "direction": "higher"},
    {"player": "Talanoa Hufanga", "team": "DEN", "position": "DEF", "stat": "tackles", "line": 5.5, "direction": "higher"},
    
    # Dre Greenlaw (DEN DEF)
    {"player": "Dre Greenlaw", "team": "DEN", "position": "DEF", "stat": "sacks", "line": 0.5, "direction": "higher"},
    {"player": "Dre Greenlaw", "team": "DEN", "position": "DEF", "stat": "tackles", "line": 5.5, "direction": "higher"},
]

def main():
    print("=" * 70)
    print("  BUF @ DEN - QUICK PROP ANALYSIS")
    print("=" * 70)
    
    # Save to slate file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slate_file = Path("outputs") / f"nfl_slate_buf_den_{timestamp}.json"
    slate_file.parent.mkdir(exist_ok=True)
    
    slate_data = {
        "label": f"buf_den_{timestamp}",
        "timestamp": timestamp,
        "picks": PROPS
    }
    
    with open(slate_file, "w") as f:
        json.dump(slate_data, f, indent=2)
    
    print(f"\n[✓] Saved {len(PROPS)} props to: {slate_file}")
    
    # Update settings to point to this slate
    settings_file = Path(".nfl_analyzer_settings.json")
    settings = {"current_slate": str(slate_file)}
    settings_file.write_text(json.dumps(settings, indent=2))
    
    print(f"[✓] Set as current slate")
    
    # Now run the analysis
    print("\n" + "=" * 70)
    print("  RUNNING ANALYSIS...")
    print("=" * 70)
    
    try:
        from analyze_nfl_props import analyze_nfl_slate
        
        # Load role mapping
        with open("nfl_role_mapping.json") as f:
            role_mapping = json.load(f)
        
        results = analyze_nfl_slate(PROPS, role_mapping)
        
        print(f"\n{'PLAYER':<25} {'TEAM':<5} {'STAT':<15} {'LINE':>6} {'DIR':<6} {'PROB':>6} {'GRADE':<6}")
        print("-" * 80)
        
        # Sort by probability descending
        sorted_results = sorted(results, key=lambda x: x.get('probability', 0), reverse=True)
        
        for r in sorted_results:
            prob = r.get('probability', 0.5) * 100
            grade = "A" if prob >= 60 else "B" if prob >= 55 else "C" if prob >= 50 else "D"
            print(f"{r['player']:<25} {r['team']:<5} {r['stat']:<15} {r['line']:>6.1f} {r['direction']:<6} {prob:>5.1f}% {grade:<6}")
        
        # Top plays
        strong = [r for r in sorted_results if r.get('probability', 0) >= 0.55]
        if strong:
            print(f"\n{'='*70}")
            print("  TOP PLAYS (55%+)")
            print("=" * 70)
            for s in strong[:10]:
                print(f"  ★ {s['player']} {s['stat']} {s['direction']} {s['line']} ({s['probability']*100:.1f}%)")
        
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n[DONE]")

if __name__ == "__main__":
    main()
