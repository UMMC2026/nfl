"""soccer/soccer_main.py

Soccer (Futbol) interactive submenu.

v1.0 is RESEARCH + manual-only. This menu is intentionally small:
- Run pipeline from a manual slate JSON
- View latest report / latest RISK_FIRST

No scraping. No live.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


SOCCER_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = SOCCER_DIR / "outputs"
INPUTS_DIR = SOCCER_DIR / "inputs"


def _pause() -> None:
    try:
        input("\nPress Enter to continue...")
    except Exception:
        return


def _latest(pattern: str) -> Optional[Path]:
    if not OUTPUTS_DIR.exists():
        return None
    files = sorted(OUTPUTS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _print_header() -> None:
    print("=" * 60)
    print("[SOCCER] FUTBOL MODULE — v1.0 (RESEARCH)")
    print("Manual slate only | Hard gates | 1 primary per match")
    print("=" * 60)


def _run_pipeline_prompt() -> None:
    from soccer.run_daily import run_pipeline

    default_slate = INPUTS_DIR / "slate_example.json"
    print("\nSlate JSON path (manual inputs)")
    print(f"  Default example: {default_slate}")

    # Help prevent the common failure mode: user pastes a number (not a file path).
    # We reprompt and show available slates.
    def _list_available_slates() -> list[Path]:
        if not INPUTS_DIR.exists():
            return []
        return sorted([p for p in INPUTS_DIR.glob("*.json") if p.is_file()])

    def _looks_like_props_ingest(p: Path) -> bool:
        # Props ingest artifacts contain plays + analysis_allowed false.
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        if isinstance(data.get("plays"), list) and data.get("analysis_allowed") is False:
            return True
        return False

    slate_path: Optional[Path] = None
    attempts = 0
    while slate_path is None and attempts < 5:
        attempts += 1
        raw = input("Enter path (press Enter for example): ").strip().strip('"')
        if not raw:
            slate_path = default_slate
            break

        # If they typed a bare filename, assume it's under soccer/inputs.
        candidate = Path(raw)
        if not candidate.suffix and (INPUTS_DIR / f"{raw}.json").exists():
            candidate = INPUTS_DIR / f"{raw}.json"
        elif candidate.name == raw and not candidate.is_absolute():
            candidate = INPUTS_DIR / raw

        if raw.isdigit():
            print(f"\n[!] '{raw}' looks like a number, but this prompt requires a JSON file path.")
        elif not candidate.exists():
            print(f"\n[!] File not found: {candidate}")
        else:
            # Guard: don't allow props ingest files to be run through the match pipeline.
            if _looks_like_props_ingest(candidate):
                print("\n[!] That file is a SOCCER PLAYER PROPS ingest artifact (mode=INGEST_ONLY).")
                print("    Use option [4] to ingest props; option [1] only runs TEAM/MATCH markets from xG inputs.")
            else:
                slate_path = candidate
                break

        # Show available slate files to reduce confusion.
        avail = _list_available_slates()
        if avail:
            print("\nAvailable soccer input JSON files:")
            for i, p in enumerate(avail, start=1):
                tag = " (props ingest)" if _looks_like_props_ingest(p) else ""
                print(f"  [{i}] {p}{tag}")
            print("\nTip: press Enter to run the example slate, or paste one of the paths above.")
        else:
            print("\nNo JSON files found in soccer/inputs. The example slate should exist at:")
            print(f"  {default_slate}")

    if slate_path is None:
        print("\n[SOCCER] Cancelled: no valid slate path provided.")
        return

    sims_raw = input("Monte Carlo sims per match (default 10000): ").strip()
    sims = 10000
    if sims_raw:
        try:
            sims = int(sims_raw)
        except Exception:
            sims = 10000

    try:
        run_pipeline(slate_path=str(slate_path), sims=sims)
    except Exception as e:
        print(f"\n[SOCCER] Pipeline error: {e}")


def _ingest_underdog_soccer_paste() -> None:
    """Paste Underdog soccer props and save to soccer/inputs as JSON.

    Now supports ANALYSIS via the new soccer props pipeline (manual hydration).
    """
    from datetime import datetime

    from soccer.ingest.parse_soccer_underdog_paste import parse_text

    print("\n" + "-" * 60)
    print("Paste your Underdog SOCCER slate below.")
    print("Type 'END' on its own line when finished.")
    print("-" * 60 + "\n")

    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)

    text = "\n".join(lines).strip()
    if not text:
        print("\nNo input received.")
        return

    plays = parse_text(text)
    if not plays:
        print("\nNo props parsed from input (format mismatch).")
        return

    label = input("\nLabel for this slate (optional): ").strip().upper() or "SOCCER"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = INPUTS_DIR / f"soccer_props_{label}_{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "sport": "SOCCER",
                "slate_type": "PLAYER_PROPS",
                "mode": "ANALYSIS_READY",
                "analysis_allowed": True,
                "reason": "Use option [5] to run Monte Carlo analysis (manual stats hydration)",
                "source": "underdog_paste_manual",
                "created_at": datetime.now().isoformat(),
                "plays": plays,
                "raw_lines": lines,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved {len(plays)} soccer props to: {out}")
    print("➡️  Use option [5] to analyze this slate with Monte Carlo.")


def _run_props_analysis_prompt() -> None:
    """Run Monte Carlo analysis on a saved soccer props slate."""
    from soccer.soccer_props_pipeline import run_props_pipeline

    # List available props slates
    props_files = sorted([
        p for p in INPUTS_DIR.glob("soccer_props_*.json")
        if p.is_file()
    ], key=lambda p: p.stat().st_mtime, reverse=True)

    if not props_files:
        print("\nNo soccer props slates found in soccer/inputs.")
        print("Use option [4] to paste and save a slate first.")
        return

    print("\nAvailable soccer props slates:")
    for i, p in enumerate(props_files[:10], start=1):
        print(f"  [{i}] {p.name}")

    choice = input("\nSelect slate number (or paste full path): ").strip()

    slate_path = None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(props_files):
            slate_path = props_files[idx]
    else:
        candidate = Path(choice)
        if candidate.exists():
            slate_path = candidate
        elif (INPUTS_DIR / choice).exists():
            slate_path = INPUTS_DIR / choice

    if slate_path is None:
        print("\n[!] Invalid selection.")
        return

    interactive_raw = input("\nPrompt for missing stats interactively? (y/n, default=y): ").strip().lower()
    interactive = interactive_raw != "n"
    
    skip_all = False
    if interactive:
        skip_raw = input("Skip ALL players with missing stats? (y/n, default=n): ").strip().lower()
        skip_all = skip_raw == "y"

    sims_raw = input("Monte Carlo sims (default 10000): ").strip()
    sims = 10000
    if sims_raw:
        try:
            sims = int(sims_raw)
        except Exception:
            sims = 10000

    try:
        result = run_props_pipeline(
            str(slate_path), 
            interactive=interactive, 
            num_sims=sims,
            skip_all_missing=skip_all,
        )
        print(f"\n✅ Analysis complete!")
        print(f"   Actionable picks: {result['actionable']}")
        print(f"   Missing data: {result['missing_data']}")
    except Exception as e:
        print(f"\n[SOCCER PROPS] Pipeline error: {e}")
        import traceback
        traceback.print_exc()


def _import_player_stats_json() -> None:
    """Bulk import player stats from a JSON file."""
    from soccer.data.soccer_stats_api import get_soccer_stats_store

    print("\nImport player stats from JSON file.")
    print("Expected format:")
    print('''  {
    "players": [
      {"player": "Name", "team": "Team", "tackles_l5": 2.1, "tackles_l10": 1.8, ...}
    ]
  }''')

    path = input("\nPath to stats JSON: ").strip().strip('"')
    if not path:
        print("\nCancelled.")
        return

    try:
        store = get_soccer_stats_store()
        count = store.bulk_import_json(path)
        print(f"\n✅ Imported {count} player stats.")
    except Exception as e:
        print(f"\n[!] Import failed: {e}")


def _fetch_stats_from_api() -> None:
    """
    NEW OPTION 7: Fetch player stats from API-Football (RapidAPI).
    
    Automatically fetches latest player statistics from API-Football API.
    Saves to soccer/data/player_stats.json for use in Monte Carlo analysis.
    
    Requires: RAPIDAPI_KEY environment variable
    """
    from soccer.api_football_integration import fetch_soccer_stats_for_slate, test_api_connection
    
    print("\n" + "="*60)
    print("⚽ API-FOOTBALL PLAYER STATS FETCHER")
    print("="*60)
    
    # Test API connection first
    print("\nTesting API connection...")
    if not test_api_connection():
        print("\n❌ Setup required:")
        print("   1. Get API key from: https://rapidapi.com/api-sports/api/api-football")
        print("   2. Set environment variable: RAPIDAPI_KEY=your_key")
        print("   3. Or create .env file with RAPIDAPI_KEY=your_key")
        return
    
    print("\n✅ API connection verified!")
    
    # Option to fetch from slate or manual entry
    print("\nFetch stats for:")
    print("  [1] Players in current slate (auto-detect from latest props)")
    print("  [2] Specific players (manual entry)")
    print("  [0] Cancel")
    
    choice = input("\nSelect option: ").strip()
    
    player_names = []
    
    if choice == '1':
        # Find latest props slate
        props_files = []
        if INPUTS_DIR.exists():
            props_files = sorted(
                [p for p in INPUTS_DIR.glob("*.json") if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
        
        if not props_files:
            print("\n⚠️  No slate files found in soccer/inputs/")
            print("   Run option [4] first to paste and save a slate")
            return
        
        slate_path = props_files[0]
        print(f"\nUsing slate: {slate_path.name}")
        
        # Load slate and extract player names
        try:
            with open(slate_path, 'r') as f:
                slate_data = json.load(f)
            
            # Extract from 'plays' array
            if 'plays' in slate_data:
                for play in slate_data['plays']:
                    player = play.get('player')
                    if player and player not in player_names:
                        player_names.append(player)
            
            if not player_names:
                print("\n⚠️  No players found in slate")
                return
                
            print(f"\nFound {len(player_names)} players:")
            for i, name in enumerate(player_names[:10], 1):
                print(f"  {i}. {name}")
            if len(player_names) > 10:
                print(f"  ... and {len(player_names) - 10} more")
            
        except Exception as e:
            print(f"\n⚠️  Error loading slate: {e}")
            return
    
    elif choice == '2':
        # Manual entry
        print("\nEnter player names (comma-separated):")
        print("Example: Mohamed Salah, Erling Haaland, Harry Kane")
        
        names_input = input("\nPlayers: ").strip()
        if not names_input:
            print("\nCancelled.")
            return
        
        player_names = [name.strip() for name in names_input.split(',') if name.strip()]
        
        if not player_names:
            print("\nNo valid player names entered.")
            return
    
    elif choice == '0':
        print("\nCancelled.")
        return
    
    else:
        print("\nInvalid option.")
        return
    
    # Fetch stats from API
    print(f"\nFetching stats for {len(player_names)} players...")
    print("(This may take 30-60 seconds depending on API rate limits)\n")
    
    stats = fetch_soccer_stats_for_slate(player_names)
    
    if not stats:
        print("\n❌ No stats fetched. Check API key and internet connection.")
        return
    
    # Save to player_stats.json
    output_path = SOCCER_DIR / 'data' / 'player_stats_api.json'
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n✅ SUCCESS!")
    print(f"   Fetched stats for {len(stats)}/{len(player_names)} players")
    print(f"   Saved to: {output_path}")
    print(f"\n💡 TIP: Stats saved to player_stats_api.json")
    print(f"   You can now import these via option [6]")
    print(f"   Or run option [5] to analyze props with fresh stats!")


def _view_file(path: Path, *, max_lines: int = 200) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"\nFailed to read {path}: {e}")
        return

    lines = text.splitlines()
    head = lines[:max_lines]
    print("\n" + "-" * 60)
    print(f"{path}")
    print("-" * 60)
    print("\n".join(head))
    if len(lines) > max_lines:
        print("\n... (truncated) ...")


def _view_latest_report() -> None:
    p = _latest("soccer_report_*.txt")
    if not p:
        print("\nNo soccer reports found in soccer/outputs")
        return
    _view_file(p)


def _view_latest_risk_first() -> None:
    p = _latest("soccer_RISK_FIRST_*.json")
    if not p:
        print("\nNo soccer RISK_FIRST outputs found in soccer/outputs")
        return

    # Pretty-print first few edges for readability
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _view_file(p)
        return

    if not isinstance(data, list):
        _view_file(p)
        return

    print("\nLatest SOCCER RISK_FIRST (top 15 edges)")
    print("-" * 60)
    for i, e in enumerate(data[:15], 1):
        if not isinstance(e, dict):
            continue
        print(
            f"{i:>2}. {e.get('tier')} {e.get('match')} | {e.get('market')} {e.get('direction')} {e.get('line')} | p={float(e.get('probability', 0.0)) * 100:.1f}%"
        )


def show_menu() -> None:
    while True:
        _print_header()
        print("\nOptions:")
        print("  [1] Run Soccer Match Pipeline (team markets, manual xG)")
        print("  [2] View Latest Soccer Report")
        print("  [3] View Latest Soccer RISK_FIRST JSON")
        print("  [4] Paste Underdog Soccer Slate -> Save JSON (props)")
        print("  [5] ⚽ Analyze Player Props (Monte Carlo)")
        print("  [6] Import Player Stats (JSON)")
        print("  [7] 🌐 Fetch Stats from API-Football (Real-time)")
        print("  [0] Back")

        choice = input("\nSelect option: ").strip().upper()
        if choice == "1":
            _run_pipeline_prompt()
            _pause()
        elif choice == "2":
            _view_latest_report()
            _pause()
        elif choice == "3":
            _view_latest_risk_first()
            _pause()
        elif choice == "4":
            _ingest_underdog_soccer_paste()
            _pause()
        elif choice == "5":
            _run_props_analysis_prompt()
            _pause()
        elif choice == "6":
            _import_player_stats_json()
            _pause()
        elif choice == "7":
            _fetch_stats_from_api()
            _pause()
        elif choice == "0":
            return
        else:
            print("\nInvalid option")
            _pause()
