"""Patch interactive_run in tennis/oddsapi_dfs_props.py"""

with open('tennis/oddsapi_dfs_props.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start of interactive_run
idx = content.find('def interactive_run')
if idx == -1:
    print("ERROR: interactive_run not found")
    exit(1)

# Keep everything before interactive_run
before = content[:idx]

# New interactive_run function
new_func = '''def interactive_run() -> None:
    print("\\n" + "=" * 70)
    print("TENNIS ODDS API (NO SCRAPE)")
    print("=" * 70)
    print("Ingests tennis lines from Odds API. Tries DFS player props first,")
    print("then falls back to match-level markets (total games, spreads).")

    tour = (input("Tour [ATP/WTA] (default WTA): ").strip() or "WTA").upper()
    surface = (input("Surface [Hard/Clay/Grass/Indoor] (default Hard): ").strip() or "Hard")
    max_events_s = input("Max events (blank = default): ").strip()
    max_events = int(max_events_s) if max_events_s else None

    # === STEP 1: Try DFS player props (usually returns 0 for tennis) ===
    props: List[Dict[str, Any]] = []
    raw_path: Optional[Path] = None
    try:
        props, meta, raw_path = ingest_oddsapi_tennis_dfs_props(tour=tour, max_events=max_events)
        print(f"\\n  DFS player props check: {len(props)} found")
    except Exception as e:
        print(f"\\n  DFS props check failed: {e}")

    # === STEP 2: Fall back to match-level markets (totals/spreads) ===
    if not props:
        print("\\n  Player props not available -- fetching match-level markets (totals/spreads)...")
        try:
            props, meta, raw_path = ingest_oddsapi_tennis_match_markets(tour=tour, max_events=max_events)
            print(f"  Saved: {raw_path}")
            print(f"  Match-level props: {len(props)}")

            if props:
                total_games = [p for p in props if p.get("stat") == "total_games"]
                spreads = [p for p in props if p.get("stat") == "game_spread"]
                n_matches = len(total_games) // 2 if total_games else 0
                print(f"\\n  Total games lines: {n_matches} matches")
                print(f"  Game spreads:      {len(spreads)} entries")

                seen_matches: set = set()
                for p in total_games:
                    match_name = p.get("player", "?")
                    if match_name not in seen_matches and p.get("direction") == "higher":
                        seen_matches.add(match_name)
                        print(f"    {match_name}: O/U {p.get('line')}")
                    if len(seen_matches) >= 5:
                        remaining = n_matches - 5
                        if remaining > 0:
                            print(f"    ... and {remaining} more")
                        break
        except Exception as e:
            print(f"\\n  Match markets also failed: {e}")
            input("\\nPress Enter to continue...")
            return

    if not props:
        print("\\n  0 props from both player props and match markets.")
        print("  Tournament may not have odds posted yet.")
        input("\\nPress Enter to continue...")
        return

    # === STEP 3: Analyze ===
    results = analyze_ingested_props(props, surface=surface, source_label="oddsapi_tennis")
    paths = write_analysis_artifacts(results)
    print(f"\\n  Analysis saved: {paths[\'analysis\']}")

    export_governed_signals(results)
    input("\\nPress Enter to continue...")


if __name__ == "__main__":
    interactive_run()
'''

# Write the patched file
with open('tennis/oddsapi_dfs_props.py', 'w', encoding='utf-8') as f:
    f.write(before + new_func)

print("Patched interactive_run successfully")
