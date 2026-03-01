"""
Soccer Interactive Menu
=======================
Interactive menu for soccer prop analysis.
"""

import sys
import os
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import only what we need - avoid broken run_daily imports
from soccer.data.player_database import PlayerDatabase
from soccer.soccer_slate_analyzer import (
    analyze_slate_file,
    analyze_scraped_props,
    analyze_scraped_props_structured,
    parse_underdog_slate,
    parse_slate_auto,
    analyze_prop,
    format_report,
)

# Define paths locally to avoid import issues
ROOT = Path(__file__).parent
PROJECT_ROOT = ROOT.parent
INPUTS_DIR = ROOT / "inputs"
OUTPUTS_DIR = ROOT / "outputs"
CALIBRATION_DIR = ROOT / "calibration_results"

SCRAPED_PROPS_LATEST = PROJECT_ROOT / "outputs" / "props_latest.json"

# Create dirs if needed
INPUTS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)
CALIBRATION_DIR.mkdir(exist_ok=True)

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
# Multi-destination: personal + channel (matches NBA behaviour)
TELEGRAM_CHAT_IDS = [
    cid.strip()
    for cid in os.getenv('TELEGRAM_CHAT_IDS', '').split(',')
    if cid.strip()
] or ([TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else [])


def send_telegram_message(message: str) -> bool:
    """Send a message to all configured Telegram destinations."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        print("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS in .env")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    success = False
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                success = True
            else:
                print(f"❌ Telegram error (chat {chat_id}): {response.text}")
        except Exception as e:
            print(f"❌ Telegram error (chat {chat_id}): {e}")
    return success


def send_top_picks_to_telegram(num_picks: int = 7, skip_confirm: bool = False):
    """Send top N soccer picks to Telegram.

    Priority order:
      1) Latest exported soccer signals (Odds API / Playwright / Paste) from:
         - outputs/soccer_signals_latest.json
         - soccer/outputs/signals_latest.json
      2) Fallback: analyze most recent saved slate_*.txt

    Args:
        num_picks: Number of top picks to send.
        skip_confirm: If True, skip the confirmation prompt.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        print("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS in .env")
        return

    def _load_json_list(path: Path) -> list[dict]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [x for x in raw if isinstance(x, dict)]
            if isinstance(raw, dict):
                arr = raw.get("signals") or raw.get("edges") or []
                return [x for x in arr if isinstance(x, dict)]
        except Exception:
            return []
        return []

    # Prefer the most recently-written soccer signals export.
    signal_candidates = [
        PROJECT_ROOT / "outputs" / "soccer_signals_latest.json",
        OUTPUTS_DIR / "signals_latest.json",
    ]
    existing_signals = [p for p in signal_candidates if p.exists()]
    signals_path = max(existing_signals, key=lambda p: p.stat().st_mtime, default=None)

    # Find most recent slate for fallback.
    slates = list(INPUTS_DIR.glob("slate_*.txt"))
    slate_file = max(slates, key=lambda p: p.stat().st_mtime, default=None)

    # IMPORTANT: Default to exported signals whenever present.
    # Rationale: Odds API / Playwright ingest should be the source of truth for "latest slate",
    # and users frequently keep old pasted slates around which would otherwise override.
    use_signals = signals_path is not None

    today = datetime.now().strftime("%B %d, %Y")
    lines: list[str] = [f"⚽ <b>SOCCER PICKS — {today}</b>"]

    if use_signals and signals_path is not None:
        signals = _load_json_list(signals_path)

        def _prob(s: dict) -> float:
            try:
                return float(s.get("probability") or 0.0)
            except Exception:
                return 0.0

        # Governance: never send REJECTED. VETTED can be shown, but flagged.
        eligible = [
            s
            for s in signals
            if (s.get("pick_state") != "REJECTED")
            and (s.get("tier") in {"SLAM", "STRONG", "LEAN"})
            and (_prob(s) >= 0.60)
        ]
        eligible.sort(key=_prob, reverse=True)

        # Dedupe by edge_id (some feeds repeat the same prop multiple times).
        deduped: list[dict] = []
        seen: set[str] = set()
        for s in eligible:
            edge_id = str(s.get("edge_id") or "").strip()
            if not edge_id:
                edge_id = f"{s.get('player') or s.get('entity','')}|{s.get('market') or s.get('stat','')}|{s.get('line')}|{s.get('direction')}"
            if edge_id in seen:
                continue
            seen.add(edge_id)
            deduped.append(s)

        top = deduped[:num_picks]

        if not top:
            print(f"⚠️ No actionable soccer signals found in {signals_path} (need 60%+ and not REJECTED).")
            # Fall back to slate if available
            use_signals = False
        else:
            # Attempt to detect source mode for the header.
            src_mode = ""
            try:
                src = top[0].get("source")
                if isinstance(src, dict):
                    src_mode = str(src.get("mode") or "").strip()
                elif isinstance(src, str):
                    src_mode = src.strip()
            except Exception:
                src_mode = ""

            mode_label = {
                "odds_api": "Odds API",
                "playwright": "Playwright",
                "paste": "Paste",
                "smoke": "Smoke",
            }.get(src_mode, "")

            # Always show which artifact we pulled from, so it's obvious what source was used.
            lines.append(
                f"📊 Top {len(top)} Risk-First Selections"
                + (f"  |  Source: {mode_label}" if mode_label else "")
                + f"  |  File: {signals_path.as_posix()}"
            )
            lines.append("")

            tier_emoji = {"SLAM": "🔥", "STRONG": "🔥", "LEAN": "✅", "AVOID": "⚠️"}
            for s in top:
                player = s.get("player") or s.get("entity") or "Unknown"
                stat = s.get("stat") or s.get("market") or ""
                stat = str(stat).replace("_", " ").title()
                line = s.get("line", 0)
                direction = s.get("direction")
                over_under = "OVER" if direction in {"higher", "over", "OVER"} else "UNDER"
                p = _prob(s)
                t = str(s.get("tier") or "").upper()
                ps = str(s.get("pick_state") or "").upper()

                warn = "⚠️ " if ps == "VETTED" else ""
                emoji = tier_emoji.get(t, "✅" if p >= 0.72 else "📊")
                lines.append(f"{warn}{emoji} <b>{player}</b>")
                lines.append(f"   {stat} {over_under} {line} ({p*100:.0f}%)")
                lines.append("")

            lines.append("━━━━━━━━━━━━━━━")
            lines.append("🎯 UNDERDOG ANALYSIS")

            message = "\n".join(lines)
    
    if not use_signals:
        if slate_file is None:
            print("❌ No soccer signals found and no slates found. Run Odds API [8], Auto-Ingest [0], or Paste [1] first.")
            return

        print(f"\n🔄 Analyzing {slate_file.name}...")
        text = slate_file.read_text(encoding="utf-8")
        props = parse_slate_auto(text)
        analyzed = [analyze_prop(p) for p in props]

        def get_best_prob(p):
            return max(p.prob_over, p.prob_under)

        actionable = [p for p in analyzed if get_best_prob(p) >= 0.60]
        actionable.sort(key=get_best_prob, reverse=True)
        top_picks = actionable[:num_picks]
        if not top_picks:
            print("❌ No actionable picks found (need 60%+ probability)")
            return

        lines.append(f"📊 Top {len(top_picks)} Risk-First Selections  |  Source: Saved Slate")
        lines.append("")
        for p in top_picks:
            prob = p.prob_over if p.direction == "OVER" else p.prob_under
            tier = "🔥" if prob >= 0.72 else "✅"
            lines.append(f"{tier} <b>{p.player}</b>")
            lines.append(f"   {p.stat} {p.direction} {p.line} ({prob*100:.0f}%)")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━")
        lines.append("🎯 UNDERDOG ANALYSIS")
        message = "\n".join(lines)
    
    # Preview
    print("\n📱 TELEGRAM MESSAGE PREVIEW:")
    print("-" * 40)
    print(message.replace("<b>", "").replace("</b>", ""))
    print("-" * 40)
    
    # Confirm send (unless already confirmed)
    if not skip_confirm:
        confirm = input("\nSend to Telegram? [Y/n]: ").strip().lower()
        if confirm == 'n':
            print("❌ Cancelled")
            return
    
    # Send
    if send_telegram_message(message):
        print("✅ Sent to Telegram!")
    else:
        print("❌ Failed to send")


def print_header():
    """Print menu header."""
    print("\n" + "=" * 60)
    print("⚽ SOCCER PROP ANALYSIS — RISK-FIRST ENGINE")
    print("=" * 60)


# =============================================================================
# CALIBRATION TRACKING FUNCTIONS
# =============================================================================

def save_picks_to_calibration(analyzed_props: list, slate_date: str = None):
    """
    Save analyzed picks to unified calibration tracker.
    
    Args:
        analyzed_props: List of AnalyzedProp objects from analyze_prop()
        slate_date: Optional date override (defaults to today)
    """
    try:
        from calibration.unified_tracker import UnifiedCalibration, CalibrationPick
        
        tracker = UnifiedCalibration()
        date_str = slate_date or datetime.now().strftime("%Y-%m-%d")
        saved = 0
        
        for prop in analyzed_props:
            # Only track actionable tiers
            if prop.tier not in ['STRONG', 'LEAN', 'SLAM']:
                continue
            
            # Determine best direction and probability
            if prop.prob_over > prop.prob_under:
                direction = "Higher"
                probability = prop.prob_over * 100
            else:
                direction = "Lower" 
                probability = prop.prob_under * 100
            
            # Generate unique pick ID
            pick_id = f"soccer_{date_str}_{prop.player}_{prop.stat}_{prop.line}".replace(" ", "_")
            
            # Check if already exists
            existing = [p for p in tracker.picks if p.pick_id == pick_id]
            if existing:
                continue
            
            pick = CalibrationPick(
                pick_id=pick_id,
                date=date_str,
                sport="soccer",
                player=prop.player,
                stat=prop.stat,
                line=prop.line,
                direction=direction,
                probability=probability,
                tier=prop.tier
            )
            
            tracker.add_pick(pick)
            saved += 1

        # ── Also write to structured DB (fail-soft) ───────────────────────
        _db_picks_list = []
        for _prop in analyzed_props:
            if getattr(_prop, "tier", None) not in ("STRONG", "LEAN", "SLAM"):
                continue
            _pover  = getattr(_prop, "prob_over",  0) or 0
            _punder = getattr(_prop, "prob_under", 0) or 0
            if _pover >= _punder:
                _dir, _prob = "higher", _pover
            else:
                _dir, _prob = "lower",  _punder
            _db_picks_list.append({
                "player":     getattr(_prop, "player",  ""),
                "team":       getattr(_prop, "team",    ""),
                "stat":       getattr(_prop, "stat",    ""),
                "line":       getattr(_prop, "line",    0),
                "direction":  _dir,
                "sport":      "Soccer",
                "source":     "Underdog",
                "confidence": _prob * 100,
                "p_hit":      _prob,
                "tier":       getattr(_prop, "tier", ""),
            })
        if _db_picks_list:
            try:
                from db.writer import write_picks_batch  # type: ignore
                write_picks_batch(_db_picks_list, sport="Soccer")
            except Exception:
                pass

        if saved > 0:
            print(f"\n📊 Saved {saved} picks to calibration tracker")
        return saved
        
    except Exception as e:
        print(f"⚠️ Calibration save failed: {e}")
        return 0


def resolve_results():
    """Interactive result resolution for tracked picks."""
    try:
        from calibration.unified_tracker import UnifiedCalibration
        
        tracker = UnifiedCalibration()
        
        # Filter to unresolved soccer picks
        unresolved = [p for p in tracker.picks if p.sport == "soccer" and p.hit is None]
        
        if not unresolved:
            print("\n✅ No unresolved soccer picks!")
            return
        
        # Group by date
        by_date = {}
        for pick in unresolved:
            if pick.date not in by_date:
                by_date[pick.date] = []
            by_date[pick.date].append(pick)
        
        print(f"\n📋 UNRESOLVED SOCCER PICKS ({len(unresolved)} total)")
        print("=" * 60)
        
        for date_str in sorted(by_date.keys(), reverse=True):
            picks = by_date[date_str]
            print(f"\n📅 {date_str} ({len(picks)} picks)")
            print("-" * 40)
            
            for i, pick in enumerate(picks, 1):
                dir_emoji = "⬆️" if pick.direction == "Higher" else "⬇️"
                print(f"  [{i}] {pick.player}: {pick.stat} {dir_emoji} {pick.line} ({pick.probability:.0f}%)")
            
            resolve_choice = input(f"\nResolve these picks? [y/N]: ").strip().lower()
            
            if resolve_choice == 'y':
                for pick in picks:
                    dir_emoji = "⬆️" if pick.direction == "Higher" else "⬇️"
                    print(f"\n  {pick.player}: {pick.stat} {dir_emoji} {pick.line}")
                    actual = input(f"  Actual result (or 'skip'): ").strip()
                    
                    if actual.lower() == 'skip':
                        continue
                    
                    try:
                        actual_val = float(actual)
                        tracker.update_result(pick.pick_id, actual_val)
                        
                        # Show result
                        if pick.direction == "Higher":
                            hit = actual_val > pick.line
                        else:
                            hit = actual_val < pick.line
                        
                        result_emoji = "✅" if hit else "❌"
                        print(f"  {result_emoji} {'HIT' if hit else 'MISS'} - Actual: {actual_val}")
                        
                    except ValueError:
                        print(f"  ⚠️ Invalid number, skipping")
        
        print("\n✅ Result resolution complete!")
        
    except Exception as e:
        print(f"❌ Error resolving results: {e}")


def show_calibration_report():
    """Display calibration report for soccer."""
    try:
        from calibration.unified_tracker import UnifiedCalibration
        
        tracker = UnifiedCalibration()
        
        # Get soccer-specific picks
        soccer_picks = [p for p in tracker.picks if p.sport == "soccer"]
        resolved = [p for p in soccer_picks if p.hit is not None]
        
        print("\n📊 SOCCER CALIBRATION REPORT")
        print("=" * 60)
        
        if not soccer_picks:
            print("No soccer picks tracked yet.")
            print("Run analysis [1] to start tracking picks.")
            return
        
        print(f"Total tracked: {len(soccer_picks)}")
        print(f"Resolved: {len(resolved)}")
        print(f"Pending: {len(soccer_picks) - len(resolved)}")
        
        if resolved:
            # Calculate stats
            hits = len([p for p in resolved if p.hit])
            hit_rate = hits / len(resolved) * 100
            
            print(f"\n📈 OVERALL STATS")
            print(f"  Hit Rate: {hits}/{len(resolved)} ({hit_rate:.1f}%)")
            
            # Brier score
            brier = tracker.get_sport_brier("soccer")
            print(f"  Brier Score: {brier:.4f} (target: <0.24)")
            
            # Tier breakdown
            tier_stats = tracker.get_tier_stats("soccer")
            
            print(f"\n📊 TIER BREAKDOWN")
            for tier, stats in tier_stats.items():
                target_pct = stats['target'] * 100
                actual_pct = stats['hit_rate'] * 100
                status = "✅" if stats['meets_target'] else "⚠️"
                print(f"  {tier}: {actual_pct:.1f}% (target: {target_pct:.0f}%) {status} — {stats['picks']} picks")
            
            # Recent picks
            print(f"\n📋 RECENT RESULTS (last 10)")
            for pick in resolved[-10:]:
                result = "✅" if pick.hit else "❌"
                print(f"  {result} {pick.date} | {pick.player}: {pick.stat} {pick.direction} {pick.line}")
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")


def show_menu():
    """Display main menu options."""
    print(f"""
  +{'='*64}+
  |{'SOCCER PROP ANALYSIS - RISK-FIRST ENGINE':^64}|
  +{'='*64}+
  |                                                                |
  |  PREGAME WORKFLOW                                              |
  |  ----------------                                              |
  |  [1B] Auto-Ingest         - Playwright scraper (DK/PP/UD)      |
  |  [8]  Odds API Ingest     - No-scrape props (us_dfs)           |
  |  [8A] Odds API ALL        - Pull ALL 6 leagues at once         |
  |  [1]  Paste Props         - Paste Underdog soccer lines        |
  |  [2]  Analyze Slate       - Run risk-first pipeline (latest)   |
  |  [3]  Full Analysis       - Show all incl. NO_PLAY             |
  |                                                                |
  |  INSIGHTS                                                      |
  |  --------                                                      |
  |  [4]  Player Database     - View all tracked players           |
  |  [5]  Search Player       - Look up individual stats           |
  |  [6]  League Selection    - Filter by league                   |
  |  [7]  View Saved Slates   - Browse saved slate files           |
  |                                                                |
  |  POSTGAME                                                      |
  |  --------                                                      |
  |  [R]  Resolve Results     - Enter actuals, update history      |
  |  [C]  Calibration Report  - Hit rates by tier                  |
  |                                                                |
  |  DATA MANAGEMENT                                               |
  |  ---------------                                               |
  |  [U]  Update Stats        - Props + ESPN -> CSV                |
  |  [E]  Export Database     - Backup to CSV                      |
  |  [A]  Refresh API Stats   - Pull latest from API-Football      |
  |                                                                |
  |  REPORTS                                                       |
  |  -------                                                       |
  |  [T]  Telegram            - Send top picks to Telegram         |
  |  [V]  View Report         - Show latest analysis output        |
  |                                                                |
  |  [Q]  BACK                - Return to main menu                |
  +{'='*64}+
""")


def odds_api_ingest_mode(force_all: bool = False):
    """Run the Odds API no-scrape ingest for soccer, then analyze props_latest.json.

    Args:
        force_all: If True, skip league selection and pull ALL leagues.
    """
    print("\n🛰️ ODDS API NO-SCRAPE INGEST — SOCCER")
    print("-" * 40)
    print("This uses The Odds API (regions=us_dfs) to fetch player props (no browser).")
    print("It will also run the validation gate and set the active slate pointer.")

    league_menu = {
        "1": "SOCCER_EPL",
        "2": "SOCCER_MLS",
        "3": "SOCCER_LA_LIGA",
        "4": "SOCCER_BUNDESLIGA",
        "5": "SOCCER_SERIE_A",
        "6": "SOCCER_LIGUE_1",
    }

    ALL_LEAGUES = list(league_menu.values())

    if force_all:
        choice = "A"
    else:
        print("\nChoose league:")
        print("[A] ALL LEAGUES (pull all at once)")
        print("[1] EPL (soccer_epl) [default]")
        print("[2] MLS (soccer_usa_mls)")
        print("[3] La Liga")
        print("[4] Bundesliga")
        print("[5] Serie A")
        print("[6] Ligue 1")
        print("Or type a sport tag like SOCCER_EPL / SOCCER_MLS / SOCCER")

        choice = input("League [1]: ").strip().upper() or "1"

    script_path = (PROJECT_ROOT / "scripts" / "fuoom_no_scrape_ingest.py").resolve()
    if not script_path.exists():
        print(f"❌ Missing script: {script_path}")
        return

    # ── All-leagues mode ──────────────────────────────────────
    if choice == "A":
        all_props = []
        leagues_hit = []

        for tag in ALL_LEAGUES:
            label = tag.replace("SOCCER_", "")
            print(f"\n{'─'*40}")
            print(f"  🛰️  Fetching {label}...")
            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path), "--sport", tag],
                    cwd=str(PROJECT_ROOT),
                    check=False,
                )
                if proc.returncode == 0 and SCRAPED_PROPS_LATEST.exists():
                    data = json.loads(SCRAPED_PROPS_LATEST.read_text(encoding="utf-8"))
                    props = data.get("props") if isinstance(data, dict) else None
                    if isinstance(props, list) and props:
                        # Tag each prop with its league
                        for p in props:
                            p.setdefault("league", label)
                        all_props.extend(props)
                        leagues_hit.append(f"{label}({len(props)})")
                        print(f"     ✅ {label}: {len(props)} props")
                    else:
                        print(f"     ⚠️  {label}: 0 props (no markets posted)")
                elif proc.returncode == 4:
                    print(f"     ⚠️  {label}: 0 props (us_dfs not posted yet)")
                else:
                    print(f"     ❌ {label}: ingest failed (exit {proc.returncode})")
            except Exception as e:
                print(f"     ❌ {label}: {e}")

        print(f"\n{'═'*50}")
        print(f"  📊 TOTAL: {len(all_props)} props from {len(leagues_hit)} leagues")
        if leagues_hit:
            print(f"     {', '.join(leagues_hit)}")
        print(f"{'═'*50}")

        if not all_props:
            print("\n❌ No props found across any league.")
            return

        # Write combined props to props_latest.json for analysis
        combined = {"props": all_props, "source": "odds_api_all_leagues",
                    "timestamp": datetime.now().isoformat(),
                    "leagues": [l.split("(")[0] for l in leagues_hit]}
        try:
            SCRAPED_PROPS_LATEST.write_text(
                json.dumps(combined, indent=2), encoding="utf-8"
            )
        except Exception as e:
            print(f"❌ Could not write combined props: {e}")
            return

        props = all_props
        sport_tag = "SOCCER_ALL"

    else:
        # ── Single-league mode ────────────────────────────────
        sport_tag = league_menu.get(choice, choice)

        try:
            # Run the canonical end-to-end workflow (ingest → validate → set slate).
            proc = subprocess.run(
                [sys.executable, str(script_path), "--sport", sport_tag],
                cwd=str(PROJECT_ROOT),
                check=False,
            )
            if proc.returncode != 0:
                if proc.returncode == 4:
                    print("⚠️ Odds API returned 0 props for this league.")
                    print("   This usually means us_dfs books haven’t posted player prop markets yet.")
                    print("   Try EPL, run closer to kickoff, or clear ODDS_API_BOOKMAKERS.")
                else:
                    print(f"❌ Odds API ingest failed (exit code {proc.returncode}).")
                return
        except Exception as e:
            print(f"❌ Failed to run Odds API ingest: {e}")
            return

        if not SCRAPED_PROPS_LATEST.exists():
            print(f"❌ Missing output: {SCRAPED_PROPS_LATEST}")
            return

        try:
            data = json.loads(SCRAPED_PROPS_LATEST.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"❌ Could not read props_latest.json: {e}")
            return

        props = data.get("props") if isinstance(data, dict) else None
        if not isinstance(props, list) or not props:
            print("❌ No props found in props_latest.json.")
            return

    # DEBUG: Show sample prop structure
    if props:
        sample_keys = list(props[0].keys()) if props else []
        print(f"\n[DEBUG] Sample prop keys: {sample_keys}")

    # Auto-fetch real player stats from API-Football before analysis
    print("\n📥 Fetching real player stats from API-Football...")
    # Extract unique player names from props (try multiple field names)
    unique_players = set()
    for p in props:
        name = p.get("player") or p.get("athlete_display_name") or p.get("athlete", {}).get("name")
        if name and isinstance(name, str) and name.strip():
            unique_players.add(name.strip())
    
    unique_players = list(unique_players)
    
    if unique_players:
        print(f"   Found {len(unique_players)} unique players: {', '.join(unique_players[:5])}...")
        try:
            from soccer.api_football_integration import fetch_soccer_stats_for_slate
            stats = fetch_soccer_stats_for_slate(unique_players[:20])  # Limit to 20 to avoid rate limits
            if stats:
                print(f"   ✅ Fetched {len(stats)} real player profiles from API-Football")
                print(f"      (Reduces ESTIMATES, improves opponent adjustments)")
            else:
                print("   ⚠️ API-Football returned 0 stats (may need different league/season)")
                print("      Analysis will use database + estimates as fallback")
        except Exception as e:
            print(f"   ⚠️ API-Football fetch skipped: {e}")
            print("      Analysis will use database + estimates as fallback")
    else:
        print("   ⚠️ No player names found in props (check props structure)")

    show_all = input("\nShow full report (incl. AVOID)? [y/N]: ").strip().lower() == "y"

    print("\n🔄 Analyzing Odds API props with Risk-First Engine...")
    report, analyzed = analyze_scraped_props_structured(props, show_no_play=show_all)
    print(report)

    # Quant exports (signals + governance artifacts + pick_state)
    try:
        from soccer.soccer_slate_analyzer import export_soccer_quant_artifacts

        # league_tag is the suffix (EPL/MLS/...) when available.
        league_tag = sport_tag.replace("SOCCER_", "") if sport_tag.startswith("SOCCER_") else sport_tag
        export_soccer_quant_artifacts(
            analyzed,
            league_tag=league_tag,
            source={
                "mode": "odds_api",
                "sport_tag": sport_tag,
                "props_latest": str(SCRAPED_PROPS_LATEST),
            },
        )
        print("\n✅ Exported soccer signals + governance artifacts")
        print("   - outputs/soccer_signals_latest.json")
        print("   - soccer/outputs/signals_latest.json")
    except Exception as e:
        print(f"\n⚠️ Quant export failed (non-fatal): {e}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUTS_DIR / f"soccer_oddsapi_report_{timestamp}.txt"
    try:
        report_path.write_text(report, encoding="utf-8")
        print(f"\n📁 Report saved to: {report_path}")
    except Exception:
        pass


def auto_ingest_mode():
    """Auto-ingest soccer props via Playwright (no manual paste)."""
    print("\n🔌 AUTO-INGEST SOCCER PROPS")
    print("-" * 40)
    print("This uses the existing Playwright ingestion pipeline.")
    print("Tip: the persistent profile mode is most reliable for logins.")

    try:
        from ingestion.prop_ingestion_pipeline import interactive_browse_persistent, run_pipeline
    except Exception as e:
        print(f"❌ Could not import ingestion pipeline: {e}")
        print("   Expected: ingestion/prop_ingestion_pipeline.py")
        return

    print("\nChoose ingest mode:")
    print("[1] Persistent browser (recommended) — login once, navigate to Soccer props, press Enter")
    print("[2] Quick scrape all sites — may require logins each run")
    mode = input("Select [1/2] (default 1): ").strip() or "1"

    try:
        if mode.strip() == "2":
            run_pipeline(sites=["draftkings", "prizepicks", "underdog"], headless=False)
        else:
            interactive_browse_persistent()
    except Exception as e:
        print(f"❌ Ingest failed: {e}")
        return

    if not SCRAPED_PROPS_LATEST.exists():
        print(f"❌ Missing scraped output: {SCRAPED_PROPS_LATEST}")
        return

    try:
        data = json.loads(SCRAPED_PROPS_LATEST.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Could not read scraped props JSON: {e}")
        return

    props = data.get("props") if isinstance(data, dict) else None
    if not isinstance(props, list) or not props:
        print("❌ No props found in scraped output.")
        return

    show_all = input("Show full report (incl. AVOID)? [y/N]: ").strip().lower() == "y"

    print("\n🔄 Analyzing scraped props with Risk-First Engine...")
    report, analyzed = analyze_scraped_props_structured(props, show_no_play=show_all)
    print(report)

    # Quant exports (signals + governance artifacts + pick_state)
    try:
        from soccer.soccer_slate_analyzer import export_soccer_quant_artifacts

        export_soccer_quant_artifacts(
            analyzed,
            league_tag="SCRAPED",
            source={
                "mode": "playwright",
                "props_latest": str(SCRAPED_PROPS_LATEST),
            },
        )
        print("\n✅ Exported soccer signals + governance artifacts")
        print("   - outputs/soccer_signals_latest.json")
        print("   - soccer/outputs/signals_latest.json")
    except Exception as e:
        print(f"\n⚠️ Quant export failed (non-fatal): {e}")

    # Save report + a timestamped snapshot of the scraped input
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = INPUTS_DIR / f"scraped_props_{timestamp}.json"
    report_path = OUTPUTS_DIR / f"soccer_scraped_report_{timestamp}.txt"

    try:
        snapshot_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        # Best-effort; don't block analysis.
        pass

    report_path.write_text(report, encoding="utf-8")
    print(f"\n📁 Report saved to: {report_path}")

    # If Telegram is configured, offer to send the top actionable picks.
    try:
        from soccer.soccer_slate_analyzer import parsed_props_from_scraped_props

        parsed = parsed_props_from_scraped_props(props)
        analyzed = [analyze_prop(p) for p in parsed]

        def best_prob(ap):
            return max(ap.prob_over, ap.prob_under)

        actionable = [p for p in analyzed if best_prob(p) >= 0.60]
        actionable.sort(key=best_prob, reverse=True)
        top_picks = actionable[:7]

        if top_picks and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            send_tg = input(f"\n📱 Send top {len(top_picks)} to Telegram? [Y/n]: ").strip().lower()
            if send_tg != "n":
                today = datetime.now().strftime("%B %d, %Y")
                lines = [
                    f"⚽ <b>SOCCER PICKS — {today}</b>",
                    f"📊 Top {len(top_picks)} Risk-First Selections",
                    "",
                ]
                for p in top_picks:
                    prob = p.prob_over if p.direction == "OVER" else p.prob_under
                    tier = "🔥" if prob >= 0.72 else "✅"
                    lines.append(f"{tier} <b>{p.player}</b>")
                    lines.append(f"   {p.stat} {p.direction} {p.line} ({prob*100:.0f}%)")
                    lines.append("")
                lines.append("━━━━━━━━━━━━━━━")
                lines.append("🎯 UNDERDOG ANALYSIS")
                send_telegram_message("\n".join(lines))
    except Exception:
        pass


def paste_props_mode():
    """Interactive mode to paste props from Underdog - uses NEW analyzer."""
    print("\n📋 PASTE UNDERDOG PROPS")
    print("-" * 40)
    print("Paste ALL your props below.")
    print("Type 'END' on a new line when finished.")
    print("-" * 40)
    
    lines = []
    
    while True:
        try:
            line = input()
            # Check for end signal (case insensitive)
            if line.strip().lower() in ['end', 'done', 'go', 'run']:
                break
            lines.append(line)
        except EOFError:
            break
    
    # Filter out empty lines at start/end but keep internal structure
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    
    if not lines:
        print("[WARN] No input received")
        return
    
    # Show what we captured
    non_empty = [l for l in lines if l.strip()]
    print(f"\n✓ Captured {len(lines)} lines ({len(non_empty)} non-empty)")
    
    # Ask for confirmation before processing
    confirm = input("Process these props? [Y/n]: ").strip().lower()
    if confirm == 'n':
        print("Cancelled. Use [1] to try again.")
        return
    
    # Save to dated slate file
    slate_text = "\n".join(lines)
    today = datetime.now().strftime("%Y%m%d")
    slate_file = INPUTS_DIR / f"slate_{today}.txt"
    slate_file.write_text(slate_text, encoding='utf-8')
    print(f"\n✓ Saved to {slate_file}")
    
    # Parse and analyze using auto-detect (Pick6 or Underdog)
    print("\n🔄 Analyzing with Risk-First Engine...")
    props = parse_slate_auto(slate_text)
    print(f"📋 Parsed {len(props)} props")
    
    if props:
        analyzed = [analyze_prop(p) for p in props]
        report = format_report(analyzed, show_no_play=False)
        print(report)
        
        # Save report to outputs folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = OUTPUTS_DIR / f"soccer_props_report_{timestamp}.txt"
        report_file.write_text(report, encoding='utf-8')
        print(f"\n📁 Report saved to: {report_file}")
        
        # === CALIBRATION TRACKING (NEW) ===
        save_picks_to_calibration(analyzed)
        
        # === QUANT EXPORTS + CROSS-SPORT DATABASE AUTO-SAVE ===
        try:
            from soccer.soccer_slate_analyzer import (
                build_quant_edges_from_analyzed,
                export_soccer_quant_artifacts,
            )
            from engine.daily_picks_db import save_top_picks

            export_soccer_quant_artifacts(
                analyzed,
                league_tag="PASTE",
                source={"mode": "paste", "slate_file": str(slate_file)},
            )

            edges = build_quant_edges_from_analyzed(analyzed, source="soccer_paste")
            optimizable = [
                e
                for e in edges
                if e.get("pick_state") == "OPTIMIZABLE" and e.get("tier") in {"LEAN", "STRONG", "SLAM"}
            ]
            if optimizable:
                save_top_picks(optimizable, "SOCCER", top_n=5)
                print(f"✅ Saved top {min(5, len(optimizable))} Soccer picks to cross-sport database")
        except Exception as e:
            print(f"⚠️ Quant export / cross-sport save failed: {e}")
        
        # === AUTO-TELEGRAM SEND (like tennis) ===
        actionable = [p for p in analyzed if max(p.prob_over, p.prob_under) >= 0.60]
        if actionable:
            print(f"\n📱 Found {len(actionable)} actionable picks (60%+)")
            send_tg = input("Send top 7 to Telegram? [Y/n]: ").strip().lower()
            if send_tg != 'n':
                send_top_picks_to_telegram(7, skip_confirm=True)
    else:
        print("❌ No props parsed. Check format.")


def view_player_database():
    """Display player database summary."""
    db = PlayerDatabase()
    print(f"\n⚽ SOCCER PLAYER DATABASE — {len(db)} Players")
    print("=" * 60)
    
    # Group by league
    by_league = {}
    for player in db.players.values():
        league = player.league.replace("_", " ").title()
        if league not in by_league:
            by_league[league] = []
        by_league[league].append(player)
    
    for league, players in sorted(by_league.items()):
        print(f"\n{league}:")
        for p in sorted(players, key=lambda x: x.goals, reverse=True):
            print(f"  {p.name:25} | {p.team:20} | {p.position:12} | G:{p.goals:.2f} A:{p.assists:.2f}")


def search_player():
    """Search for player stats."""
    db = PlayerDatabase()
    
    query = input("\nEnter player name to search: ").strip()
    if not query:
        return
    
    results = db.search_players(query)
    
    if not results:
        print(f"No players found matching '{query}'")
        return
    
    print(f"\nFound {len(results)} player(s):")
    for p in results:
        print(f"\n{p.name} ({p.team})")
        print(f"  Position: {p.position}")
        print(f"  League: {p.league.replace('_', ' ').title()}")
        print(f"  Games: {p.games_played}")
        print(f"  Shots: {p.shots:.1f} | SOT: {p.shots_on_target:.1f}")
        print(f"  Goals: {p.goals:.2f} | Assists: {p.assists:.2f}")
        print(f"  Passes: {p.passes:.0f} | Tackles: {p.tackles:.1f}")


def league_selection():
    """Select league for analysis."""
    print("\n📊 LEAGUE SELECTION")
    print("-" * 40)
    leagues = [
        ("1", "premier_league", "Premier League (England)"),
        ("2", "la_liga", "La Liga (Spain)"),
        ("3", "bundesliga", "Bundesliga (Germany)"),
        ("4", "serie_a", "Serie A (Italy)"),
        ("5", "ligue_1", "Ligue 1 (France)"),
        ("6", "mls", "MLS (USA)"),
        ("7", "champions_league", "Champions League"),
    ]
    
    for num, code, name in leagues:
        print(f"  [{num}] {name}")
    
    choice = input("\nSelect league: ").strip()
    
    for num, code, name in leagues:
        if choice == num:
            print(f"\n✓ Selected: {name}")
            print("⚠️ League-specific analysis not yet available. Use [1] to paste props.")
            return
    
    print("Invalid selection")


def view_saved_slates():
    """List and optionally analyze saved slates."""
    print("\n📁 SAVED SLATES")
    print("-" * 40)
    
    slates = list(INPUTS_DIR.glob("slate_*.txt"))
    
    if not slates:
        print("No saved slates found.")
        return
    
    slates.sort(reverse=True)  # Most recent first
    
    for i, slate in enumerate(slates[:10], 1):
        print(f"  [{i}] {slate.name}")
    
    choice = input("\nEnter number to analyze (or Q to cancel): ").strip()
    
    if choice.upper() == 'Q':
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(slates):
            slate_file = slates[idx]
            print(f"\n🔄 Analyzing {slate_file.name}...")
            report = analyze_slate_file(str(slate_file), show_no_play=False)
            print(report)
    except (ValueError, IndexError):
        print("Invalid selection")


def update_stats_from_props():
    """
    [U] Update player stats from current slate via ESPN API + save CSV backup.
    """
    print("\n" + "=" * 60)
    print("⚽ UPDATE PLAYER STATS FROM PROPS")
    print("=" * 60)
    
    try:
        from soccer.data.update_from_props import update_from_slate, update_specific_players
        
        print("\nOptions:")
        print("[1] Update from latest slate file")
        print("[2] Update specific players")
        print("[Q] Cancel")
        
        choice = input("\nSelect option: ").strip().upper()
        
        if choice == "1":
            update_from_slate()
        elif choice == "2":
            names = input("\nEnter player names (comma-separated): ").strip()
            if names:
                player_list = [n.strip() for n in names.split(',') if n.strip()]
                if player_list:
                    update_specific_players(player_list)
        elif choice == "Q":
            print("Cancelled.")
        else:
            print("Invalid option.")
            
    except ImportError as e:
        print(f"❌ Update module not available: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def export_database_to_csv():
    """
    [E] Export current player database to CSV for backup/fallback.
    """
    print("\n" + "=" * 60)
    print("⚽ EXPORT PLAYER DATABASE TO CSV")
    print("=" * 60)
    
    try:
        from soccer.data.update_from_props import export_to_csv, export_to_json, CSV_BACKUP_FILE
        from soccer.data.player_database import KNOWN_PLAYERS
        
        print(f"\n📊 Database has {len(KNOWN_PLAYERS)} players")
        
        confirm = input("\nExport to CSV? [Y/n]: ").strip().lower()
        if confirm == 'n':
            print("Cancelled.")
            return
        
        csv_path = export_to_csv()
        json_path = export_to_json()
        
        print(f"\n✅ Export complete!")
        print(f"   CSV: {csv_path}")
        print(f"   JSON: {json_path}")
        
    except ImportError as e:
        print(f"❌ Export module not available: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

def refresh_api_stats():
    """Refresh player stats from API-Football (RapidAPI)."""
    print("\n🔄 API-FOOTBALL STATS REFRESH")
    print("=" * 60)
    
    try:
        from soccer.api_football_integration import get_api_key, fetch_soccer_stats_for_slate
        
        api_key = get_api_key()
        if not api_key:
            print("❌ No RAPIDAPI_KEY found in .env file!")
            print("\nSetup instructions:")
            print("1. Get API key from: https://rapidapi.com/api-sports/api/api-football")
            print("2. Add to .env: RAPIDAPI_KEY=your_key_here")
            return
        
        print(f"✅ API key found: {api_key[:8]}...")
        
        # Get players from recent slates
        db = PlayerDatabase()
        
        print(f"\n📊 Database has {len(db.players)} players")
        
        # Offer options
        print("\n[1] Update ALL players (slow, many API calls)")
        print("[2] Update specific player")
        print("[3] Test API connection")
        print("[Q] Cancel")
        
        choice = input("\nSelect option: ").strip().upper()
        
        if choice == "1":
            print("\n⚠️ This will make many API calls and may hit rate limits.")
            confirm = input("Continue? [y/N]: ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return
            
            # Would batch update here - for now show status
            print("\n🔄 Batch update not yet implemented.")
            print("Use option [2] to update individual players.")
            
        elif choice == "2":
            player_name = input("\nEnter player name: ").strip()
            if not player_name:
                return
            
            print(f"\n🔍 Searching API for '{player_name}'...")
            
            try:
                stats = fetch_soccer_stats_for_slate([player_name])
                if stats and player_name in stats:
                    print(f"\n✅ Found: {player_name}")
                    ps = stats[player_name]
                    print(f"  Team: {ps.get('team', 'N/A')}")
                    print(f"  Games: {ps.get('games_played', 0)}")
                    print(f"  Goals: {ps.get('goals', 0)}")
                    print(f"  Assists: {ps.get('assists', 0)}")
                    print(f"  Shots: {ps.get('shots', 0)}")
                else:
                    print(f"❌ Player '{player_name}' not found in API")
            except Exception as e:
                print(f"❌ API error: {e}")
                
        elif choice == "3":
            print("\n🔍 Testing API connection...")
            try:
                # Test with a known player
                stats = fetch_soccer_stats_for_slate(["Mohamed Salah"])
                if stats:
                    print("✅ API connection working!")
                    print(f"  Test player (Salah) found: {bool(stats.get('Mohamed Salah'))}")
                else:
                    print("⚠️ API returned empty response")
            except Exception as e:
                print(f"❌ API error: {e}")
        
    except ImportError as e:
        print(f"❌ API integration module not available: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def _is_soccer_props_data(text: str) -> bool:
    """
    Detect if input looks like Underdog soccer props paste data.
    
    DISABLED: Auto-detection was triggering prematurely on partial pastes.
    Users should use [1] to paste props explicitly.
    """
    # AUTO-DETECTION DISABLED - too aggressive, triggers before full paste
    # User reported: "prematurely run analysis without all info"
    # Fix: Always return False, force users to use [1] Paste Props mode
    return False
    
    # --- ORIGINAL CODE (commented out) ---
    # text_lower = text.lower().strip()
    # 
    # # Skip menu options - these are NOT props
    # if text_lower in ['1', '2', '3', '4', '5', '6', '7', 't', 'q', '']:
    #     return False
    # 
    # # Soccer-specific stat indicators
    # soccer_stats = ['goals', 'assists', 'shots', 'saves', 'tackles']
    # for stat in soccer_stats:
    #     if stat in text_lower:
    #         return True
    # 
    # return False


def _run_auto_analysis(initial_lines: list):
    """Run analysis when props are auto-detected from menu input."""
    print("\n⚽ PROPS DETECTED! Starting analysis...")
    print("-" * 40)
    print("Continue pasting your props below.")
    print("Press Enter twice when done.\n")
    
    lines = initial_lines.copy()
    blank_count = 0
    
    while blank_count < 2:
        try:
            line = input()
            if line.strip() == "":
                blank_count += 1
            else:
                blank_count = 0
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break
    
    if not lines:
        print("[WARN] No input received")
        return
    
    # Save to dated slate file
    slate_text = "\n".join(lines)
    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    slate_file = INPUTS_DIR / f"slate_{today}.txt"
    slate_file.write_text(slate_text, encoding='utf-8')
    print(f"\n✓ Saved {len(lines)} lines to {slate_file}")
    
    # Parse and analyze (auto-detect Pick6 or Underdog format)
    print("\n🔄 Analyzing with Risk-First Engine...")
    props = parse_slate_auto(slate_text)
    print(f"📋 Parsed {len(props)} props")
    
    if props:
        analyzed = [analyze_prop(p) for p in props]
        report = format_report(analyzed, show_no_play=False)
        print(report)
        
        # Save report to outputs folder
        report_file = OUTPUTS_DIR / f"soccer_props_report_{today}.txt"
        report_file.write_text(report, encoding='utf-8')
        print(f"\n📁 Report saved to: {report_file}")
        
        # === CALIBRATION TRACKING (NEW) ===
        save_picks_to_calibration(analyzed)
        
        # Offer Telegram send (default YES like tennis)
        actionable = [p for p in analyzed if max(p.prob_over, p.prob_under) >= 0.60]
        if actionable:
            print(f"\n📱 Found {len(actionable)} actionable picks (60%+)")
            send_tg = input("Send top 7 to Telegram? [Y/n]: ").strip().lower()
            if send_tg != 'n':
                send_top_picks_to_telegram(7, skip_confirm=True)
    else:
        print("❌ No props parsed. Check format.")


def _flush_input_buffer():
    """Flush any remaining input from the buffer."""
    import sys
    import msvcrt  # Windows only
    while msvcrt.kbhit():
        msvcrt.getch()


def run_menu():
    """Main menu loop with auto-detection of pasted props."""
    while True:
        print_header()
        show_menu()
        
        choice = input("  Select option: ").strip()
        choice_upper = choice.upper()
        
        # AUTO-DETECT: Check if user pasted props instead of menu option
        valid_keys = ['0', '1B', '8', '8A', '1', '2', '3', '4', '5', '6', '7',
                      'T', 'Q', 'R', 'C', 'A', 'U', 'E', 'V']
        if choice and choice_upper not in valid_keys and _is_soccer_props_data(choice):
            _run_auto_analysis([choice])
            input("\nPress Enter to continue...")
            try:
                _flush_input_buffer()
            except:
                pass
            continue
        
        if choice_upper in ("0", "1B"):
            auto_ingest_mode()
        elif choice_upper == "8A":
            # Shortcut: jump straight to all-leagues mode
            odds_api_ingest_mode(force_all=True)
        elif choice_upper == "8":
            odds_api_ingest_mode()
        elif choice_upper == "1":
            paste_props_mode()
        elif choice_upper == "2":
            # Find most recent slate
            slates = list(INPUTS_DIR.glob("slate_*.txt"))
            if slates:
                slates.sort(reverse=True)
                print(f"\n🔄 Analyzing {slates[0].name}...")
                report = analyze_slate_file(str(slates[0]), show_no_play=False)
                print(report)
            else:
                print("No slates found. Use option [1] to paste props first.")
        elif choice_upper == "3":
            # Show all including NO_PLAY
            slates = list(INPUTS_DIR.glob("slate_*.txt"))
            if slates:
                slates.sort(reverse=True)
                print(f"\n🔄 Analyzing {slates[0].name} (full report)...")
                report = analyze_slate_file(str(slates[0]), show_no_play=True)
                print(report)
            else:
                print("No slates found. Use option [1] to paste props first.")
        elif choice_upper == "4":
            view_player_database()
        elif choice_upper == "5":
            search_player()
        elif choice_upper == "6":
            print("\n⚠️ League selection temporarily disabled. Use [1] to paste props.")
        elif choice_upper == "7":
            view_saved_slates()
        elif choice_upper == "R":
            resolve_results()
        elif choice_upper == "C":
            show_calibration_report()
        elif choice_upper == "A":
            refresh_api_stats()
        elif choice_upper == "U":
            update_stats_from_props()
        elif choice_upper == "E":
            export_database_to_csv()
        elif choice_upper == "T":
            # Ask how many picks to send
            print("\n📱 SEND TOP PICKS TO TELEGRAM")
            num = input("How many picks? [7]: ").strip()
            try:
                num_picks = int(num) if num else 7
            except ValueError:
                num_picks = 7
            send_top_picks_to_telegram(num_picks)
        elif choice_upper == "V":
            # View latest report
            report_files = sorted(
                list(OUTPUTS_DIR.glob("soccer_*report*.txt")) + list(OUTPUTS_DIR.glob("SOCCER_*.txt")),
                key=lambda p: p.stat().st_mtime, reverse=True
            )
            if report_files:
                latest = report_files[0]
                print(f"\n  Latest Report: {latest.name}")
                print("-" * 60)
                try:
                    print(latest.read_text(encoding='utf-8'))
                except Exception as e:
                    print(f"  Error reading: {e}")
            else:
                print("\n  No soccer reports found in outputs/. Run analysis first.")
        elif choice_upper == "Q":
            print("\nReturning to main menu...")
            break
        else:
            print("\nInvalid option. Please try again.")
        
        input("\nPress Enter to continue...")
        # Flush any remaining buffered input from pasting
        try:
            _flush_input_buffer()
        except:
            pass  # Ignore errors on non-Windows


if __name__ == "__main__":
    run_menu()
