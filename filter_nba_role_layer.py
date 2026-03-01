"""
NBA ROLE LAYER FILTER - Auto-filter best picks by archetype
============================================================
Filters JSON output to show only optimal picks based on:
- Archetype (SECONDARY_CREATOR, PRIMARY_USAGE_SCORER)
- Primary stats only (PTS/REB/STL/BLK)
- No high-risk flags (HIGH_BENCH_RISK, BLOWOUT_GAME_RISK)
- Minimum confidence threshold (default 55%)
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Dict
from rich import box
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

def _get_console_width() -> int | None:
    """Best-effort console width.

    Notes:
    - When stdout is not a TTY (e.g., piped input), Rich often falls back to a
      narrow width which makes tables unreadable. In that case we default to a
      wider width (override via RICH_WIDTH env var).
    """
    try:
        is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        is_tty = False

    if not is_tty:
        try:
            return int(os.environ.get("RICH_WIDTH", "160"))
        except Exception:
            return 160

    try:
        return shutil.get_terminal_size(fallback=(160, 24)).columns
    except Exception:
        return None


console = Console(width=_get_console_width())


def _is_interactive() -> bool:
    try:
        return bool(getattr(sys.stdin, "isatty", lambda: False)())
    except Exception:
        return False


def load_picks(file_path: str) -> List[Dict]:
    """Load picks from RISK_FIRST JSON output."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    picks = data.get("results", [])
    
    # Deduplicate by (player, stat, line, direction)
    seen = set()
    unique_picks = []
    for pick in picks:
        key = (
            pick.get("player", "").lower().strip(),
            pick.get("stat", "").lower().strip(),
            str(pick.get("line", "")),
            pick.get("direction", "").lower().strip()
        )
        if key not in seen:
            seen.add(key)
            unique_picks.append(pick)
    
    if len(picks) != len(unique_picks):
        print(f"  [Deduplicated: {len(picks)} → {len(unique_picks)} picks]")
    
    return unique_picks


def filter_optimal_picks(
    picks: List[Dict],
    min_confidence: float = 55.0,
    respect_decision: bool = True,
) -> List[Dict]:
    """
    Filter for optimal NBA Role Layer picks.

    Args:
        picks:            List of enriched pick dicts.
        min_confidence:   Minimum effective_confidence % to include.
        respect_decision: When True (default), skip picks the analysis engine
                          marked NO_PLAY/SKIP/BLOCKED.  Set False for
                          exploratory views (option 5) where the user wants
                          to see all probability-passing picks regardless of
                          the system decision.
    """
    optimal = []
    
    # Primary stat patterns (including Underdog combo stats)
    PRIMARY_STAT_PATTERNS = [
        "point", "pts", "rebound", "reb", "steal", "stl", "block", "blk",
        "pts+", "+pts", "reb+", "+reb",  # Combo stats like pts+ast, reb+ast
        "pa", "ra", "pr", "pra"  # Shorthand combos
    ]
    
    for pick in picks:
        # Must have NBA Role Layer data
        if not pick.get("nba_role_archetype"):
            continue

        # Gate on analysis-engine decision (skip in exploratory mode)
        pick_state = str(pick.get("pick_state", "")).upper().strip()
        if pick_state == "REJECTED":
            continue
        decision = str(pick.get("decision", "")).upper().strip()
        if respect_decision and decision in {"SKIP", "NO_PLAY", "BLOCKED", "REJECTED"}:
            continue
        
        archetype = pick["nba_role_archetype"]
        stat = pick.get("stat", "").lower()
        confidence = pick.get("effective_confidence", 0.0)
        flags = pick.get("nba_role_flags", [])
        
        # Skip BENCH_MICROWAVE (too volatile)
        if archetype == "BENCH_MICROWAVE":
            continue
        
        # Check for primary stats (including combos)
        is_primary = any(s in stat for s in PRIMARY_STAT_PATTERNS)
        # Also check if it's pts+ast or reb+ast (common Underdog combos)
        if stat in ["pts+ast", "reb+ast", "pts+reb", "pts+reb+ast"]:
            is_primary = True
        
        if not is_primary:
            continue
        
        # Skip high-risk flags
        if "HIGH_BENCH_RISK" in flags or "BLOWOUT_GAME_RISK" in flags:
            continue
        
        # Confidence threshold
        if confidence < min_confidence:
            continue
        
        optimal.append(pick)
    
    # Sort by confidence descending
    optimal.sort(key=lambda p: p.get("effective_confidence", 0), reverse=True)
    
    return optimal


def filter_by_archetype(picks: List[Dict], archetype: str) -> List[Dict]:
    """Filter picks by specific archetype."""
    return [p for p in picks if p.get("nba_role_archetype") == archetype]


def show_risky_picks(picks: List[Dict]) -> List[Dict]:
    """Show picks to AVOID (BENCH_MICROWAVE, high-risk flags)."""
    risky = []
    
    for pick in picks:
        archetype = pick.get("nba_role_archetype")
        flags = pick.get("nba_role_flags", [])
        
        if archetype == "BENCH_MICROWAVE":
            risky.append(pick)
        elif "HIGH_BENCH_RISK" in flags or "HIGH_USAGE_VOLATILITY" in flags:
            risky.append(pick)
    
    return risky


def show_specialist_picks(picks: List[Dict], min_conf: float = 50.0) -> List[Dict]:
    """Show picks where player is a specialist in that stat.
    
    Excludes:
    - BENCH_MICROWAVE archetype (too volatile)
    - HIGH_USAGE_VOLATILITY flags
    - Picks below min_conf threshold
    """
    specialist_picks = []
    
    for pick in picks:
        # Skip risky archetypes/flags per governance
        archetype = pick.get("nba_role_archetype", "")
        flags = pick.get("nba_role_flags", [])
        if archetype == "BENCH_MICROWAVE":
            continue
        if "HIGH_USAGE_VOLATILITY" in flags:
            continue
        
        # Skip low confidence picks
        conf = pick.get("effective_confidence", 0)
        if conf < min_conf:
            continue
        
        stat = pick.get("stat", "").lower()
        # Check both field names (nba_specialist_flags and specialist_flags)
        specialist_flags = pick.get("nba_specialist_flags") or pick.get("specialist_flags", [])
        
        # Match stat to specialist flag (including combo stats)
        # Rebound specialists: reb, rebounds, reb+ast, pts+reb
        if ("rebound" in stat or "reb" in stat) and "REB_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
        # 3PM specialists
        elif ("3p" in stat or "three" in stat) and "3PM_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
        # Steals - check both singular and plural
        elif ("steal" in stat or "stl" in stat) and "STL_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
        # Blocks - check both singular and plural  
        elif ("block" in stat or "blk" in stat) and "BLK_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
        elif ("fg" in stat or "field goal" in stat) and "FGM_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
        # Assist specialists: ast, assists, pts+ast, reb+ast
        elif ("assist" in stat or "ast" in stat or "+ast" in stat) and "AST_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
        # Points specialists: pts, points, pts+ast, pts+reb
        elif ("point" in stat or "pts" in stat) and "PTS_SPECIALIST" in specialist_flags:
            specialist_picks.append(pick)
    
    # Sort by confidence
    specialist_picks.sort(key=lambda p: p.get("effective_confidence", 0), reverse=True)
    
    return specialist_picks


def display_picks_table(
    picks: List[Dict],
    title: str = "Filtered Picks",
    all_picks: List[Dict] = None,
    min_conf: float = 55.0,
    mode: str = "auto",
):
    """Display picks in a formatted table."""
    if not picks:
        console.print(f"\n[yellow]No picks match criteria for: {title}[/yellow]\n")
        
        # Provide helpful context if we have all picks data
        if all_picks:
            # Count how many have role data
            with_role = [p for p in all_picks if p.get("nba_role_archetype")]
            # Count how many meet confidence threshold
            above_conf = [p for p in all_picks if p.get("effective_confidence", 0) >= min_conf]
            # Primary stats above conf
            PRIMARY_STAT_PATTERNS = ["point", "pts", "rebound", "reb", "steal", "stl", "block", "blk"]
            primary_above = [p for p in above_conf 
                           if any(s in p.get("stat", "").lower() for s in PRIMARY_STAT_PATTERNS)]
            
            console.print(f"[dim]  Analysis context:[/dim]")
            console.print(f"[dim]    Total picks: {len(all_picks)}[/dim]")
            console.print(f"[dim]    With NBA Role data: {len(with_role)}[/dim]")
            console.print(f"[dim]    Confidence >= {min_conf}%: {len(above_conf)}[/dim]")
            console.print(f"[dim]    Primary stats w/ conf >= {min_conf}%: {len(primary_above)}[/dim]")
            
            if not above_conf:
                console.print(f"\n[yellow]  ⚠️  TIP: No picks have confidence >= {min_conf}%.[/yellow]")
                console.print(f"[yellow]       Try [5] Custom confidence threshold to lower the bar.[/yellow]")
        
        return
    
    # Pick a rendering mode based on console width.
    width = getattr(console, "width", None) or 160
    resolved_mode = mode.lower().strip()
    if resolved_mode == "auto":
        # "Wide" needs room for context columns; compact is much more readable
        # in narrower terminals.
        resolved_mode = "wide" if width >= 140 else "compact"

    # Use a compact border to save horizontal space.
    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
    )

    if resolved_mode == "wide":
        table.add_column("Player", style="white", ratio=2, no_wrap=True, overflow="ellipsis")
        table.add_column("Tm", style="white", width=3, no_wrap=True)
        table.add_column("Opp", style="white", width=3, no_wrap=True)
        table.add_column("Stat", style="cyan", ratio=1, no_wrap=True, overflow="ellipsis")
        table.add_column("Line", style="yellow", width=6, no_wrap=True)
        table.add_column("Dir", style="green", width=6, no_wrap=True)
        table.add_column("Conf", style="magenta", width=6, justify="right")
        table.add_column("μ", style="cyan", width=6, justify="right")
        table.add_column("σ", style="cyan", width=6, justify="right")
        table.add_column("n", style="cyan", width=4, justify="right")
        table.add_column("Arch", style="blue", ratio=2, overflow="ellipsis")
        table.add_column("Cap", style="red", width=5, justify="right")
        table.add_column("Flags", style="yellow", ratio=2, overflow="ellipsis")
    else:
        # Compact = the "what should I look at" view. Fewer columns; no wrapping.
        table.add_column("Player", style="white", ratio=2, no_wrap=True, overflow="ellipsis")
        table.add_column("Stat", style="cyan", ratio=1, no_wrap=True, overflow="ellipsis")
        table.add_column("Line", style="yellow", width=6, no_wrap=True)
        table.add_column("Dir", style="green", width=6, no_wrap=True)
        table.add_column("Conf", style="magenta", width=6, justify="right")
        table.add_column("Tm", style="white", width=3, no_wrap=True)
        table.add_column("Opp", style="white", width=3, no_wrap=True)
        table.add_column("Arch", style="blue", ratio=2, overflow="ellipsis")
        table.add_column("Flags", style="yellow", ratio=2, overflow="ellipsis")
    
    for pick in picks[:15]:  # Top 15
        player = str(pick.get("player", ""))
        team = str(pick.get("team", "")).upper().strip()[:3]
        opp = str(pick.get("opponent", "")).upper().strip()[:3]
        stat = str(pick.get("stat", ""))
        line = str(pick.get("line", ""))
        direction = str(pick.get("direction", ""))
        confidence = f"{pick.get('effective_confidence', 0):.1f}"

        mu_val = pick.get("mu", None)
        sigma_val = pick.get("sigma", None)
        n_val = pick.get("sample_n", None)

        def _fmt_num(x, places: int = 2):
            try:
                return f"{float(x):.{places}f}"
            except Exception:
                return "-"

        archetype = str(pick.get("nba_role_archetype", ""))
        cap_adj = str(pick.get("nba_confidence_cap_adjustment", 0))
        role_flags = list(pick.get("nba_role_flags", []) or [])
        # Bubble the system decision into the flags column so it's visible
        decision_val = str(pick.get("decision", "")).upper().strip()
        if decision_val and decision_val not in {"LEAN", "STRONG", "PLAY", ""}:
            role_flags = [f"[{decision_val}]"] + role_flags
        flags = ", ".join(role_flags)

        if resolved_mode == "wide":
            table.add_row(
                player,
                team,
                opp,
                stat,
                line,
                direction,
                confidence,
                _fmt_num(mu_val),
                _fmt_num(sigma_val),
                "-" if n_val is None else str(n_val),
                archetype,
                cap_adj,
                flags,
            )
        else:
            table.add_row(
                player,
                stat,
                line,
                direction,
                confidence,
                team,
                opp,
                archetype,
                flags,
            )
    
    console.print(table)
    console.print(f"\n[dim]Showing top 15 of {len(picks)} total picks[/dim]\n")


def show_archetype_distribution(picks: List[Dict]):
    """Show distribution of picks by archetype."""
    from collections import Counter
    
    archetypes = [p.get("nba_role_archetype") for p in picks if p.get("nba_role_archetype")]
    counts = Counter(archetypes)
    
    table = Table(title="Archetype Distribution", show_header=True, header_style="bold cyan")
    table.add_column("Archetype", style="white", width=25)
    table.add_column("Count", style="cyan", width=10)
    table.add_column("Percentage", style="yellow", width=12)
    
    total = len(archetypes)
    for archetype, count in counts.most_common():
        pct = f"{count/total*100:.1f}%" if total > 0 else "0%"
        table.add_row(archetype, str(count), pct)
    
    console.print(table)


def main():
    """Interactive NBA Role Layer filter menu."""
    if len(sys.argv) < 2:
        console.print("[red]Usage: python filter_nba_role_layer.py <RISK_FIRST_JSON_FILE>[/red]")
        
        # Auto-detect latest file
        outputs = Path("outputs")
        if outputs.exists():
            risk_files = sorted(outputs.glob("*RISK_FIRST*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if risk_files:
                console.print(f"\n[yellow]Latest file found: {risk_files[0]}[/yellow]")
                use_it = input("Use this file? (Y/n): ").strip().lower()
                if use_it != 'n':
                    file_path = str(risk_files[0])
                else:
                    sys.exit(1)
            else:
                console.print("[red]No RISK_FIRST files found in outputs/[/red]")
                sys.exit(1)
        else:
            sys.exit(1)
    else:
        file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        sys.exit(1)
    
    # Load picks
    console.print(f"\n[cyan]Loading picks from: {file_path}[/cyan]\n")
    picks = load_picks(file_path)
    
    # Filter to only NBA picks with Role Layer data
    nba_picks = [p for p in picks if p.get("nba_role_archetype")]
    
    if not nba_picks:
        console.print("\n" + "="*70)
        console.print("[bold red]❌ NO NBA ROLE LAYER DATA FOUND[/bold red]")
        console.print("="*70)
        console.print("\n[yellow]This file was generated BEFORE NBA API enrichment was added.[/yellow]")
        console.print("[cyan]\nTo use NBA Role Layer filter:[/cyan]")
        console.print("  1. Run Menu → [2] to analyze a slate")
        console.print("  2. Select a file with timestamp AFTER January 26, 2026")
        console.print("  3. Or re-run analysis on this slate to regenerate with NBA data")
        console.print("\n[dim]File checked: {0}[/dim]\n".format(file_path))
        input("Press Enter to continue...")
        sys.exit(1)
    
    console.print(f"[green]Found {len(nba_picks)} NBA picks with Role Layer data[/green]\n")
    
    while True:
        console.print(Panel.fit(
            "[bold cyan]NBA ROLE LAYER FILTER MENU[/bold cyan]\n\n"
            "[1] Show OPTIMAL picks (SECONDARY_CREATOR + primary stats)\n"
            "[2] Show RISKY picks to AVOID (HIGH_USAGE_VOLATILITY flags)\n"
            "[3] Filter by archetype\n"
            "[4] Show archetype distribution\n"
            "[5] Custom confidence threshold\n"
            "[6] Export filtered picks to JSON\n"
            "[7] Show SPECIALIST picks (REB/3PM/STL/BLK specialists)\n"
            "[8] [magenta]Generate FUOOM Subscriber Report[/magenta]\n"
            "[0] Exit",
            title="Filter Options"
        ))
        
        try:
            choice = input("\nSelect option: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]Exiting filter...[/cyan]\n")
            break
        if choice == "\x18":
            choice = "0"
        
        if choice == "1":
            optimal = filter_optimal_picks(nba_picks, min_confidence=55.0)
            display_picks_table(optimal, title="⭐ OPTIMAL PICKS (Primary Stats, Conf >= 55%)",
                               all_picks=nba_picks, min_conf=55.0)
            
        elif choice == "2":
            risky = show_risky_picks(nba_picks)
            display_picks_table(risky, title="⚠️  RISKY PICKS TO AVOID",
                               all_picks=nba_picks)
            
        elif choice == "3":
            console.print("\n[cyan]Available archetypes in current data:[/cyan]")
            console.print("  1. SECONDARY_CREATOR (most common - stable role players)")
            console.print("  2. PRIMARY_USAGE_SCORER (stars - high usage, volatile)")
            console.print("\n[dim]Note: Use option [4] to see exact distribution[/dim]")
            
            arch_input = input("\nEnter archetype name: ").strip().upper()
            filtered = filter_by_archetype(nba_picks, arch_input)
            display_picks_table(filtered, title=f"Picks: {arch_input}")
            
        elif choice == "4":
            show_archetype_distribution(nba_picks)
            
        elif choice == "5":
            try:
                threshold = float(input("\nEnter minimum confidence % (e.g., 70): ").strip())
            except (EOFError, KeyboardInterrupt):
                continue
            except ValueError:
                console.print("[red]Invalid confidence threshold[/red]")
                continue
            # Exploratory mode: ignore NO_PLAY gate so user can see all
            # probability-passing picks (decision shown in Flags column)
            all_above = filter_optimal_picks(
                nba_picks, min_confidence=threshold, respect_decision=False
            )
            play_above = [p for p in all_above
                          if str(p.get("decision", "")).upper().strip()
                          not in {"NO_PLAY", "SKIP", "BLOCKED", "REJECTED"}]
            console.print(
                f"[dim]  {len(play_above)} picks are system-approved plays; "
                f"{len(all_above) - len(play_above)} are [NO_PLAY] (shown with flag)[/dim]"
            )
            display_picks_table(
                all_above,
                title=f"All picks conf >= {threshold}%  (NO_PLAY shown with flag)",
                all_picks=nba_picks,
                min_conf=threshold,
            )
            
        elif choice == "6":
            optimal = filter_optimal_picks(nba_picks, min_confidence=68.0)
            output_file = file_path.replace(".json", "_FILTERED_OPTIMAL.json")
            
            with open(output_file, 'w') as f:
                json.dump({"results": optimal, "total": len(optimal)}, f, indent=2)
            
            console.print(f"\n[green]Exported {len(optimal)} optimal picks to: {output_file}[/green]\n")
            
        elif choice == "7":
            specialist = show_specialist_picks(nba_picks)
            if specialist:
                display_picks_table(specialist, title="⭐ SPECIALIST PICKS (Stat Specialists)")
                console.print("\n[cyan]Specialist Breakdown:[/cyan]")
                from collections import Counter
                flags_counter = Counter()
                for p in specialist:
                    for flag in p.get("nba_specialist_flags", []):
                        flags_counter[flag] += 1
                for flag, count in flags_counter.most_common():
                    console.print(f"  {flag}: {count} picks")
            else:
                console.print("\n[yellow]No specialist picks found[/yellow]")
                console.print("\n[dim]Note: Specialist flags depend on the analysis run.\nIf your latest file has no specialist flags, re-run analysis (newer runs may include them).[/dim]\n")
                
                # Show alternative: players with relevant stats that have high confidence
                console.print("[cyan]Alternative: High-confidence picks by stat type:[/cyan]")
                stats_of_interest = {"rebound": [], "3p": [], "steal": [], "block": [], "assist": []}
                for p in nba_picks:
                    stat = p.get("stat", "").lower()
                    conf = p.get("effective_confidence", 0)
                    if conf >= 55:
                        for key in stats_of_interest:
                            if key in stat:
                                stats_of_interest[key].append(p)
                                break
                
                for stat_type, stat_picks in stats_of_interest.items():
                    if stat_picks:
                        console.print(f"  {stat_type.upper()}: {len(stat_picks)} picks >= 55% conf")
        
        elif choice == "8":
            # Generate FUOOM Subscriber Report
            try:
                from report_enhancer import enhance_report, save_enhanced_report
                
                # Filter to qualified picks (confidence >= 55%)
                qualified = [p for p in nba_picks if p.get("effective_confidence", 0) >= 55]
                
                if not qualified:
                    console.print("[yellow]No qualified picks (need >= 55% confidence)[/yellow]")
                else:
                    # Convert to FUOOM format
                    picks_for_report = []
                    for prop in qualified:
                        picks_for_report.append({
                            'player': prop.get('player', ''),
                            'stat': prop.get('stat', ''),
                            'line': prop.get('line', 0),
                            'direction': prop.get('direction', 'higher'),
                            'probability': prop.get('effective_confidence', 50) / 100,
                            'mu': prop.get('mu', 0),
                            'sigma': prop.get('sigma', 0),
                            'opponent': prop.get('opponent', 'OPP'),
                            'recent_hits': prop.get('hit_count'),
                            'recent_total': 10,
                        })
                    
                    use_llm = input("\nUse DeepSeek LLM for polish? (y/N): ").strip().lower() == 'y'
                    filepath = save_enhanced_report(picks_for_report, "NBA", use_llm=use_llm)
                    console.print(f"\n[green]✓ FUOOM report saved: {filepath}[/green]")
                    console.print(f"[cyan]  {len(picks_for_report)} picks included[/cyan]")
                    
                    # Option to view it
                    view_it = input("\nView report? (Y/n): ").strip().lower()
                    if view_it != 'n':
                        with open(filepath, 'r', encoding='utf-8') as f:
                            console.print(Panel(f.read(), title="FUOOM DARK MATTER", border_style="magenta"))
                            
            except ImportError as e:
                console.print(f"[red]Error: report_enhancer.py not found: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Error generating report: {e}[/red]")
            
        elif choice == "0":
            console.print("\n[cyan]Exiting filter...[/cyan]\n")
            break
        else:
            console.print("[red]Invalid option[/red]")
        
        # In non-interactive / piped runs, a pause prompt tends to consume the
        # next queued command and produces confusing "Invalid option" output.
        if _is_interactive():
            try:
                input("\nPress Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                break


if __name__ == "__main__":
    main()
