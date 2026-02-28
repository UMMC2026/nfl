"""
Tennis Module - Main Entry Point
================================
Orchestrates the full tennis pipeline.

Order of operations:
1. ingest_tennis.py
2. generate_tennis_edges.py
3. score_tennis_edges.py
4. validate_tennis_output.py  ← HARD GATE
5. render_tennis_report.py
"""

import json
import os
import sys
import subprocess
from pathlib import Path

# Add tennis directory and project root to path
TENNIS_DIR = Path(__file__).parent
PROJECT_ROOT = TENNIS_DIR.parent
sys.path.insert(0, str(TENNIS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# Import tennis modules AFTER path setup
# Delayed imports to ensure path is set first
def _import_tennis_modules():
    """Import tennis modules after path is configured."""
    global interactive_ingest, load_latest_slate, parse_tennis_paste, save_slate
    global generate_all_edges, print_edges_summary
    global score_all_edges, print_scored_summary
    global run_validation, render_report, seed_initial_ratings
    
    from ingest_tennis import interactive_ingest, load_latest_slate, parse_tennis_paste, save_slate
    from generate_tennis_edges import generate_all_edges, print_edges_summary
    from score_tennis_edges import score_all_edges, print_scored_summary
    from validate_tennis_output import run_validation
    from render_tennis_report import render_report
    from tennis_elo import seed_initial_ratings

# Import modules now
_import_tennis_modules()


def run_full_pipeline(skip_ingest: bool = False) -> bool:
    """
    Run the complete tennis analysis pipeline.
    
    Returns: True if successful, False if validation failed
    """
    print("\n" + "=" * 70)
    print("🎾 TENNIS ANALYSIS PIPELINE v1.0")
    print("   Singles only | Match Winner only | Pre-match only")
    print("=" * 70)
    
    # Step 0: Ensure Elo ratings exist
    seed_initial_ratings()
    
    # Step 1: Ingest (optional)
    slate_path = None
    if not skip_ingest:
        print("\n[1/5] INGEST MATCHES")
        print("-" * 40)
        slate = load_latest_slate()
        if slate:
            slate_file = slate.get("_slate_file") or "(unknown file)"
            slate_mtime = slate.get("_slate_mtime") or "(unknown mtime)"
            print(f"  Found existing slate: {slate.get('match_count', 0)} matches")
            print(f"  Slate file: {slate_file}")
            print(f"  Updated:   {slate_mtime}")
            use_existing = input("  Use existing slate? [Y/n]: ").strip().lower()
            if use_existing == 'n':
                saved = interactive_ingest()
                # If user explicitly declined the existing slate, we must not
                # continue with stale data when the new ingest failed or was not saved.
                if not saved:
                    print("\n✗ Ingest did not produce a new saved slate. Aborting pipeline to avoid using stale slate.")
                    print("  Tip: For Odds API ingest, confirm ODDS_API_KEY and the tour sport_key mapping in .env.")
                    return False
                slate_path = saved
        else:
            saved = interactive_ingest()
            if not saved:
                print("\n✗ Ingest did not produce a saved slate. Aborting pipeline.")
                return False
            slate_path = saved
    
    # Step 2: Generate edges
    print("\n[2/5] GENERATE EDGES")
    print("-" * 40)
    edges = generate_all_edges(slate_file=Path(slate_path)) if slate_path else generate_all_edges()
    
    if not edges:
        print("✗ No edges generated - aborting")
        return False
    
    # Step 2.5: Apply direction gate (FUOOM bias protection)
    print("\n[2.5/5] APPLY DIRECTION GATE")
    print("-" * 40)
    from tennis.direction_gate import apply_direction_gate
    
    # Only check playable edges; detect platform constraint
    playable_tiers = {"SLAM", "STRONG", "LEAN"}
    playable_edges = [e for e in edges if e.get("tier", "").upper() in playable_tiers]
    prop_dirs = set(e.get("direction", "").upper() for e in edges if e.get("direction"))
    norm_dirs = set()
    for d in prop_dirs:
        if d in ("HIGHER", "OVER"):
            norm_dirs.add("OVER")
        elif d in ("LOWER", "UNDER"):
            norm_dirs.add("UNDER")
    source_one_dir = len(norm_dirs) == 1
    
    gate_input = playable_edges if playable_edges else edges
    gate_result = apply_direction_gate(
        gate_input, context={},
        source_all_same_direction=source_one_dir,
    )
    if not gate_result:
        return False
    # Keep original edges list (gate only validates, doesn't filter here)
    print(f"  ✓ Direction Gate PASSED ({len(gate_result)} edges)")
    
    # Step 2.6: Save to calibration tracker (after gate)
    # Note: This step would normally save the scored edges
    # For match winner pipeline, edges format may differ
    # Actual calibration save happens in props pipeline (_run_props_analysis)
    
    # Step 3: Score edges
    print("\n[3/5] SCORE EDGES")
    print("-" * 40)
    scored = score_all_edges()
    
    # Step 4: Validate (HARD GATE)
    print("\n[4/5] VALIDATE OUTPUT — HARD GATE")
    print("-" * 40)
    valid = run_validation()
    
    if not valid:
        print("\n⛔ PIPELINE ABORTED — Validation failed")
        return False

    # Export governed signals for downstream Telegram/parlays.
    # Match-winner pipeline writes to the same signals_latest file, but only
    # replaces the match_winner subset (props signals are preserved).
    try:
        scored_path = TENNIS_DIR / "outputs" / "tennis_scored_latest.json"
        if scored_path.exists():
            scored_output = json.loads(scored_path.read_text(encoding="utf-8"))
            from tennis.tennis_quant_export import export_tennis_match_winner_quant_artifacts

            export_tennis_match_winner_quant_artifacts(
                scored_output,
                source={
                    "pipeline": "match_winner",
                },
            )
            print("✓ Exported governed match-winner signals (outputs/tennis_signals_latest.json)")
    except Exception as e:
        print(f"\n⚠️ Tennis match-winner quant export skipped: {e}")
    
    # Step 5: Render report
    print("\n[5/5] RENDER REPORT")
    print("-" * 40)
    report = render_report()
    print(report)
    
    print("\n" + "=" * 70)
    print("✅ TENNIS PIPELINE COMPLETE")
    print("=" * 70)
    
    return True


def quick_analyze(raw_text: str) -> bool:
    """
    Quick analysis from raw paste.
    
    Skips interactive ingest.
    """
    print("\n🎾 TENNIS QUICK ANALYSIS")
    print("-" * 40)
    
    # Parse and save
    matches = parse_tennis_paste(raw_text)
    if not matches:
        print("✗ No valid matches parsed")
        return False
    
    print(f"✓ Parsed {len(matches)} matches")
    save_slate(matches, "quick_analysis")
    
    # Run pipeline
    return run_full_pipeline(skip_ingest=True)


def _is_props_data(text: str) -> bool:
    """Detect if input looks like Underdog props paste data START.
    
    Be conservative - only trigger on clear prop data patterns,
    not on single keywords like 'Higher' or 'Lower'.
    """
    text_lower = text.lower().strip()
    
    # Single keywords that appear in props but shouldn't trigger alone
    single_keywords = {'higher', 'lower', 'over', 'under', 'games played', 
                       'games won', 'sets played', 'aces', 'double faults'}
    if text_lower in single_keywords:
        return False
    
    # Check if it's just a number (line value like 21.5)
    import re
    if re.match(r'^\d+\.?\d*$', text.strip()):
        return False
    
    # Check if it looks like a multiplier alone (e.g., "1.03x", "0.94x")
    if re.match(r'^\d+\.\d+x$', text.strip()):
        return False
    
    # STRONG indicators - these clearly indicate props data
    strong_indicators = [
        'athlete or team avatar',  # Underdog header
        'vs',                       # Match format "Player vs Player"
        ' cst', ' est', ' pst',     # Time zone in match time
        'am cst', 'pm cst',         # Time format
        'am est', 'pm est',
    ]
    
    for indicator in strong_indicators:
        if indicator in text_lower:
            return True
    
    # Check if it's a player name with match info (e.g., "Parks vs Avanesyan - 12:40PM CST")
    if ' vs ' in text_lower and ('-' in text or ':' in text):
        return True
    
    return False


def _run_props_analysis(initial_lines: list = None):
    """Run Monte Carlo props analysis with paste input - using CALIBRATED engine."""
    from tennis.calibrated_props_engine import CalibratedTennisPropsEngine
    
    print("\n" + "=" * 90)
    print("🎾 TENNIS PROPS - CALIBRATED MONTE CARLO (AUTO-DETECTED)")
    print("=" * 90)
    
    if initial_lines:
        # Already have lines from auto-detect
        lines = initial_lines
    else:
        # Manual mode - collect paste
        print("\nPaste Underdog tennis props below.")
        print("Type 'END' on a new line when finished.\n")
        
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == 'END':
                    break
                lines.append(line)
            except (EOFError, KeyboardInterrupt):
                break
    
    if not lines:
        print("\n[!] No input received")
        return
    
    paste = '\n'.join(lines)
    
    # Save the slate for Telegram to use
    from pathlib import Path
    from datetime import datetime
    slate_dir = Path(__file__).parent / "saved_slates"
    slate_dir.mkdir(exist_ok=True)
    slate_file = slate_dir / f"slate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    slate_file.write_text(paste, encoding='utf-8')
    
    # Run CALIBRATED Monte Carlo pipeline (uses Tennis Abstract 2024 data)
    print("\n🔄 Running CALIBRATED Monte Carlo analysis...")
    print("   • Using Tennis Abstract 2024 data (1700+ matches)")
    print("   • Fetching real player statistics")
    print("   • Running 2,000 simulations per prop")
    print("   • Applying SOP v2.1 confidence caps\n")
    
    try:
        engine = CalibratedTennisPropsEngine()
        
        # Parse props from paste
        props = engine.parse_underdog_paste(paste)
        
        if not props:
            print("⚠️ No valid props found in paste")
            engine.close()
            return
        
        print(f"  ✓ Parsed {len(props)} props")
        
        # Analyze slate
        results = engine.analyze_slate(props, surface="Hard")
        
        # DIRECTION GATE (FUOOM bias protection)
        print("\n🛡️ Applying Direction Gate (FUOOM protection)...")
        
        # Extract PLAYABLE edges only (SLAM/STRONG/LEAN) for bias check.
        # NO_PLAY edges carry the raw input direction and would inflate
        # the bias count even though the model did NOT recommend them.
        PLAYABLE_TIERS = {'SLAM', 'STRONG', 'LEAN'}
        all_edges = []
        for tier_name, tier_edges in results.get('tiers', {}).items():
            if tier_name not in PLAYABLE_TIERS:
                continue
            for edge in tier_edges:
                # Convert to standard edge format for gate
                all_edges.append({
                    'player': edge.get('player', ''),
                    'stat': edge.get('stat', ''),
                    'line': edge.get('line', 0),
                    'direction': edge.get('direction', ''),
                    'probability': edge.get('probability', edge.get('confidence', 0)),
                    'tier': tier_name
                })
        
        if all_edges:
            from tennis.direction_gate import apply_direction_gate

            # Detect platform constraint: if ALL parsed props share the
            # same direction, the bias is in the source board, not our
            # model.  Pass this flag so the gate warns instead of aborting.
            prop_directions = set()
            for p in props:
                d = (p.get('direction') or p.get('pick_type') or '').upper()
                if d in ('HIGHER', 'OVER'):
                    prop_directions.add('OVER')
                elif d in ('LOWER', 'UNDER'):
                    prop_directions.add('UNDER')
            source_one_dir = len(prop_directions) == 1

            filtered_edges = apply_direction_gate(
                all_edges, context={},
                source_all_same_direction=source_one_dir,
            )
            
            if not filtered_edges:
                print("\n⛔ DIRECTION GATE FAILED — Structural bias detected")
                print("   Aborting to prevent betting into model weakness")
                engine.close()
                return
            
            print(f"   ✓ Direction Gate PASSED ({len(filtered_edges)} edges)")
            
            # Rebuild tiers with filtered edges
            # Create set of (player, stat, line, direction) tuples for fast lookup
            filtered_set = {
                (e.get('player', ''), e.get('stat', ''), e.get('line', 0), e.get('direction', ''))
                for e in filtered_edges
            }
            
            for tier_name, tier_edges in results.get('tiers', {}).items():
                results['tiers'][tier_name] = [
                    e for e in tier_edges
                    if (e.get('player', ''), e.get('stat', ''), e.get('line', 0), e.get('direction', '')) in filtered_set
                ]
            
            # CALIBRATION TRACKING: Save filtered picks for accuracy monitoring
            try:
                from tennis.calibration_saver import save_picks_to_calibration
                save_picks_to_calibration(results)
            except Exception as e:
                print(f"   ⚠️ Calibration tracking failed: {e}")
        else:
            print("   ⚠️ No edges to check (0 playable)")

        # Export governed, quant-compatible signals (source of truth for Telegram/parlays)
        try:
            from tennis.tennis_quant_export import export_tennis_props_quant_artifacts

            export_tennis_props_quant_artifacts(
                results,
                source={
                    "ingest": "underdog_paste",
                    "surface": "Hard",
                },
            )
        except Exception as e:
            print(f"\n⚠️ Tennis quant export skipped: {e}")
        
        # Generate cheatsheet
        cheatsheet = engine.generate_cheatsheet(results)
        print(cheatsheet)
        
        # Save to file
        from datetime import datetime
        from pathlib import Path
        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        filename = f"TENNIS_CALIBRATED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = outputs_dir / filename
        filepath.write_text(cheatsheet, encoding='utf-8')
        print(f"\n✓ Cheat sheet saved: {filepath}")
        
        # CROSS-SPORT DATABASE: Save top picks for parlay builder
        try:
            from engine.daily_picks_db import save_top_picks
            
            tiers = results.get('tiers', {})
            tennis_edges = []
            for tier in ['SLAM', 'STRONG', 'LEAN']:
                for r in tiers.get(tier, []):
                    prob = r.get('probability', r.get('confidence', 0.5))
                    if prob <= 1:
                        prob *= 100
                    tennis_edges.append({
                        "player": r.get("player", ""),
                        "stat": r.get("stat", ""),
                        "line": r.get("line", 0),
                        "direction": r.get("direction", ""),
                        "probability": prob,
                        "tier": tier
                    })
            
            if tennis_edges:
                saved = save_top_picks(tennis_edges, "TENNIS", top_n=5)
                print(f"✓ Cross-Sport DB: Saved {saved} Tennis picks")
        except ImportError:
            pass  # Module not available
        except Exception as e:
            print(f"⚠️ Cross-Sport DB: {e}")
        
        # Summary
        tiers = results.get('tiers', {})
        print(f"\n📊 ANALYSIS SUMMARY:")
        print(f"   Props analyzed: {len(results.get('results', []))}")
        print(f"   Players with data: {len(results.get('players_analyzed', []))}")
        print(f"   SLAM: {len(tiers.get('SLAM', []))} | STRONG: {len(tiers.get('STRONG', []))} | LEAN: {len(tiers.get('LEAN', []))}")
        
        if results.get('players_not_found'):
            print(f"   ⚠️ No data for: {', '.join(results['players_not_found'])}")
        
        # Show Telegram hint instead of interactive prompt
        playable = tiers.get('SLAM', []) + tiers.get('STRONG', []) + tiers.get('LEAN', [])
        if playable:
            print("\n📱 To send to Telegram: press [T] from menu")
        else:
            print("\n⚠️  No playable edges found (all props < 55% probability)")
        
        engine.close()
    
    except Exception as e:
        print(f"\n✗ Error running Monte Carlo analysis: {e}")
        import traceback
        traceback.print_exc()


def _export_printable_report(results: dict) -> str:
    """Generate a clean, printable text report for tennis analysis."""
    from datetime import datetime
    
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("  TENNIS PROPS ANALYSIS - PRINTABLE REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    lines.append(f"  Surface: {results.get('surface', 'Hard')}")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary
    tiers = results.get('tiers', {})
    total_plays = len(tiers.get('SLAM', [])) + len(tiers.get('STRONG', [])) + len(tiers.get('LEAN', []))
    
    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Total Playable Picks:  {total_plays}")
    lines.append(f"  SLAM (70%+):           {len(tiers.get('SLAM', []))}")
    lines.append(f"  STRONG (62-70%):       {len(tiers.get('STRONG', []))}")
    lines.append(f"  LEAN (55-62%):         {len(tiers.get('LEAN', []))}")
    lines.append("")
    
    # Picks by tier
    for tier, tier_name in [('SLAM', 'SLAM PICKS (HIGHEST CONFIDENCE)'), 
                            ('STRONG', 'STRONG PICKS'), 
                            ('LEAN', 'LEAN PICKS')]:
        tier_results = tiers.get(tier, [])
        if not tier_results:
            continue
        
        lines.append("")
        lines.append(tier_name)
        lines.append("=" * 60)
        lines.append(f"{'PLAYER':<25} {'PICK':<15} {'LINE':<8} {'PROB':<8} {'SAMPLE'}")
        lines.append("-" * 60)
        
        for r in tier_results:
            profile = r.get('profile_data', {})
            n = profile.get('n_matches', '?')
            direction = r.get('direction', '').upper()
            stat = r.get('stat', '')
            line_val = r.get('line', 0)
            prob = r.get('probability', r.get('confidence', 0))
            
            pick_text = f"{direction} {stat}"[:20]
            
            lines.append(f"  {r['player']:<25} {pick_text:<21} {line_val:<8} {prob:.0f}%     n={n}")
        
        lines.append("")
    
    # Warnings
    if results.get('players_not_found'):
        lines.append("")
        lines.append("PLAYERS WITHOUT DATA (SKIPPED)")
        lines.append("-" * 40)
        for p in results['players_not_found']:
            lines.append(f"  - {p}")
        lines.append("")
    
    # Footer
    lines.append("")
    lines.append("=" * 80)
    lines.append("RULES (SOP v2.1)")
    lines.append("-" * 40)
    lines.append("  * One player, one bet per match")
    lines.append("  * Never combine correlated stats (Games Won + Sets)")
    lines.append("  * Verify surface matches props (Hard/Clay/Grass)")
    lines.append("  * Probability = Monte Carlo simulation (2,000 runs)")
    lines.append("=" * 80)
    
    return '\n'.join(lines)


def _show_reports_menu():
    """Reporting menu for tennis outputs (props + daily engine)."""
    outputs_dir = TENNIS_DIR / "outputs"

    if not outputs_dir.exists():
        print("\n  No tennis outputs found yet.")
        return

    while True:
        print("\n" + "=" * 60)
        print("  TENNIS REPORTING MENU")
        print("=" * 60)
        print("  Props Reports:")
        print("    [1] View latest props cheatsheet (calibrated)")
        print("    [2] Generate AI commentary for props 🤖")
        print()
        print("  Daily Engine Reports:")
        print("    [3] View latest DAILY engine report (totals/sets/aces)")
        print("    [4] View latest Daily Top-20 AI report")
        print()
        print("  [5] List recent tennis output files")
        print("  [0] Back")
        print()

        choice = input("  Select option: ").strip().upper()

        if choice == "1":
            # Latest calibrated props report
            reports = sorted(outputs_dir.glob("TENNIS_CALIBRATED_*.txt"), reverse=True)
            if not reports:
                reports = sorted(outputs_dir.glob("tennis_*.txt"), reverse=True)
            if not reports:
                print("\n  No props reports found. Run [1] Analyze Props first.")
            else:
                latest = reports[0]
                print(f"\n  Latest Props Report: {latest.name}")
                print("-" * 60)
                try:
                    print(latest.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"  Error reading: {e}")

        elif choice == "2":
            # Generate AI commentary for latest calibrated props
            from tennis.generate_props_ai_commentary import save_props_ai_report
            
            reports = sorted(outputs_dir.glob("TENNIS_CALIBRATED_*.txt"), reverse=True)
            if not reports:
                print("\n  No props reports found. Run [1] Analyze Props first.")
            else:
                latest = reports[0]
                print(f"\n  📊 Analyzing: {latest.name}")
                print(f"  🤖 Generating AI commentary...")
                
                use_ai = bool(os.getenv("DEEPSEEK_API_KEY"))
                if not use_ai:
                    print("  ⚠️  DEEPSEEK_API_KEY not found — using fallback narratives")
                
                output_path = save_props_ai_report(latest, use_ai=use_ai)
                
                if output_path:
                    print(f"\n  ✅ AI Report saved: {output_path.name}")
                    print("\n" + "-" * 60)
                    try:
                        print(output_path.read_text(encoding='utf-8'))
                    except Exception as e:
                        print(f"  Error reading: {e}")
                else:
                    print("  ✗ Failed to generate AI report")

        elif choice == "3":
            # Latest daily engine report rendered from merged JSON
            merged_files = sorted(outputs_dir.glob("tennis_merged_*.json"), reverse=True)
            if not merged_files:
                print("\n  No daily engine outputs found. Run Tennis Daily Run first.")
            else:
                latest = merged_files[0]
                try:
                    from tennis.render.render_report import render_report as daily_render_report

                    data = json.loads(latest.read_text(encoding="utf-8"))
                    report = daily_render_report(data, "text")
                    print(f"\n  Latest DAILY Report: {latest.name}")
                    print("-" * 60)
                    print(report)
                except Exception as e:
                    print(f"\n  Error rendering daily report: {e}")

        elif choice == "4":
            # Latest Top-20 AI report from tennis/run_daily.py
            ai_reports = sorted(outputs_dir.glob("tennis_TOP20_AI_REPORT_*.txt"), reverse=True)
            if not ai_reports:
                print("\n  No Top-20 AI reports found. Run Tennis Daily Run first.")
            else:
                latest = ai_reports[0]
                print(f"\n  Latest Top-20 AI Report: {latest.name}")
                print("-" * 60)
                try:
                    print(latest.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"  Error reading: {e}")

        elif choice == "5":
            # List a quick inventory of recent tennis outputs
            files = sorted(outputs_dir.glob("tennis_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
            files_txt = sorted(outputs_dir.glob("TENNIS_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
            combined = sorted(set(files + files_txt), key=lambda p: p.stat().st_mtime, reverse=True)

            if not combined:
                print("\n  No tennis outputs found.")
            else:
                print("\n  Recent tennis outputs:")
                for f in combined[:15]:
                    ts = f.stat().st_mtime
                    from datetime import datetime

                    ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    print(f"   • {f.name:40}  {ts_str}")

        elif choice == "0":
            return
        else:
            print("\n  Invalid choice.")


def _show_ingestion_menu():
    """Data / ingestion menu for Sackmann + backups."""
    scripts_dir = TENNIS_DIR / "scripts"
    python_exe = sys.executable or "python"

    while True:
        print("\n" + "=" * 60)
        print("  TENNIS DATA / INGESTION MENU")
        print("=" * 60)
        print("  [1] Fetch Sackmann match data (ATP/WTA)")
        print("  [2] Update player_stats.json from Sackmann (L10)")
        print("  [3] Run Tier 1 upgrade (fetch + L10 + validate)")
        print("  [4] Backup tennis data (FULL)")
        print("  [5] Show tennis backup status")
        print("  [0] Back")
        print()

        choice = input("  Select option: ").strip().upper()

        try:
            if choice == "1":
                year = input("   Year to fetch (blank = current): ").strip()
                cmd = [python_exe, str(scripts_dir / "fetch_sackmann_data.py")]
                if year:
                    cmd += ["--year", year]
                print("\n  🔄 Fetching Sackmann data...\n")
                subprocess.run(cmd, check=False)

            elif choice == "2":
                year = input("   Year to analyze (blank = current): ").strip()
                window = input("   Rolling window size (default 10): ").strip()
                dry = input("   Dry-run only? [y/N]: ").strip().lower() == "y"
                cmd = [python_exe, str(scripts_dir / "update_stats_from_sackmann.py")]
                if year:
                    cmd += ["--year", year]
                if window:
                    cmd += ["--window", window]
                if dry:
                    cmd.append("--dry-run")
                print("\n  🔄 Updating player stats from Sackmann...\n")
                subprocess.run(cmd, check=False)

            elif choice == "3":
                year = input("   Year for Tier 1 upgrade (blank = current): ").strip()
                cmd = [python_exe, str(scripts_dir / "tier1_upgrade.py")]
                if year:
                    cmd += ["--year", year]
                print("\n  🔄 Running Tier 1 upgrade (this may take a while)...\n")
                subprocess.run(cmd, check=False)

            elif choice == "4":
                cmd = [python_exe, str(scripts_dir / "backup_tennis_data.py"), "--full"]
                print("\n  🔄 Creating FULL tennis backup...\n")
                subprocess.run(cmd, check=False)

            elif choice == "5":
                cmd = [python_exe, str(scripts_dir / "backup_tennis_data.py"), "--status"]
                print("\n  🔎 Tennis backup status...\n")
                subprocess.run(cmd, check=False)

            elif choice == "0":
                return
            else:
                print("\n  Invalid choice.")
        except Exception as e:
            print(f"\n  ✗ Error running command: {e}")


def _show_daily_menu():
    """Daily run / backtest menu (tees off tennis/run_daily.py)."""
    python_exe = sys.executable or "python"
    run_daily_path = TENNIS_DIR / "run_daily.py"

    while True:
        print("\n" + "=" * 60)
        print("  TENNIS DAILY PIPELINE MENU")
        print("=" * 60)
        print("  [1] Run Tennis Daily Pipeline (FULL)")
        print("  [2] Run Tennis Daily Pipeline (DRY RUN)")
        print("  [0] Back")
        print()

        choice = input("  Select option: ").strip().upper()

        if choice == "1":
            print("\n  🔄 Running Tennis Daily Pipeline (FULL)...\n")
            subprocess.run([python_exe, str(run_daily_path)], check=False)
        elif choice == "2":
            print("\n  🔄 Running Tennis Daily Pipeline (DRY RUN)...\n")
            subprocess.run([python_exe, str(run_daily_path), "--dry-run"], check=False)
        elif choice == "0":
            return
        else:
            print("\n  Invalid choice.")


def run_tennis_auto_ingest():
    """🔌 Auto-ingest Tennis props via Playwright (DK Pick6/PrizePicks/Underdog)."""
    print("\n" + "=" * 70)
    print("  🔌 AUTO-INGEST TENNIS PROPS (Playwright)")
    print("=" * 70)
    print("\n  This uses the universal Playwright scraper.")
    print("  Tip: Persistent profile mode keeps you logged in.")
    
    try:
        from ingestion.prop_ingestion_pipeline import interactive_browse_persistent, run_pipeline
    except Exception as e:
        print(f"\n  ❌ Could not import ingestion pipeline: {e}")
        print("     Expected: ingestion/prop_ingestion_pipeline.py")
        return
    
    print("\n  Choose ingest mode:")
    print("    [1] Persistent browser (recommended) — login once, navigate to Tennis props")
    print("    [2] Quick scrape all sites — may require logins each run")
    mode = input("\n  Select [1/2] (default 1): ").strip() or "1"
    
    try:
        if mode.strip() == "2":
            run_pipeline(sites=["draftkings", "prizepicks", "underdog"], headless=False)
        else:
            interactive_browse_persistent()
    except Exception as e:
        print(f"\n  ❌ Ingest failed: {e}")
        return
    
    from pathlib import Path
    scraped_latest = Path("outputs/props_latest.json")
    
    if not scraped_latest.exists():
        print(f"\n  ❌ Missing scraped output: {scraped_latest}")
        return
    
    try:
        import json
        data = json.loads(scraped_latest.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\n  ❌ Could not read scraped props JSON: {e}")
        return
    
    props = data.get("props") if isinstance(data, dict) else None
    if not isinstance(props, list) or not props:
        print("\n  ❌ No props found in scraped output.")
        return
    
    print(f"\n  ✅ Ingested {len(props)} props successfully!")
    print(f"  📁 Saved to: outputs/props_latest.json")
    print(f"  ⚠️  Note: Ensure you scraped Tennis props in the browser")
    
    # IMMEDIATE ANALYSIS OPTION (Cohesive flow)
    print("\n" + "-" * 70)
    auto_analyze = input("  🔬 Run calibrated analysis now? [Y/n]: ").strip().lower()
    
    if auto_analyze in ['', 'y', 'yes']:
        print("\n  🔄 Converting props to analysis format...")
        
        # Convert JSON props to paste format for engine compatibility
        paste_lines = _convert_json_to_paste_format(props)
        
        if paste_lines:
            # Trigger calibrated analysis with converted data
            print(f"  ✓ Converted {len(props)} props for analysis\n")
            _run_props_analysis(initial_lines=paste_lines)
        else:
            print("  ⚠️ Could not convert props for analysis")
            print("     Tip: Try manual paste mode with [1]")
    else:
        print(f"\n  ➡️  Later: Select [1] from menu to analyze")


def _convert_json_to_paste_format(props_json: list) -> list:
    """
    Convert JSON props from Playwright scraper to paste format.
    
    JSON format: {player, stat, line, direction, source}
    Paste format: 
        Player Name
        25.5
        Aces
        Higher
    """
    lines = []
    
    for prop in props_json:
        player = prop.get('player')
        stat = prop.get('stat')
        line = prop.get('line')
        direction = prop.get('direction')
        
        # Skip incomplete props
        if not all([player, stat, line, direction]):
            continue
        
        # Format as paste lines
        lines.append(player)
        lines.append(str(line))
        lines.append(stat.title())  # "aces" → "Aces"
        lines.append(direction.title())  # "higher" → "Higher"
    
    return lines if lines else None



def show_menu():
    """Interactive tennis menu."""
    while True:
        print("\n" + "=" * 70)
        print("  🎾 TENNIS PROPS ANALYZER — Risk-First Pipeline")
        print("=" * 70)
        print()
        print("  📥 INGESTION")
        print("    [0] Auto-Ingest + Analyze — Playwright scraper → Calibrated MC")
        print("    [O] Ingest via Odds API — DFS Props (no-scrape)")
        print()
        print("  🔬 ANALYSIS (Manual Mode)")
        print("    [1] Analyze Props — Paste Mode (for manual copy/paste)")
        print("        → Paste ALL props, type END when done")
        print()
        print("  📊 REPORTS")
        print("    [2] View Latest Props Report")
        print("    [3] Export Printable Report")
        print("    [R] Full Reporting Menu (props + daily + Top-20 AI)")
        print()
        print("  🏆 MATCH WINNER PIPELINE")
        print("    [W]  Ingest + Analyze (includes Odds API)")
        print("    [WL] Analyze Latest Saved Slate")
        print()
        print("  📡 BROADCAST")
        print("    [T] Send Report to Telegram")
        print("    [P] Send Parlay Picks to Telegram")
        print()
        print("  ⚙️ MANAGEMENT")
        print("    [D] Daily Pipeline Menu")
        print("    [I] Data & Ingestion Menu (Sackmann, backups)")
        print()
        print("  [Q] Back to Main Menu")
        print("=" * 70)
        
        choice = input("  → Select option (or paste props): ").strip().upper()
        
        # Auto-ingest handler
        if choice == "0":
            run_tennis_auto_ingest()
            input("\n  ✓ Press Enter to continue...")
            continue
        
        # SMART AUTO-DETECT: Check if user pasted props data instead of menu option
        if choice and choice not in ['0', '1', '2', '3', 'T', 'P', 'W', 'WL', 'O', 'R', 'D', 'I', 'Q'] and _is_props_data(choice):
            print("\n  Props detected! Collecting all pasted data...")
            print("  Type 'END' on a new line when finished pasting.\n")
            
            # Collect all pasted lines
            all_lines = [choice]
            while True:
                try:
                    line = input()
                    if line.strip().upper() == 'END':
                        break
                    all_lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            
            print("\n  Starting analysis...")
            _run_props_analysis(initial_lines=all_lines)
            input("\nPress Enter to continue...")
            continue
        
        if choice == "1":
            # Main option: Analyze Props (Monte Carlo)
            _run_props_analysis()
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            # View latest report
            outputs_dir = TENNIS_DIR / "outputs"
            if not outputs_dir.exists():
                print("\n  No reports found. Run analysis first.")
            else:
                reports = sorted(outputs_dir.glob("TENNIS_CALIBRATED_*.txt"), reverse=True)
                if not reports:
                    reports = sorted(outputs_dir.glob("tennis_*.txt"), reverse=True)
                
                if reports:
                    latest = reports[0]
                    print(f"\n  Latest Report: {latest.name}")
                    print("-" * 60)
                    try:
                        print(latest.read_text(encoding='utf-8'))
                    except Exception as e:
                        print(f"  Error reading: {e}")
                else:
                    print("\n  No reports found. Run analysis first.")
        
        elif choice == "3":
            # Export printable report
            outputs_dir = TENNIS_DIR / "outputs"
            reports = sorted(outputs_dir.glob("TENNIS_CALIBRATED_*.txt"), reverse=True) if outputs_dir.exists() else []
            
            if not reports:
                print("\n  No analysis found. Run [1] first to analyze props.")
            else:
                # Find the most recent results JSON (or regenerate)
                print("\n  Exporting printable version of latest analysis...")
                
                # Read the latest cheatsheet and reformat
                latest = reports[0]
                try:
                    content = latest.read_text(encoding='utf-8')
                    
                    # Create printable filename
                    from datetime import datetime
                    printable_name = f"TENNIS_PRINTABLE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    printable_path = outputs_dir / printable_name
                    
                    # Add print-friendly header
                    printable = []
                    printable.append("=" * 80)
                    printable.append("        TENNIS PROPS - PRINTABLE CHEATSHEET")
                    printable.append(f"        {datetime.now().strftime('%A, %B %d, %Y')}")
                    printable.append("=" * 80)
                    printable.append("")
                    printable.append(content)
                    printable.append("")
                    printable.append("=" * 80)
                    printable.append("END OF REPORT")
                    printable.append("=" * 80)
                    
                    printable_path.write_text('\n'.join(printable), encoding='utf-8')
                    
                    print(f"\n  Saved: {printable_path}")
                    print(f"  Location: {printable_path.absolute()}")
                    print("\n  Ready to print!")
                except Exception as e:
                    print(f"  Error: {e}")

        elif choice == "R":
            _show_reports_menu()

        elif choice == "D":
            _show_daily_menu()

        elif choice == "O":
            # Odds API tennis DFS props (no-scrape)
            try:
                from tennis.oddsapi_dfs_props import interactive_run

                interactive_run()
            except Exception as e:
                print(f"\n  ✗ Odds API DFS props run failed: {e}")

        elif choice == "I":
            _show_ingestion_menu()
        
        elif choice == "T":
            # Send full report to Telegram
            _send_report_to_telegram()
        
        elif choice == "P":
            # Send parlay picks to Telegram
            _send_parlays_to_telegram()

        elif choice == "W":
            # Match Winner pipeline (ingest includes Odds API)
            print("\n🎾 Switching to Tennis Match Winner pipeline...")
            run_full_pipeline(skip_ingest=False)

        elif choice == "WL":
            # Match Winner pipeline using latest saved slate
            print("\n🎾 Running Tennis Match Winner pipeline using latest saved slate...")
            run_full_pipeline(skip_ingest=True)
        
        elif choice == "Q":
            break

        else:
            print("\n  Invalid choice.")
        
        input("\nPress Enter to continue...")


def _send_report_to_telegram():
    """Send professional tennis report to Telegram."""
    from datetime import datetime

    # Prefer governed exports as source of truth (prevents stale slate sends)
    try:
        from pathlib import Path
        from tennis.telegram.send import send_tennis_signals

        signals_path = Path("outputs") / "tennis_signals_latest.json"
        if signals_path.exists():
            signals = json.loads(signals_path.read_text(encoding="utf-8"))
            if isinstance(signals, list) and signals:
                # Staleness check: warn if signals are from a previous day
                file_date = datetime.fromtimestamp(signals_path.stat().st_mtime).date()
                today = datetime.now().date()
                if file_date < today:
                    print(f"\n  ⚠️  WARNING: Signals are from {file_date.strftime('%b %d')} (not today).")
                    print(f"     Today's analysis may have been blocked by Direction Gate.")
                    confirm = input("     Send stale signals anyway? [y/N]: ").strip().lower()
                    if confirm != 'y':
                        print("  ✗ Cancelled (signals are stale).")
                        return
                else:
                    confirm = input("\n  Send latest governed signals to Telegram? [Y/n]: ").strip().lower()
                    if confirm == 'n':
                        return
                print(f"\n  Using exported signals: {signals_path}")
                ok = send_tennis_signals(signals)
                if ok:
                    print("  ✓ Signals sent to Telegram!")
                else:
                    print("  ✗ Failed to send signals")
                return
    except Exception:
        # Fall back to legacy behavior below
        pass
    
    outputs_dir = TENNIS_DIR / "outputs"
    reports = sorted(outputs_dir.glob("TENNIS_CALIBRATED_*.txt"), reverse=True) if outputs_dir.exists() else []
    
    if not reports:
        print("\n  No analysis found. Run [1] first to analyze props.")
        return
    
    # Load latest analysis results (need to re-run or load from cache)
    print("\n  Loading latest analysis...")
    
    # Try to find cached results or re-analyze
    slate_path = TENNIS_DIR / "saved_slates"
    slates = sorted(slate_path.glob("slate_*.txt"), reverse=True) if slate_path.exists() else []
    
    if not slates:
        print("  No saved slate found. Run analysis first.")
        return
    
    try:
        from tennis.calibrated_props_engine import CalibratedTennisPropsEngine
        from tennis.telegram.send import send_tennis_analysis
        
        # Find the first valid slate (not empty/corrupted)
        engine = CalibratedTennisPropsEngine()
        paste = None
        props = None
        used_slate = None
        
        for slate_file in slates:
            try:
                content = slate_file.read_text(encoding='utf-8')
                # Skip empty or corrupted slates (less than 50 chars or no alphanumeric)
                if len(content.strip()) < 50 or not any(c.isalpha() for c in content[:100]):
                    print(f"  Skipping invalid slate: {slate_file.name}")
                    continue
                
                test_props = engine.parse_underdog_paste(content)
                if test_props and len(test_props) > 0:
                    paste = content
                    props = test_props
                    used_slate = slate_file
                    break
            except Exception:
                continue
        
        if not props:
            print("  No valid props found in any saved slate.")
            engine.close()
            return
        
        print(f"  Using slate: {used_slate.name}")
        
        results = engine.analyze_slate(props, surface="Hard")
        
        # Show summary
        tiers = results.get('tiers', {})
        slam_count = len(tiers.get('SLAM', []))
        strong_count = len(tiers.get('STRONG', []))
        lean_count = len(tiers.get('LEAN', []))
        
        print(f"\n  📊 Report Summary:")
        print(f"     SLAM: {slam_count} | STRONG: {strong_count} | LEAN: {lean_count}")
        
        confirm = input("\n  Send this report to Telegram? [Y/n]: ").strip().lower()
        if confirm != 'n':
            success = send_tennis_analysis(results)
            if success:
                print("  ✓ Report sent to Telegram!")
            else:
                print("  ✗ Failed to send to Telegram")
        
        engine.close()
        
    except Exception as e:
        print(f"  Error: {e}")


def _send_parlays_to_telegram():
    """Send parlay picks to Telegram - professional format."""
    from datetime import datetime

    # Prefer governed exports as source of truth (prevents stale slate sends)
    try:
        from pathlib import Path
        from tennis.telegram.send import send_parlays

        signals_path = Path("outputs") / "tennis_signals_latest.json"
        if signals_path.exists():
            signals = json.loads(signals_path.read_text(encoding="utf-8"))
            if isinstance(signals, list) and signals:
                slam_picks = [p for p in signals if str(p.get('tier') or '').upper() == 'SLAM']
                strong_picks = [p for p in signals if str(p.get('tier') or '').upper() == 'STRONG']

                if not slam_picks and not strong_picks:
                    print("\n  No SLAM/STRONG picks in exported signals.")
                    return

                # Staleness check
                file_date = datetime.fromtimestamp(signals_path.stat().st_mtime).date()
                today = datetime.now().date()
                if file_date < today:
                    print(f"\n  \u26a0\ufe0f  WARNING: Signals are from {file_date.strftime('%b %d')} (not today).")
                    print(f"     Today's analysis may have been blocked by Direction Gate.")
                    confirm = input("     Use stale signals for parlay? [y/N]: ").strip().lower()
                    if confirm != 'y':
                        print("  \u2717 Cancelled (signals are stale).")
                        return

                print(f"\n  Using exported signals: {signals_path}")
                print(f"\n  🎯 PARLAY OPTIONS:")
                print(f"     SLAM picks available: {len(slam_picks)}")
                print(f"     STRONG picks available: {len(strong_picks)}")
                print()
                print("  Select parlay size:")
                print("    [2] 2-leg parlay (SLAM only)")
                print("    [3] 3-leg parlay (SLAM + STRONG)")
                print("    [4] 4-leg parlay (SLAM + STRONG)")
                print("    [5] 5-leg parlay (Full mix)")
                print("    [A] All top picks (individual bets)")

                parlay_choice = input("\n  Choice: ").strip().upper()

                if parlay_choice == '2':
                    picks = slam_picks[:2]
                    parlay_name = "2-Leg SLAM Parlay"
                elif parlay_choice == '3':
                    picks = slam_picks[:2] + strong_picks[:1]
                    parlay_name = "3-Leg Power Parlay"
                elif parlay_choice == '4':
                    picks = slam_picks[:3] + strong_picks[:1]
                    parlay_name = "4-Leg Premium Parlay"
                elif parlay_choice == '5':
                    picks = slam_picks[:3] + strong_picks[:2]
                    parlay_name = "5-Leg Max Parlay"
                elif parlay_choice == 'A':
                    picks = slam_picks + strong_picks
                    parlay_name = "All Top Picks"
                else:
                    print("  Invalid choice.")
                    return

                if not picks:
                    print("  Not enough picks for selected parlay.")
                    return

                print(f"\n  📋 {parlay_name}:")
                for p in picks:
                    d = str(p.get('direction') or '').strip().lower()
                    dir_emoji = "⬆️" if d in {'higher', 'over', 'more', 'higher '} else "⬇️"
                    prob = p.get('probability', 0) or 0
                    prob_pct = prob * 100 if prob < 1.5 else prob
                    print(f"     {dir_emoji} {p.get('player')}: {p.get('stat')} {p.get('direction')} {p.get('line')} ({prob_pct:.0f}%)")

                confirm = input("\n  Send parlay to Telegram? [Y/n]: ").strip().lower()
                if confirm != 'n':
                    ok = send_parlays(picks, parlay_name)
                    if ok:
                        print("  ✓ Parlay sent to Telegram!")
                    else:
                        print("  ✗ Failed to send parlay")
                return
    except Exception:
        # Fall back to legacy behavior below
        pass
    
    outputs_dir = TENNIS_DIR / "outputs"
    slate_path = TENNIS_DIR / "saved_slates"
    slates = sorted(slate_path.glob("slate_*.txt"), reverse=True) if slate_path.exists() else []
    
    if not slates:
        print("\n  No saved slate found. Run analysis first.")
        return
    
    try:
        from tennis.calibrated_props_engine import CalibratedTennisPropsEngine
        from tennis.telegram.send import send_parlays
        
        # Find the first valid slate (not empty/corrupted)
        engine = CalibratedTennisPropsEngine()
        paste = None
        props = None
        used_slate = None
        
        for slate_file in slates:
            try:
                content = slate_file.read_text(encoding='utf-8')
                # Skip empty or corrupted slates
                if len(content.strip()) < 50 or not any(c.isalpha() for c in content[:100]):
                    continue
                
                test_props = engine.parse_underdog_paste(content)
                if test_props and len(test_props) > 0:
                    paste = content
                    props = test_props
                    used_slate = slate_file
                    break
            except Exception:
                continue
        
        if not props:
            print("  No valid props found in any saved slate.")
            engine.close()
            return
        
        print(f"  Using slate: {used_slate.name}")
        
        results = engine.analyze_slate(props, surface="Hard")
        tiers = results.get('tiers', {})
        
        # Get SLAM + STRONG picks for parlays
        slam_picks = tiers.get('SLAM', [])
        strong_picks = tiers.get('STRONG', [])
        
        if not slam_picks and not strong_picks:
            print("  No high-confidence picks for parlays.")
            engine.close()
            return
        
        print(f"\n  🎯 PARLAY OPTIONS:")
        print(f"     SLAM picks available: {len(slam_picks)}")
        print(f"     STRONG picks available: {len(strong_picks)}")
        print()
        print("  Select parlay size:")
        print("    [2] 2-leg parlay (SLAM only)")
        print("    [3] 3-leg parlay (SLAM + STRONG)")
        print("    [4] 4-leg parlay (SLAM + STRONG)")
        print("    [5] 5-leg parlay (Full mix)")
        print("    [A] All top picks (individual bets)")
        
        parlay_choice = input("\n  Choice: ").strip().upper()
        
        if parlay_choice == '2':
            picks = slam_picks[:2]
            parlay_name = "2-Leg SLAM Parlay"
        elif parlay_choice == '3':
            picks = slam_picks[:2] + strong_picks[:1]
            parlay_name = "3-Leg Power Parlay"
        elif parlay_choice == '4':
            picks = slam_picks[:3] + strong_picks[:1]
            parlay_name = "4-Leg Premium Parlay"
        elif parlay_choice == '5':
            picks = slam_picks[:3] + strong_picks[:2]
            parlay_name = "5-Leg Max Parlay"
        elif parlay_choice == 'A':
            picks = slam_picks + strong_picks
            parlay_name = "All Top Picks"
        else:
            print("  Invalid choice.")
            engine.close()
            return
        
        if not picks:
            print("  Not enough picks for selected parlay.")
            engine.close()
            return
        
        # Show selected picks
        print(f"\n  📋 {parlay_name}:")
        for p in picks:
            dir_emoji = "⬆️" if p.get('direction', '').upper() == 'HIGHER' else "⬇️"
            prob = p.get('probability', 0)
            prob_pct = prob * 100 if prob < 1.5 else prob
            print(f"     {dir_emoji} {p.get('player')}: {p.get('stat')} {p.get('direction')} {p.get('line')} ({prob_pct:.0f}%)")
        
        confirm = input("\n  Send parlay to Telegram? [Y/n]: ").strip().lower()
        if confirm != 'n':
            success = send_parlays(picks, parlay_name)
            if success:
                print("  ✓ Parlay sent to Telegram!")
            else:
                print("  ✗ Failed to send parlay")
        
        engine.close()
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        run_full_pipeline()
    else:
        show_menu()
