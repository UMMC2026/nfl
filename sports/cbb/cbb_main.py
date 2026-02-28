"""
CBB Module - Main Entry Point
==============================
Orchestrates the full CBB pipeline with slate ingest.

Order of operations:
1. parse_cbb_paste.py         ← INGEST
2. generate_cbb_edges.py      ← EDGES
3. apply_cbb_gates.py         ← GATES (min_mpg, blowout, role, etc.)
4. score_cbb_edges.py         ← SCORE
5. validate_cbb_output.py     ← HARD GATE
6. render_cbb_report.py       ← RENDER

Based on: tennis_main.py, menu.py ingest_slate()
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Setup paths
CBB_DIR = Path(__file__).parent
PROJECT_ROOT = CBB_DIR.parent.parent  # repo root = parent of "sports"
if str(CBB_DIR) not in sys.path:
    sys.path.insert(0, str(CBB_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import CBB modules (fully qualified to avoid confusion with top-level ingest package)
from sports.cbb.ingest.parse_cbb_paste import parse_text, save_slate, load_latest_slate
from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
from reporting.cbb_matchup_engine import MatchupEngine
from reporting.cbb_roster_tbl import generate_roster_table


def send_cbb_top7_telegram():
    """Send the top 7 CBB picks from the latest analysis JSON to Telegram."""
    import os
    import re
    from dotenv import load_dotenv
    load_dotenv()

    clear_screen()
    print("\n" + "=" * 70)
    print("  [T2] SEND TELEGRAM - TOP 7 CBB PICKS")
    print("=" * 70)

    # Find latest analysis JSON file (the actual edges data)
    json_outputs = sorted(OUTPUTS_DIR.glob("cbb_RISK_FIRST_*.json"), reverse=True)
    if not json_outputs:
        # Also check main outputs folder
        main_outputs = PROJECT_ROOT / "outputs"
        json_outputs = sorted(main_outputs.glob("cbb_RISK_FIRST_*.json"), reverse=True)
    
    if not json_outputs:
        print("\n❌ No CBB analysis found. Run [2] ANALYZE SLATE first.")
        pause()
        return
    
    latest = json_outputs[0]
    print(f"\nSource: {latest.name}")

    # Load and parse JSON
    try:
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"\n❌ Failed to load analysis: {e}")
        pause()
        return

    # Extract picks - look for edges array
    edges = data if isinstance(data, list) else data.get("edges", data.get("picks", []))
    
    # Filter to actionable picks (STRONG/LEAN) and sort by probability
    actionable = [
        e for e in edges 
        if e.get("tier", e.get("status", "")).upper() in ["STRONG", "LEAN", "PLAY"]
        or e.get("probability", 0) >= 0.60
    ]
    
    # Sort by probability descending
    actionable.sort(key=lambda x: x.get("probability", x.get("final_probability", 0)), reverse=True)
    
    # Take top 7
    picks = actionable[:7]
    
    if not picks:
        print("\n❌ No actionable picks found (no STRONG/LEAN tier picks).")
        pause()
        return

    print(f"\n✅ Found {len(picks)} actionable picks")

    # Format message
    msg_lines = ["🏀 *CBB Top Picks*\n"]
    for i, pick in enumerate(picks, 1):
        player = pick.get("player", pick.get("name", "Unknown"))
        stat = pick.get("stat", pick.get("market", "")).upper()
        direction = pick.get("direction", "").upper()
        line = pick.get("line", "?")
        prob = pick.get("probability", pick.get("final_probability", 0))
        tier = pick.get("tier", pick.get("status", "")).upper()
        team = pick.get("team", "")
        mu = pick.get("mean", pick.get("mu", pick.get("lambda", "")))
        
        dir_emoji = "⬆️" if direction == "HIGHER" else "⬇️" if direction == "LOWER" else ""
        tier_emoji = "🔥" if tier == "STRONG" else "📊" if tier == "LEAN" else "✅"
        
        msg_lines.append(f"{tier_emoji} *{i}. {player}* ({team})")
        msg_lines.append(f"   {stat} {dir_emoji} {direction} {line}")
        msg_lines.append(f"   Prob: {prob*100:.1f}% | Tier: {tier}")
        if mu:
            msg_lines.append(f"   Mean: {mu:.1f}" if isinstance(mu, (int, float)) else f"   Mean: {mu}")
        msg_lines.append("")
    
    message = "\n".join(msg_lines)

    # Telegram config
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("SPORTS_BOT_TOKEN")
    chat_ids_raw = (
        os.getenv("TELEGRAM_CHAT_IDS")
        or os.getenv("TELEGRAM_BROADCAST_CHAT_IDS")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    chat_ids = [c for c in re.split(r"[\s,]+", chat_ids_raw) if c]

    if not bot_token:
        print("\n⚠️ Telegram not configured: missing TELEGRAM_BOT_TOKEN (or SPORTS_BOT_TOKEN).")
    if not chat_ids:
        print("\n⚠️ Telegram not configured: missing TELEGRAM_CHAT_ID (or TELEGRAM_CHAT_IDS).")
    else:
        print(f"\nTelegram targets configured: {len(chat_ids)}")

    confirm = input("\nSend to Telegram? (y/n): ").strip().lower()
    if confirm != "y":
        print("\nAborted.")
        return

    # Send message
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        ok = 0
        fail = 0
        for chat_id in chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            try:
                response = requests.post(url, json=payload, timeout=15)
                if response.status_code == 200:
                    ok += 1
                else:
                    fail += 1
                    print(f"\n❌ Telegram error for chat_id={chat_id}: {response.text}")
            except Exception as e:
                fail += 1
                print(f"\n❌ Telegram send failed for chat_id={chat_id}: {e}")
        print(f"\n[✓] Sent to {ok} chats. {fail} failed.")
    except Exception as e:
        print(f"\n❌ Telegram send error: {e}")

# Directories
INPUTS_DIR = CBB_DIR / "inputs"
OUTPUTS_DIR = CBB_DIR / "outputs"
CONFIG_DIR = CBB_DIR / "config"
CACHE_DIR = CBB_DIR / "data" / "cache"

INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_label_for_filename(label: str, *, default: str = "CBB") -> str:
    """Return a filesystem-safe label for use in filenames."""
    raw = str(label or "").strip().upper()
    if not raw:
        return default
    safe = re.sub(r"[\\/:*?\"<>|]+", "_", raw)
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"[^A-Z0-9._-]+", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("._-")
    return safe or default


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def _cbb_offline_mode() -> bool:
    """Return True when CBB should avoid network calls (tests/offline runs)."""
    v = (os.environ.get("CBB_OFFLINE") or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def toggle_cbb_offline_mode() -> None:
    """Toggle offline mode for the current CBB process (no terminal/env edits required)."""
    if _cbb_offline_mode():
        try:
            del os.environ["CBB_OFFLINE"]
        except KeyError:
            pass
    else:
        os.environ["CBB_OFFLINE"] = "1"


def _render_roster_from_analysis(team_abbr: str, picks: List[Dict]) -> List[str]:
    """
    Render roster stats directly from ANALYSIS OUTPUT (player_mean from each edge).
    This is the CORRECT approach - uses the actual data we computed, not external APIs.
    """
    team_abbr = (team_abbr or "UNK").upper()
    
    # Group picks by player to get stats for each stat type
    player_stats = {}  # {player_name: {stat: mean, ...}}
    for p in picks:
        if (p.get("team") or "UNK").upper() != team_abbr:
            continue
        name = (p.get("player") or "").strip()
        if not name:
            continue
        stat = (p.get("stat") or "").lower()
        mean = p.get("player_mean") or p.get("mu") or 0
        
        if name not in player_stats:
            player_stats[name] = {"pts": "-", "reb": "-", "ast": "-", "3pm": "-", "tier": "SKIP"}
        
        # Map stat to column
        if stat == "points":
            player_stats[name]["pts"] = mean
        elif stat == "rebounds":
            player_stats[name]["reb"] = mean
        elif stat == "assists":
            player_stats[name]["ast"] = mean
        elif stat in ["threes", "3pm", "three_pointers"]:
            player_stats[name]["3pm"] = mean
        
        # Track best tier for this player
        tier = p.get("tier", "SKIP")
        if tier in ["LEAN", "STRONG", "SLAM"]:
            player_stats[name]["tier"] = tier
    
    lines: List[str] = []
    lines.append(f"ROSTER (FROM ANALYSIS) - {team_abbr}")
    lines.append(f"{'PLAYER':<20} {'PTS':>6} {'REB':>6} {'AST':>6} {'3PM':>6} {'TIER':>8}")
    lines.append("-" * 60)
    
    if not player_stats:
        lines.append(f"{'[No analyzed players for this team]':<20}")
        return lines
    
    # Sort by whether they have actionable picks, then by PTS
    def sort_key(item):
        name, stats = item
        is_actionable = 1 if stats["tier"] in ["LEAN", "STRONG", "SLAM"] else 0
        pts = float(stats["pts"]) if stats["pts"] != "-" else 0
        return (-is_actionable, -pts)
    
    sorted_players = sorted(player_stats.items(), key=sort_key)
    
    for name, stats in sorted_players:
        pts_str = f"{float(stats['pts']):>6.1f}" if stats['pts'] != "-" else f"{'-':>6}"
        reb_str = f"{float(stats['reb']):>6.1f}" if stats['reb'] != "-" else f"{'-':>6}"
        ast_str = f"{float(stats['ast']):>6.1f}" if stats['ast'] != "-" else f"{'-':>6}"
        tpm_str = f"{float(stats['3pm']):>6.1f}" if stats['3pm'] != "-" else f"{'-':>6}"
        tier_str = stats['tier']
        marker = ">" if tier_str in ["LEAN", "STRONG"] else " "
        lines.append(f"{marker}{name[:18]:<19} {pts_str} {reb_str} {ast_str} {tpm_str} {tier_str:>8}")
    
    return lines


def _render_cached_roster_table_for_team(team_abbr: str, props: List[Dict]) -> List[str]:
    """Render a roster-style table using ONLY cached/override stats for slate players."""
    provider = CBBDataProvider()
    team_abbr = (team_abbr or "UNK").upper()

    # Collect unique players from slate for this team
    players = []
    seen = set()
    for p in props:
        if (p.get("team") or "UNK").upper() != team_abbr:
            continue
        name = (p.get("player") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        stats = provider.cache.get_player_stats(name, team_abbr)
        if stats and (stats.get("games_played", 0) or 0) > 0:
            players.append((name, stats))

    lines: List[str] = []
    lines.append(f"ROSTER (CACHED) - {team_abbr}")
    lines.append(f"{'PLAYER':<20} {'MIN':>5} {'PTS':>5} {'REB':>5} {'AST':>5} {'3PM':>5} {'GP':>4} {'SRC':>6}")
    lines.append("-" * 70)

    if not players:
        lines.append(f"{'[No cached player stats for slate]':<20} {'-':>5} {'-':>5} {'-':>5} {'-':>5} {'-':>5} {'-':>4} {'-':>6}")
        return lines

    # Sort by points_avg descending
    players.sort(key=lambda t: float(t[1].get("points_avg", 0) or 0), reverse=True)

    for name, s in players:
        src = "MANUAL" if s.get("manual") else "CACHE"
        lines.append(
            f"{name[:18]:<20} "
            f"{float(s.get('minutes_avg', 0) or 0):>5.1f} "
            f"{float(s.get('points_avg', 0) or 0):>5.1f} "
            f"{float(s.get('rebounds_avg', 0) or 0):>5.1f} "
            f"{float(s.get('assists_avg', 0) or 0):>5.1f} "
            f"{float(s.get('three_pm_avg', 0) or 0):>5.1f} "
            f"{int(s.get('games_played', 0) or 0):>4d} "
            f"{src:>6}"
        )

    return lines


def pause(msg: str = "\nPress Enter to continue..."):
    """Pause for user input."""
    input(msg)


def print_cbb_header():
    """Print CBB module header."""
    print("\n" + "=" * 65)
    print("[CBB] COLLEGE BASKETBALL MODULE v1.0")
    # ASCII-only to avoid console mojibake.
    print("   Market Gate: 12% | L10 Blend: 0.40 | Caps: STRICT")
    print("   Poisson model | No SLAM tier | Stricter caps")
    print("=" * 65)


def _safe_read_json(path: Path) -> Optional[Dict]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _write_run_state(patch: Dict) -> None:
    """Merge-patch cbb_run_latest.json with the provided fields."""
    state_path = OUTPUTS_DIR / "cbb_run_latest.json"
    state = _safe_read_json(state_path) or {}
    # Shallow merge is enough for our use-case.
    state.update(patch or {})
    try:
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        # Never fail the pipeline/menu because state persistence failed.
        pass


def _cbb_latest_run_summary() -> str:
    """Return a single-line breakdown of the last run, if present."""
    state_path = OUTPUTS_DIR / "cbb_run_latest.json"
    s = _safe_read_json(state_path)
    if not s:
        return "LastRun=NONE"

    ts = s.get("ended_at") or s.get("started_at") or "?"
    mode = s.get("mode") or "?"
    props = s.get("props")
    raw = s.get("raw_edges")
    dedup = s.get("dedup_edges")
    passed = s.get("passed")
    failed = s.get("failed")
    skip = s.get("skipped")
    actionable = s.get("actionable")

    def _n(x) -> str:
        try:
            return str(int(x))
        except Exception:
            return "?" if x is None else str(x)

    return (
        f"LastRun={ts} | mode={mode} | props={_n(props)} | raw={_n(raw)} | dedup={_n(dedup)} | "
        f"pass={_n(passed)} fail={_n(failed)} skip={_n(skip)} | actionable={_n(actionable)}"
    )


def _cbb_latest_slate_summary() -> str:
    """Return a single-line summary for the latest slate, if present."""
    latest_path = INPUTS_DIR / "cbb_slate_latest.json"
    data = _safe_read_json(latest_path)
    if not data:
        return "LatestSlate=NONE"
    ts = data.get("timestamp") or "?"
    cnt = data.get("count")
    try:
        cnt_s = str(int(cnt)) if cnt is not None else "?"
    except Exception:
        cnt_s = str(cnt) if cnt is not None else "?"
    return f"LatestSlate={cnt_s} props @ {ts}"


def _cbb_latest_report_summary() -> str:
    """Return a single-line summary for the latest report, if present."""
    report_path = OUTPUTS_DIR / "cbb_report_latest.txt"
    if not report_path.exists():
        return "LatestReport=NONE"
    try:
        # Read only enough to parse the header quickly.
        head = report_path.read_text(encoding="utf-8", errors="replace").splitlines()[:40]
        generated = None
        totals = None
        for line in head:
            s = (line or "").strip()
            if s.lower().startswith("generated:"):
                generated = s.split(":", 1)[1].strip() if ":" in s else s
            if "total edges:" in s.lower() and "actionable" in s.lower():
                totals = s
        if generated and totals:
            return f"LatestReport={generated} | {totals}"
        # Fallback to file mtime.
        mtime = datetime.fromtimestamp(report_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return f"LatestReport={mtime} (mtime)"
    except Exception:
        return "LatestReport=UNREADABLE"


def _print_cbb_command_center_menu() -> None:
    """NBA-style menu for CBB so the user can see system state at a glance."""
    offline = "ON " if _cbb_offline_mode() else "OFF"
    jiggy = "ON " if _CBB_SETTINGS.get("jiggy", False) else "OFF"
    slate_line = _cbb_latest_slate_summary()
    report_line = _cbb_latest_report_summary()
    run_line = _cbb_latest_run_summary()

    print("\n" + "=" * 70)
    print("      CBB PROPS ANALYZER - PRODUCTION v1.2")
    print("           Risk-First Pipeline + Graduated Gate v2.0")
    print("=" * 70)

    print(f"\n  CURRENT: Offline={offline} (toggle: [F]) | JIGGY={jiggy} (toggle: [J]) | {slate_line}")
    print(f"  OUTPUT:  {report_line}")
    print(f"  RUN:     {run_line}")

    box_lines = [
        "  +================================================================+",
        "  |  PREGAME WORKFLOW                                              |",
        "  |  ----------------                                              |",
        "  |  [1B] 🔌 AUTO-INGEST        - Playwright scraper (DK/PP/UD)     |",
        "  |  [8] 🛰️ ODDS API INGEST      - No-scrape props (us_dfs)         |",
        "  |  [1] INGEST NEW SLATE       - Paste Underdog CBB lines          |",
        "  |  [2] ANALYZE SLATE          - Run full CBB pipeline (latest)    |",
        "  |  [3] QUICK ANALYZE          - Paste props + run immediately     |",
        "  |  [4] ROSTER AVERAGES        - Player stats from analysis output  |",
        "  |  [I] INTERACTIVE FILTER     - Custom filter combinations        |",
        "  |  [P] MONTE CARLO            - Entry optimization (combos)       |",
        "  |                                                                |",
        "  |  POSTGAME                                                      |",
        "  |  --------                                                      |",
        "  |  [6] RESOLVE PICKS          - Enter results, update history     |",
        "  |  [7] CALIBRATION BACKTEST   - Historical accuracy analysis      |",
        "  |  [DR] DRIFT DETECTOR        - Calibration drift alerts          |",
        "  |                                                                |",
        "  |  INSIGHTS                                                      |",
        "  |  --------                                                      |",
        "  |  [T] STAT RANKINGS          - Top-5 picks per stat category     |",
        "  |  [M] MATCHUP MEMORY         - Player x Opponent history         |",
        "  |  [A] ARCHETYPE FILTER       - Filter by player role/archetype   |",
        "  |  [P2] PROBABILITY BREAKDOWN - Confidence composition            |",
        "  |  [K] DISTRIBUTION PREVIEW   - Monte Carlo visualization         |",
        "  |  [X] LOSS EXPECTATION       - Worst-case scenarios              |",
        "  |                                                                |",
        "  |  MANAGEMENT                                                    |",
        "  |  ----------                                                    |",
        "  |  [9] BAN LIST               - Manage player+stat bans           |",
        "  |  [10] SETTINGS              - Toggle features & modes           |",
        "  |  [J] JIGGY MODE             - Toggle UNGOVERNED testing         |",
        "  |  [F] OFFLINE MODE           - Toggle ESPN/network access        |",
        "  |  [O] PLAYER OVERRIDES       - Manual averages when ESPN missing |",
        "  |  [C] CONFIGURATION          - Show CBB thresholds + config files|",
        "  |  [S] VIEW SLATE             - Show latest parsed slate          |",
        "  |  [V] VIEW RESULTS           - Show latest CBB report            |",
        "  |                                                                |",
        "  |  REPORTS                                                       |",
        "  |  -------                                                       |",
        "  |  [H] CHEAT SHEET            - Quick reference report            |",
        "  |  [D] DIAGNOSIS ALL          - Check reports for issues          |",
        "  |  [R] EXPORT REPORT          - Save latest report to a file      |",
        "  |  [R2] PROFESSIONAL REPORT   - Generate NBA-style pro report     |",
        "  |  [T2] TELEGRAM              - Send Top 7 Picks to Telegram       |",
        "  |  [0] BACK                   - Return to main menu               |",
        "  +================================================================+",
    ]
    print("\n".join(box_lines))


def run_cbb_odds_api_ingest() -> None:
    """Run Odds API no-scrape ingest for CBB (NCAAB), then auto-analyze."""
    import subprocess
    import os
    
    clear_screen()
    print("\n" + "=" * 70)
    print("  [8] ODDS API NO-SCRAPE INGEST — CBB (NCAAB)")
    print("=" * 70)
    print("\nFetching CBB player props from The Odds API (regions=us_dfs)...")
    
    # Show configured bookmakers
    bookmakers_env = os.getenv("ODDS_API_BOOKMAKERS") or "(default)"
    if bookmakers_env == "(default)":
        print("Bookmakers: PrizePicks, Underdog, Pick6, Betr, MyBookie (default)")
    else:
        print(f"Bookmakers: {bookmakers_env}")
    
    print("Markets: player_points, player_rebounds, player_assists")
    print("\nℹ️  CBB props are event-dependent (marquee games prioritized)")
    print("   If 0 props returned, try closer to game time or use manual paste [1]\n")
    
    script_path = (PROJECT_ROOT / "scripts" / "fuoom_no_scrape_ingest.py").resolve()
    if not script_path.exists():
        print(f"❌ Missing script: {script_path}")
        return
    
    try:
        # Run Odds API ingest with BASKETBALL_NCAAB sport tag
        proc = subprocess.run(
            [sys.executable, str(script_path), "--sport", "BASKETBALL_NCAAB"],
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        
        if proc.returncode != 0:
            if proc.returncode == 4:
                print("\n⚠️  Odds API returned 0 props for CBB.")
                print("   This usually means DFS books haven't posted CBB prop markets yet.")
                print("   Try closer to game time or use manual paste [1].")
            else:
                print(f"\n❌ Odds API ingest failed (exit code {proc.returncode}).")
            return
        
        # Check if props_latest.json was created
        props_latest = PROJECT_ROOT / "outputs" / "props_latest.json"
        if not props_latest.exists():
            print(f"\n❌ No props file created: {props_latest}")
            return
        
        # Load props and convert to CBB slate format
        print("\n📥 Converting Odds API props to CBB slate format...")
        try:
            with open(props_latest, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            props = data.get('props', [])
            if not props:
                print("❌ No props found in props_latest.json")
                return
            
            # Convert to CBB slate format
            cbb_props = []
            for prop in props:
                player = prop.get('player', '')
                stat = prop.get('stat', '')
                line = prop.get('line', 0)
                direction = prop.get('direction', 'higher')
                
                # Map stat names (Odds API uses different names)
                stat_map = {
                    'points': 'PTS',
                    'rebounds': 'REB',
                    'assists': 'AST',
                    'threes': '3PM',
                    '3pm': '3PM',
                    'pts_rebs_asts': 'PRA',
                    'pra': 'PRA',
                    'points+rebounds+assists': 'PRA',
                    'pts+reb+ast': 'PRA',
                    'points+assists': 'PTS+AST',
                    'pts+ast': 'PTS+AST',
                    'points+rebounds': 'PTS+REB',
                    'pts+reb': 'PTS+REB',
                    'rebounds+assists': 'REB+AST',
                    'reb+ast': 'REB+AST',
                    'blocks': 'BLK',
                    'steals': 'STL',
                    'turnovers': 'TO',
                    'blocks+steals': 'BLK+STL',
                }
                stat = stat_map.get(stat.lower(), stat.upper())
                
                # Team assignment is deferred — store both teams for now
                raw_meta = prop.get('meta', {}).get('raw', {})
                home_team_raw = raw_meta.get('home_team', 'UNK')
                away_team_raw = raw_meta.get('away_team', '')
                
                cbb_props.append({
                    'player': player,
                    'team': 'UNK',  # Resolved below via roster matching
                    'opponent': 'UNK',  # Resolved below via roster matching
                    'stat': stat,
                    'line': float(line),
                    'direction': direction,
                    'source': 'OddsAPI',
                    '_home_team': home_team_raw,
                    '_away_team': away_team_raw,
                })
            
            if not cbb_props:
                print("❌ No valid CBB props after conversion")
                return
            
            # ── Resolve team assignments ──────────────────────────────────
            # OddsAPI doesn't tag players with their team.  We fetch each
            # game's two rosters once, then match player names.
            try:
                from sports.cbb.ingest.cbb_data_provider import CBBStatsCache, CBBDataProvider
                _cache = CBBStatsCache()
                _provider = CBBDataProvider()
                
                # Collect unique game matchups from the props
                games = {}  # (home_raw, away_raw) → {home_abbr, away_abbr, home_roster, away_roster}
                for p in cbb_props:
                    key = (p.get('_home_team', ''), p.get('_away_team', ''))
                    if key not in games:
                        h_abbr = _cache._normalize_team(key[0])
                        a_abbr = _cache._normalize_team(key[1]) if key[1] else ''
                        games[key] = {'home_abbr': h_abbr, 'away_abbr': a_abbr,
                                      'home_roster': set(), 'away_roster': set()}
                        # Fetch rosters from ESPN (one API call per team)
                        for abbr, roster_key in [(h_abbr, 'home_roster'), (a_abbr, 'away_roster')]:
                            if not abbr:
                                continue
                            try:
                                team_id = _provider.espn.search_team(abbr)
                                if team_id:
                                    roster = _provider.espn.get_team_roster(team_id)
                                    if roster:
                                        for rp in roster:
                                            # CBBPlayer objects have .name attribute
                                            name = getattr(rp, 'name', None) or (rp.get('name', '') if isinstance(rp, dict) else str(rp))
                                            if name:
                                                games[key][roster_key].add(name.strip().upper())
                            except Exception:
                                pass
                
                # Now assign teams based on roster match
                resolved = 0
                for p in cbb_props:
                    gkey = (p.get('_home_team', ''), p.get('_away_team', ''))
                    g = games.get(gkey, {})
                    player_upper = p['player'].strip().upper()
                    h_abbr = g.get('home_abbr', 'UNK')
                    a_abbr = g.get('away_abbr', '')
                    
                    if player_upper in g.get('home_roster', set()):
                        p['team'] = h_abbr
                        resolved += 1
                    elif player_upper in g.get('away_roster', set()):
                        p['team'] = a_abbr
                        resolved += 1
                    else:
                        # Partial name match (last name)
                        pl_parts = player_upper.split()
                        last_name = pl_parts[-1] if pl_parts else ''
                        matched_home = any(last_name and r.split()[-1] == last_name for r in g.get('home_roster', set()) if r.split())
                        matched_away = any(last_name and r.split()[-1] == last_name for r in g.get('away_roster', set()) if r.split())
                        if matched_home and not matched_away:
                            p['team'] = h_abbr
                            resolved += 1
                        elif matched_away and not matched_home:
                            p['team'] = a_abbr
                            resolved += 1
                        else:
                            p['team'] = h_abbr  # Default to home
                    
                    # ── SET OPPONENT (Bug Fix: opponent field was missing) ──
                    # After determining player's team, set opponent to the other team
                    if p['team'] == h_abbr:
                        p['opponent'] = a_abbr if a_abbr else 'UNK'
                    elif p['team'] == a_abbr:
                        p['opponent'] = h_abbr
                    else:
                        # Fallback: if team wasn't resolved to either, mark opponent as UNK
                        p['opponent'] = 'UNK'
                    
                    # Clean up temp fields
                    p.pop('_home_team', None)
                    p.pop('_away_team', None)
                
                print(f"   Team resolution: {resolved}/{len(cbb_props)} players matched to rosters")
            except Exception as e:
                # Fallback: normalize home_team for all
                print(f"   ⚠️ Team resolution failed ({e}), using home team for all")
                try:
                    from sports.cbb.ingest.cbb_data_provider import CBBStatsCache
                    _cache = CBBStatsCache()
                    for p in cbb_props:
                        ht = p.pop('_home_team', 'UNK')
                        at = p.pop('_away_team', None)
                        p['team'] = _cache._normalize_team(ht)
                        # Set opponent to away team (all players assigned to home in fallback)
                        p['opponent'] = _cache._normalize_team(at) if at else 'UNK'
                except Exception:
                    for p in cbb_props:
                        ht = p.pop('_home_team', 'UNK')
                        at = p.pop('_away_team', None)
                        p['team'] = ht
                        # Can't normalize, use raw away team name or UNK
                        p['opponent'] = at if at else 'UNK'
            
            # Save to CBB inputs (directory + prefix, NOT full filepath)
            output_path = save_slate(cbb_props, INPUTS_DIR, filename_prefix="cbb_slate_oddsapi")
            
            print(f"✅ Converted {len(cbb_props)} props")
            print(f"   Saved to: {output_path.name}")
            print(f"   ✅ cbb_slate_latest.json UPDATED")
            
            # Auto-analyze
            print("\n🔄 Running CBB analysis...")
            ok = run_full_pipeline(skip_ingest=True)
            if ok:
                print("\n✅ CBB analysis complete!")
            else:
                print("\n⚠️  Analysis had issues (see messages above)")
                
        except Exception as e:
            print(f"\n❌ Error converting props: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"\n❌ Failed to run Odds API ingest: {e}")


def export_latest_cbb_report() -> None:
    """Export (copy) latest CBB report to a user-specified path."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [R] EXPORT CBB REPORT")
    print("=" * 70)

    report_path = OUTPUTS_DIR / "cbb_report_latest.txt"
    if not report_path.exists():
        print("\n[X] No latest report found to export.")
        print(f"  Expected: {report_path}")
        return

    default_name = f"cbb_report_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    dest_raw = input(f"\nExport path (blank = {default_name} in CBB outputs): ").strip()
    dest_path = Path(dest_raw) if dest_raw else (OUTPUTS_DIR / default_name)

    try:
        content = report_path.read_text(encoding="utf-8", errors="replace")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")
        print(f"\n[OK] Exported to: {dest_path}")
    except Exception as e:
        print(f"\n[X] Export failed: {e}")


def generate_professional_cbb_report() -> None:
    """Generate NBA-style professional report for CBB."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [R2] CBB PROFESSIONAL REPORT GENERATOR")
    print("=" * 70)
    
    try:
        from generate_professional_report import load_latest_edges, generate_professional_report, export_report
        
        print("\n  Loading latest edges...")
        edges_data = load_latest_edges()
        
        if not edges_data:
            print("\n  [!] No edges data found. Run [2] ANALYZE SLATE first.")
            return
        
        print("  Generating professional report...")
        report = generate_professional_report(edges_data)
        
        print("  Exporting...")
        output_path = export_report(report)
        
        print(f"\n  ✅ PROFESSIONAL REPORT SAVED!")
        print(f"     → {output_path}")
        
        # Ask if user wants to view
        view_choice = input("\n  View report now? [Y/n]: ").strip().upper()
        if view_choice != "N":
            print("\n" + "=" * 70)
            print(report)
            print("=" * 70)
            
    except ImportError as e:
        print(f"\n  [!] Import error: {e}")
        print("      Make sure generate_professional_report.py exists in sports/cbb/")
    except Exception as e:
        print(f"\n  [!] Error generating report: {e}")


def ingest_cbb_slate() -> Optional[List[Dict]]:
    """
    Ingest CBB slate from Underdog paste.
    
    Returns: List of parsed props or None
    """
    clear_screen()
    print("\n" + "=" * 65)
    print("  CBB SLATE INGEST")
    print("=" * 65)
    
    print("\nOptions:")
    print("  [1] Paste Underdog lines (type END when done)")
    print("  [2] Load existing slate")
    print("  [3] Load from JSON file path")
    print("  [0] Cancel")
    
    choice = input("\nChoice: ").strip()
    
    if choice == "1":
        print("\n" + "-" * 50)
        print("Paste Underdog CBB lines below.")
        print("Type 'END' on its own line when finished.")
        print("-" * 50 + "\n")
        
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == "END":
                    break
                if line.strip():
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                break
        
        if not lines:
            print("\n✗ No lines entered.")
            return None
        
        # Parse
        props = parse_text('\n'.join(lines))
        
        if not props:
            print("\n✗ No props parsed from input.")
            return None
        
        # Label
        label_in = input("\nLabel for this slate (e.g., DUKE_UNC): ").strip().upper() or "CBB"
        label = _sanitize_label_for_filename(label_in, default="CBB")
        if label != label_in:
            print(f"\nNote: label sanitized for filename -> {label}")
        
        # Save
        output_path = save_slate(props, INPUTS_DIR)
        
        # Also save with label
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        labeled_path = INPUTS_DIR / f"cbb_{label}_{timestamp}.json"
        with open(labeled_path, "w") as f:
            json.dump({
                "label": label,
                "timestamp": timestamp,
                "count": len(props),
                "props": props
            }, f, indent=2)
        
        print(f"\n[OK] Parsed {len(props)} CBB props")
        print(f"📁 Saved to: {output_path}")
        print(f"📁 Labeled:  {labeled_path}")
        
        return props
    
    elif choice == "2":
        props = load_latest_slate(INPUTS_DIR)
        if props:
            print(f"\n[OK] Loaded {len(props)} props from latest slate")
            return props
        else:
            print("\n✗ No existing slate found")
            return None
    
    elif choice == "3":
        file_path = input("\nEnter JSON file path: ").strip()
        try:
            with open(file_path) as f:
                data = json.load(f)
            props = data.get("props", data.get("plays", []))
            print(f"\n[OK] Loaded {len(props)} props from {file_path}")
            return props
        except Exception as e:
            print(f"\n✗ Error loading file: {e}")
            return None
    
    return None


def generate_cbb_edges(props: List[Dict]) -> List[Dict]:
    """
    Generate edges from props using Poisson model.
    
    Applies CBB-specific probability caps:
    - No SLAM tier (max 79%)
    - STRONG ≥70%
    - LEAN ≥60%
    
    IMPORTANT: Deduplicates props - keeps only the BETTER direction
    when both higher and lower exist for same player+stat+line.
    """
    print("\n[2/5] GENERATE EDGES")
    print("-" * 40)
    
    # First, compute probabilities for all props
    raw_edges = []
    seen_props = set()
    
    from core.validation.fail_fast import fail_fast_check, FailFastError
    from scoring.hard_gates import hard_stop_gate
    from core.integrity.checksum import model_integrity_checksum

    # Initialize normalizer for team name resolution (OddsAPI full names → abbreviations)
    try:
        from sports.cbb.ingest.cbb_data_provider import CBBStatsCache
        provider_for_norm = CBBStatsCache()
    except Exception:
        provider_for_norm = None

    for prop in props:
        # Guardrail: Underdog pastes can contain duplicates. If the same prop shows up
        # multiple times (same player/stat/line/direction), keep only one.
        prop_key = (
            (prop.get("player") or "").strip(),
            (prop.get("stat") or "").strip().lower(),
            float(prop.get("line", 0) or 0),
            (prop.get("direction") or "").strip().lower(),
        )
        if prop_key in seen_props:
            continue
        seen_props.add(prop_key)

        try:
            prob_result = compute_cbb_probability(prop)
            # Get stat-specific sigma from the CBB sigma table
            prop_stat = (prop.get("stat") or "").lower()
            prop_mean = prob_result.get("player_mean", 0)
            prop_sigma = prob_result.get("projected_sigma", get_cbb_sigma(prop_stat, prop_mean))
            
            # FAIL FAST VALIDATION
            # Note: CBB uses NegBin model with stat-specific sigma
            # The key checks are: sport valid, mu > 0, sigma > 0, prob not coin-flip
            fail_fast_check(
                sport="CBB",
                stat=prop.get("stat", ""),
                game_logs=[1] * max(3, prop.get("sample_n", 10)),  # Placeholder for sample count
                mu_raw=prop_mean,
                sigma=prop_sigma,
                prob_raw=prob_result["probability"]
            )
            # HARD-STOP GATE
            # Signature: hard_stop_gate(mu, sigma, line, prob)
            passed, reason = hard_stop_gate(
                mu=prop_mean,
                sigma=prop_sigma,
                line=float(prop.get("line", 0)),
                prob=prob_result["probability"]
            )
            if not passed:
                print(f"[HARD STOP] {prop.get('player')} {prop.get('stat')} {prop.get('line')}: {reason}")
                continue
            # INTEGRITY CHECKSUM
            # Note: model_integrity_checksum expects specific keys: mu, sigma, n_games, prob_raw, line
            checksum = model_integrity_checksum({
                "mu": prop_mean,
                "sigma": prop_sigma,
                "n_games": prop.get("sample_n", 10),
                "prob_raw": prob_result.get("raw_prob", prob_result["probability"]),
                "line": float(prop.get("line", 0)),
            })
            # Checksum logged silently in production (remove verbose print)
        except FailFastError as e:
            print(f"[FAIL FAST] {prop.get('player')} {prop.get('stat')} {prop.get('line')}: {e}")
            continue
        except Exception as e:
            print(f"[HARD STOP] {prop.get('player')} {prop.get('stat')} {prop.get('line')}: {e}")
            continue

        # Ensure edge_id is unique across multiple lines for the same player/stat/direction.
        # (Validation requires edge_id uniqueness.)
        team_abbr = (prop.get("team") or "UNK")
        # Normalize full team names → abbreviations (OddsAPI sends "Louisville Cardinals" etc.)
        try:
            if provider_for_norm:
                team_abbr = provider_for_norm._normalize_team(team_abbr)
        except Exception:
            pass
        line_slug = str(prop.get("line", "")).replace(".", "p")
        edge_id = f"cbb_{team_abbr}_{prop['player']}_{prop['stat']}_{line_slug}_{prop['direction']}".replace(" ", "_")

        edge = {
            "edge_id": edge_id,
            "sport": "cbb",
            "league": "CBB",
            "player": prop["player"],
            "team": prop.get("team", "UNK"),
            "opponent": prop.get("opponent", "UNK"),
            "stat": prop["stat"],
            "line": prop["line"],
            "direction": prop["direction"],
            "probability": prob_result["probability"],
            "player_mean": prob_result.get("player_mean"),
            # Quick Analysis compat: it reads 'mean'/'std' keys
            "mean": prob_result.get("player_mean", 0) or 0,
            "std": prob_result.get("projected_sigma", 0) or 0,
            # v2.0 mandatory tags
            "mean_source": prob_result.get("mean_source", "FALLBACK"),
            "confidence_flag": prob_result.get("confidence_flag", "UNVERIFIED"),
            "signal_flag": prob_result.get("signal_flag", "OK"),
            # v2.0 decision trace (first-class)
            "decision_trace": prob_result.get("decision_trace", {}),
            "model_used": prob_result.get("model", "poisson"),
            "data_source": prob_result.get("data_source", "fallback"),
            "tier": "PENDING",
            "goblin": prop.get("goblin", False),
            "demon": prop.get("demon", False),
            "taco": prop.get("taco", False),
            "gates_passed": [],
            "gates_failed": [],
        }
        raw_edges.append(edge)
    
    # Deduplicate: keep only the better direction for each player+stat+line
    # Group by (player, stat, line)
    grouped = {}
    for edge in raw_edges:
        key = (edge["player"], edge["stat"], edge["line"])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(edge)
    
    # For each group, keep the edge with higher probability
    edges = []
    for key, group in grouped.items():
        if len(group) == 1:
            edges.append(group[0])
        else:
            # Pick the one with higher probability
            sorted_group = sorted(group, key=lambda e: e["probability"], reverse=True)
            best = sorted_group[0]
            dropped = sorted_group[1:]
            # v2.0 transparency: store dropped direction(s)
            if dropped:
                # Keep only the closest competitor for readability
                d0 = dropped[0]
                best["dedupe_dropped"] = {
                    "direction": d0.get("direction"),
                    "probability": d0.get("probability"),
                    "kept": best.get("direction"),
                    "kept_probability": best.get("probability"),
                }
            edges.append(best)
    
    print(f"  Generated {len(edges)} edges (from {len(raw_edges)} raw, deduplicated)")
    return edges


def compute_cbb_probability(prop: Dict) -> Dict:
    """
    Compute probability for a CBB prop using Poisson model.
    
    Data Sources (in order of preference):
    1. ESPN CBB API (real player averages)
    2. Line-based estimation (fallback)
    
    CBB Caps (stricter than NBA):
    - No SLAM tier (max 79%)
    - STRONG ceiling: 79%
    - Core stats cap: 75%
    """
    line = prop["line"]
    direction = prop["direction"]
    stat = prop["stat"].lower()
    player_name = prop.get("player", "")
    team_abbr = prop.get("team", "")
    
    # Normalize team name early (OddsAPI sends full names like "Louisville Cardinals")
    try:
        from sports.cbb.ingest.cbb_data_provider import CBBStatsCache
        _norm_cache = CBBStatsCache()
        team_abbr = _norm_cache._normalize_team(team_abbr)
    except Exception:
        pass
    
    # Try to get player mean with explicit sourcing (v2.0 contract)
    estimated_mean = None
    mean_source = "FALLBACK"
    confidence_flag = "UNVERIFIED"
    data_source = "fallback"
    _raw_game_logs = None  # Stored for hybrid router


    try:
        from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
        from sports.cbb.features.player_features import build_player_features
        provider = CBBDataProvider()

        # Map stat to data provider stat key
        stat_map = {
            "points": "points",
            "pts": "points",
            "rebounds": "rebounds",
            "reb": "rebounds",
            "assists": "assists",
            "ast": "assists",
            "3pm": "three_pointers",
            "threes": "three_pointers",
            "pra": "pra",
            "pts+reb+ast": "pra",
            "points+rebounds+assists": "pra",
            "pts+reb": "points_rebounds",
            "points+rebounds": "points_rebounds",
            "pts+ast": "points_assists",
            "points+assists": "points_assists",
            "reb+ast": "rebounds_assists",
            "rebounds+assists": "rebounds_assists",
            "steals": "steals",
            "stl": "steals",
            "blocks": "blocks",
            "blk": "blocks",
            "turnovers": "turnovers",
            "to": "turnovers",
        }
        stat_key = stat_map.get(stat, stat) or stat

        # Try to get game logs for blended projection
        game_logs = provider.cache.get_player_stats(player_name, team_abbr)
        blended_mean = None
        if game_logs and isinstance(game_logs, dict) and game_logs.get("game_logs"):
            _raw_game_logs = game_logs["game_logs"]  # Save for hybrid router
            features = build_player_features(player_id=player_name, game_logs=game_logs["game_logs"])
            if stat_key == "points":
                blended_mean = features.blended_points
            elif stat_key == "rebounds":
                blended_mean = features.blended_rebounds
            elif stat_key == "assists":
                blended_mean = features.blended_assists
            elif stat_key in ("pra", "pts+reb+ast"):
                blended_mean = features.blended_points + features.blended_rebounds + features.blended_assists
            elif stat_key in ("points_assists",):
                blended_mean = features.blended_points + features.blended_assists
            elif stat_key in ("points_rebounds",):
                blended_mean = features.blended_points + features.blended_rebounds
            elif stat_key in ("rebounds_assists",):
                blended_mean = features.blended_rebounds + features.blended_assists
        # Fallback to resolve_player_mean if no logs or stat not handled
        if blended_mean is not None and blended_mean > 0:
            estimated_mean = blended_mean
            mean_source = "BLENDED"
            confidence_flag = "OK"
            data_source = "blended"
        else:
            if hasattr(provider, "resolve_player_mean"):
                resolved = provider.resolve_player_mean(
                    player_name=player_name,
                    stat=str(stat_key),
                    team_abbr=team_abbr,
                    line=float(line),
                )
                raw_mean = resolved.get("mean", line)
                if isinstance(raw_mean, (int, float)):
                    estimated_mean = float(raw_mean)
                elif isinstance(raw_mean, str):
                    try:
                        estimated_mean = float(raw_mean)
                    except ValueError:
                        estimated_mean = float(line)
                else:
                    estimated_mean = float(line)
                mean_source = str(resolved.get("mean_source", "FALLBACK"))
                confidence_flag = str(resolved.get("confidence_flag", "UNVERIFIED"))
            else:
                # Back-compat fallback (should be rare)
                real_mean = provider.get_player_mean(player_name, str(stat_key), team_abbr)
                if real_mean and real_mean > 0:
                    estimated_mean = float(real_mean)
                    mean_source = "ESPN"
                    confidence_flag = "OK"
            if estimated_mean is not None and estimated_mean > 0 and mean_source != "FALLBACK":
                data_source = "espn_api" if mean_source == "ESPN" else "manual"
    except Exception:
        # Use fallback below
        pass

    # Fallback mean is NEUTRAL (v2.0): lambda = line
    # Add combo stat fallback: sum components if available
    _combo_keys = ("pts+ast", "pts+reb", "pts+reb+ast", "pra",
                   "points+assists", "points+rebounds", "points+rebounds+assists",
                   "points_assists", "points_rebounds", "rebounds_assists",
                   "reb+ast", "rebounds+assists")
    if (estimated_mean is None or estimated_mean <= 0 or (stat_key in _combo_keys and estimated_mean == float(line))):
        # Try to sum components from player stats if available
        try:
            from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
            provider = CBBDataProvider()
            player_stats = provider.cache.get_player_stats(player_name, team_abbr)
            if player_stats and isinstance(player_stats, dict):
                pts = player_stats.get("points")
                ast = player_stats.get("assists")
                reb = player_stats.get("rebounds")
                if stat_key in ("points_assists", "pts+ast"):
                    if pts is not None and ast is not None:
                        estimated_mean = pts + ast
                        mean_source = "SUM_COMPONENTS"
                        confidence_flag = "OK"
                        data_source = "combo_fallback"
                elif stat_key in ("points_rebounds", "pts+reb"):
                    if pts is not None and reb is not None:
                        estimated_mean = pts + reb
                        mean_source = "SUM_COMPONENTS"
                        confidence_flag = "OK"
                        data_source = "combo_fallback"
                elif stat_key in ("rebounds_assists", "reb+ast"):
                    if reb is not None and ast is not None:
                        estimated_mean = reb + ast
                        mean_source = "SUM_COMPONENTS"
                        confidence_flag = "OK"
                        data_source = "combo_fallback"
                elif stat_key in ("pra", "pts+reb+ast"):
                    if pts is not None and reb is not None and ast is not None:
                        estimated_mean = pts + reb + ast
                        mean_source = "SUM_COMPONENTS"
                        confidence_flag = "OK"
                        data_source = "combo_fallback"
        except Exception:
            pass
    if estimated_mean is None or estimated_mean <= 0 or mean_source == "FALLBACK":
        # v2.2: SMART FALLBACK — Instead of mean=line (coin flip),
        # apply a small directional offset to create SOME edge.
        # This avoids the massive coin-flip rejection rate.
        # Offset is conservative: 5-8% of line value.
        fallback_offset = float(line) * 0.06  # 6% offset
        if direction == "higher":
            estimated_mean = float(line) + fallback_offset  # Slight over projection
        else:
            estimated_mean = float(line) - fallback_offset  # Slight under projection
        estimated_mean = max(estimated_mean, 0.1)  # Floor at 0.1
        mean_source = "DIRECTIONAL_FALLBACK"
        confidence_flag = "UNVERIFIED"
        data_source = "fallback"
    
    # Adjust by stat type (some stats are more predictable)
    stat_adjustments = {
        "points": 1.0,      # Most predictable
        "rebounds": 0.98,   # Slightly less predictable
        "assists": 0.95,    # Context-dependent
        "3pm": 0.90,        # High variance
        "pra": 1.0,         # Combo smooths variance
        "pts+reb": 1.0,
        "pts+ast": 0.98,
        "reb+ast": 0.95,
    }
    adj = stat_adjustments.get(stat, 0.95)
    
    # Extract spread/total context for game script adjustments
    spread = prop.get("spread")
    total = prop.get("total")
    
    # Get CBB-specific sigma for this stat (overdispersion correction)
    cbb_sigma = get_cbb_sigma(stat, estimated_mean)
    
    # v3.0: DISTRIBUTION-AWARE SIGMA — Use actual game-log variance when available
    # Instead of relying solely on CBB_SIGMA_TABLE, detect real dispersion from data.
    # Overdispersed stats get wider sigma → lower confidence (correct behavior).
    distribution_info = None
    if _raw_game_logs and len(_raw_game_logs) >= 5:
        try:
            from sports.cbb.cbb_distribution import get_distribution_for_player
            import math as _dmath
            
            # Extract stat values from game logs
            _gl_stat_map = {
                "points": "points", "pts": "points",
                "rebounds": "rebounds", "reb": "rebounds",
                "assists": "assists", "ast": "assists",
                "3pm": "three_pointers", "threes": "three_pointers",
                "steals": "steals", "stl": "steals",
                "blocks": "blocks", "blk": "blocks",
                "turnovers": "turnovers", "to": "turnovers",
            }
            _gl_combo = {
                "pra": ["points", "rebounds", "assists"],
                "pts+reb+ast": ["points", "rebounds", "assists"],
                "points+rebounds+assists": ["points", "rebounds", "assists"],
                "pts+reb": ["points", "rebounds"],
                "points+rebounds": ["points", "rebounds"],
                "pts+ast": ["points", "assists"],
                "points+assists": ["points", "assists"],
                "reb+ast": ["rebounds", "assists"],
                "rebounds+assists": ["rebounds", "assists"],
            }
            
            game_values = []
            stat_l = stat.lower()
            if stat_l in _gl_combo:
                for g in _raw_game_logs:
                    vals = [g.get(c, 0) or 0 for c in _gl_combo[stat_l]]
                    game_values.append(float(sum(vals)))
            elif stat_l in _gl_stat_map:
                key = _gl_stat_map[stat_l]
                for g in _raw_game_logs:
                    v = g.get(key)
                    if v is not None:
                        game_values.append(float(v))
            
            if len(game_values) >= 5:
                distribution_info = get_distribution_for_player(stat_l, game_values)
                actual_var = distribution_info.get("variance", 0)
                if actual_var > 0 and distribution_info["confidence"] in ("HIGH", "MEDIUM"):
                    actual_sigma = _dmath.sqrt(actual_var)
                    sigma_floor = _dmath.sqrt(max(estimated_mean, 1.0))
                    cbb_sigma = max(actual_sigma, sigma_floor)
        except Exception:
            pass  # Fall through to table sigma
    
    # v2.2: HYBRID PROBABILITY ROUTER — Selects best model per prop
    # NegBin for count stats, Normal CDF for combos, empirical blend when possible
    prob, model_selected = hybrid_probability_router(
        mean=estimated_mean, sigma=cbb_sigma, line=line, direction=direction,
        stat=stat, game_logs=_raw_game_logs, sample_n=0
    )
    
    # LOW-LINE OVERCONFIDENCE CAP
    # Poisson/NegBin on very low lines (< 3.0) can produce wildly overconfident
    # probabilities. Apply graduated caps based on line level.
    low_line_cap = 1.0  # No cap by default
    if line < 1.0:
        low_line_cap = 0.60  # Ultra-low lines: cap at 60%
    elif line < 2.0:
        low_line_cap = 0.65  # Very low lines: cap at 65%
    elif line < 3.0:
        low_line_cap = 0.70  # Low lines: cap at 70%
    elif line < 5.0:
        low_line_cap = 0.75  # Moderate-low lines: cap at 75%
    
    # Apply CBB confidence cap (stricter than NBA - no SLAM)
    CBB_MAX_CONFIDENCE = 0.79  # Max for CBB (no SLAM tier)
    
    stat_caps = {
        "points": 0.75, "pts": 0.75,
        "rebounds": 0.72, "reb": 0.72,
        "assists": 0.70, "ast": 0.70,
        "3pm": 0.65,
        "pra": 0.75,
        "pts+reb": 0.73, "pr": 0.73,
        "pts+ast": 0.72, "pa": 0.72,
        "reb+ast": 0.70, "ra": 0.70,
        "blk": 0.68, "stl": 0.68, "to": 0.68,
        "blk+stl": 0.68, "blocks": 0.68, "steals": 0.68, "turnovers": 0.68,
    }
    stat_cap = stat_caps.get(stat, 0.72)  # Default raised from 0.68 — unknown stats get 72% cap
    
    adjusted_prob = prob * adj
    
    # ========================================================================
    # GAME SCRIPT PENALTIES (v3.1 — Spread/Total Integration)
    # ========================================================================
    # Blowouts favor unders (starters sit), close games favor volume.
    # High pace games boost scoring props, low pace suppresses them.
    game_script_adj = 1.0
    game_script_reason = None
    
    if spread is not None and abs(spread) >= 15:
        # Blowout territory: ≥15 point spread
        if direction == "higher":
            game_script_adj *= 0.95  # Overs suppressed (starters sit early)
            game_script_reason = "blowout_over"
        else:
            game_script_adj *= 1.03  # Unders boosted
            game_script_reason = "blowout_under"
    
    if total is not None and stat in ["points", "pts", "pra", "pts+reb", "pts+ast", "pts+reb+ast"]:
        # Pace adjustment for scoring stats
        avg_cbb_total = 140.0  # Average CBB total
        pace_factor = total / avg_cbb_total
        
        if pace_factor > 1.15:
            # High-pace game (total >161): more possessions = more scoring
            if stat in ["points", "pts"]:
                game_script_adj *= 1.05
                game_script_reason = f"high_pace_{pace_factor:.2f}" if not game_script_reason else game_script_reason
        elif pace_factor < 0.85:
            # Low-pace game (total <119): fewer possessions = less scoring
            if stat in ["points", "pts"]:
                game_script_adj *= 0.95
                game_script_reason = f"low_pace_{pace_factor:.2f}" if not game_script_reason else game_script_reason
    
    # Apply game script adjustment
    adjusted_prob *= game_script_adj
    
    # Cap the adjusted probability
    capped_prob = min(adjusted_prob, stat_cap, CBB_MAX_CONFIDENCE, low_line_cap)

    # v2.0: NO PROBABILITY FLOOR
    signal_flag = "WEAK_SIGNAL" if capped_prob < 0.50 else "OK"

    cap_hit = None
    if adjusted_prob > min(stat_cap, CBB_MAX_CONFIDENCE, low_line_cap):
        if low_line_cap < min(stat_cap, CBB_MAX_CONFIDENCE):
            cap_hit = "low_line_cap"
        elif stat_cap <= CBB_MAX_CONFIDENCE:
            cap_hit = "stat_cap"
        else:
            cap_hit = "global_cap"

    decision_trace = {
        "mean": {
            "lambda": round(float(estimated_mean), 4),
            "mean_source": mean_source,
            "confidence_flag": confidence_flag,
        },
        "model": {
            "type": model_selected,
            "sigma": round(float(cbb_sigma), 2),
            "raw_prob": round(float(prob), 6),
            "direction": direction,
            "line": float(line),
        },
        "distribution": {
            "type": distribution_info["distribution_type"] if distribution_info else "TABLE_FALLBACK",
            "dispersion_ratio": round(distribution_info["dispersion_ratio"], 3) if distribution_info else None,
            "confidence": distribution_info["confidence"] if distribution_info else "LOW",
            "sample_size": distribution_info["sample_size"] if distribution_info else 0,
            "actual_variance": round(distribution_info["variance"], 2) if distribution_info else None,
        },
        "adjustment": {
            "multiplier": round(float(adj), 4),
            "adjusted_prob": round(float(adjusted_prob), 6),
        },
        "game_script": {
            "spread": spread,
            "total": total,
            "adjustment": round(float(game_script_adj), 4),
            "reason": game_script_reason,
        },
        "caps": {
            "stat_cap": float(stat_cap),
            "global_cap": float(CBB_MAX_CONFIDENCE),
            "low_line_cap": float(low_line_cap),
            "cap_hit": cap_hit,
        },
        "final": {
            "final_prob": round(float(capped_prob), 6),
            "signal_flag": signal_flag,
        },
    }
    
    return {
        "probability": round(capped_prob, 4),
        "player_mean": round(estimated_mean, 2),
        "projected_sigma": round(cbb_sigma, 2),
        "raw_prob": round(prob, 4),
        "adjusted_prob": round(adjusted_prob, 4),
        "model": f"{model_selected}_{data_source}",
        "data_source": data_source,
        "mean_source": mean_source,
        "confidence_flag": confidence_flag,
        "signal_flag": signal_flag,
        "capped": adjusted_prob > min(stat_cap, CBB_MAX_CONFIDENCE, low_line_cap),
        "spread": spread,
        "total": total,
        "matchup": prop.get("matchup"),
        "decision_trace": decision_trace,
    }


def poisson_probability(mean: float, line: float, direction: str) -> float:
    """
    Compute probability using Poisson distribution.
    
    P(X > line) for "higher"
    P(X < line) for "lower"
    
    NOTE: For CBB, prefer negbin_probability() which handles overdispersion.
    This is kept as a fallback when variance ≈ mean.
    """
    import math
    
    if mean <= 0:
        return 0.5
    
    def poisson_pmf(lam: float, k: int) -> float:
        """Poisson probability mass function."""
        if k < 0 or lam <= 0:
            return 0.0
        try:
            return math.exp(-lam) * (lam ** k) / math.factorial(k)
        except (OverflowError, ValueError):
            return 0.0
    
    def poisson_cdf(lam: float, k: int) -> float:
        """Cumulative distribution function P(X <= k)."""
        if k < 0:
            return 0.0
        total = sum(poisson_pmf(lam, i) for i in range(k + 1))
        return min(1.0, total)
    
    if direction == "higher":
        # P(X > line) = 1 - P(X <= floor(line))
        target = int(math.floor(line))
        prob = 1 - poisson_cdf(mean, target)
    else:
        # P(X < line) = P(X <= ceil(line) - 1)
        target = int(math.ceil(line)) - 1
        prob = poisson_cdf(mean, target)
    
    return max(0.0, min(1.0, prob))


# =============================================================================
# NORMAL CDF PROBABILITY — For high-mean stats (PRA, combos with mean > 15)
# =============================================================================

def normal_cdf_probability(mean: float, sigma: float, line: float, direction: str) -> float:
    """
    Compute probability using Normal CDF approximation.
    
    Best for high-mean stats where discrete distributions converge to Normal.
    Applies 0.5 continuity correction for integer outcomes.
    
    Used by the hybrid router for combo stats and high-scoring lines.
    """
    import math
    
    if sigma <= 0 or mean <= 0:
        return 0.5
    
    # Continuity correction
    if direction.lower() in ("higher", "over"):
        adjusted_line = line + 0.5
        z = (adjusted_line - mean) / sigma
        # P(X > line) = 1 - Phi(z)
        prob = 0.5 * (1 - math.erf(z / math.sqrt(2)))
    else:
        adjusted_line = line - 0.5
        z = (adjusted_line - mean) / sigma
        # P(X < line) = Phi(z)
        prob = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    
    return max(0.0, min(1.0, prob))


def empirical_probability(game_logs: list, stat: str, line: float, direction: str) -> float:
    """
    Compute probability from actual game log data (hit rate).
    
    This is the most accurate method when we have sufficient data (n≥10).
    Simply counts how many games the player cleared/missed the line.
    """
    if not game_logs or len(game_logs) < 5:
        return None  # Not enough data
    
    stat_map = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "3pm": "three_pointers",
        "steals": "steals",
        "blocks": "blocks",
        "turnovers": "turnovers",
    }
    stat_key = stat_map.get(stat.lower(), stat.lower())
    
    hits = 0
    total = 0
    for game in game_logs:
        val = game.get(stat_key)
        if val is None:
            continue
        total += 1
        if direction.lower() in ("higher", "over"):
            if val > line:
                hits += 1
        else:
            if val < line:
                hits += 1
    
    if total < 5:
        return None
    
    return hits / total


def hybrid_probability_router(
    mean: float, sigma: float, line: float, direction: str,
    stat: str, game_logs: list = None, sample_n: int = 0
) -> tuple:
    """
    Hybrid Auto-Router — Selects the best probability model for each prop.
    
    Borrowed from NBA pipeline's proven approach, adapted for CBB.
    
    Decision Logic:
    1. If we have ≥10 game logs → blend empirical (60%) + model (40%)
    2. If mean > 15 (combo stats) → Normal CDF (converges well)
    3. If variance > mean → Negative Binomial (overdispersed counts)
    4. Otherwise → Poisson (clean count data)
    
    Returns: (probability, model_name)
    """
    import math
    
    variance = sigma ** 2
    model_name = "poisson"
    
    # Determine model-based probability
    if mean > 15 and stat.lower() in ("pra", "pts+reb", "pts+ast", "pts+reb+ast", "reb+ast"):
        # High-mean combos → Normal CDF is more stable
        model_prob = normal_cdf_probability(mean, sigma, line, direction)
        model_name = "normal_cdf"
    elif variance > mean:
        # Overdispersion → Negative Binomial
        model_prob = negbin_probability(mean, sigma, line, direction)
        model_name = "negbin"
    else:
        # Default → Poisson
        model_prob = poisson_probability(mean, line, direction)
        model_name = "poisson"
    
    # If we have sufficient game logs, blend with empirical
    if game_logs and len(game_logs) >= 10:
        emp_prob = empirical_probability(game_logs, stat, line, direction)
        if emp_prob is not None:
            # Blend: 60% empirical (real data) + 40% model
            blended = 0.6 * emp_prob + 0.4 * model_prob
            return (blended, f"hybrid_emp60_{model_name}40")
    elif game_logs and len(game_logs) >= 5:
        emp_prob = empirical_probability(game_logs, stat, line, direction)
        if emp_prob is not None:
            # Less data → more weight on model: 40% empirical + 60% model
            blended = 0.4 * emp_prob + 0.6 * model_prob
            return (blended, f"hybrid_emp40_{model_name}60")
    
    return (model_prob, model_name)


# =============================================================================
# CBB SIGMA TABLE — Stat-specific standard deviations for college basketball
# =============================================================================
# CBB variance is significantly higher than NBA due to:
#   - Shorter seasons (less mean reversion)
#   - Larger skill gaps between opponents
#   - More rotation variance (foul trouble, blowout benching)
#   - Fewer possessions (30-sec shot clock vs NBA 24-sec)
#
# These are empirical estimates from college basketball distributions.
# Used by the Negative Binomial model for overdispersion correction.

CBB_SIGMA_TABLE = {
    "points":       6.5,    # College scorers are highly variable
    "rebounds":     3.2,    # Board variance is moderate
    "assists":      2.5,    # Playmaking is context-dependent
    "3pm":          1.5,    # Three-pointers are inherently noisy
    "steals":       1.0,    # Low-count stat, high relative variance
    "blocks":       1.2,    # Low-count stat
    "turnovers":    1.5,    # Moderately variable
    "pra":          8.5,    # Sum of PTS+REB+AST → higher σ
    "pts+reb":      7.5,    # Sum of two high-variance components
    "pts+ast":      7.0,    # Sum of two components
    "reb+ast":      4.0,    # Sum of two lower-variance components
    "pts+reb+ast":  8.5,    # Same as PRA
    "blks+stls":    1.5,    # Sum of two low-count stats
}

# Minimum sigma floor: never let sigma drop below sqrt(mean)
# This prevents overconfidence when we have limited data
CBB_SIGMA_FLOOR_MULTIPLIER = 1.0  # sigma >= sqrt(mean) * multiplier


def get_cbb_sigma(stat: str, mean: float) -> float:
    """
    Get the appropriate sigma for a CBB stat type.
    
    Uses the sigma table with a floor of sqrt(mean) to prevent
    the model from being overconfident on any stat.
    """
    import math
    table_sigma = CBB_SIGMA_TABLE.get(stat.lower(), 4.0)  # Default 4.0 for unknown stats
    floor_sigma = math.sqrt(max(mean, 1.0)) * CBB_SIGMA_FLOOR_MULTIPLIER
    return max(table_sigma, floor_sigma)


def negbin_probability(mean: float, sigma: float, line: float, direction: str) -> float:
    """
    Compute probability using Negative Binomial distribution.
    
    Unlike Poisson (variance = mean), NegBin allows variance > mean (overdispersion).
    This is CRITICAL for CBB where game-to-game variance is much higher than 
    Poisson assumes, especially for points and combo stats.
    
    Parameters:
        mean: Expected value (lambda/mu)
        sigma: Standard deviation (from CBB_SIGMA_TABLE)
        line: The prop line
        direction: "higher" or "lower"
    
    Returns:
        Probability between 0.0 and 1.0
    """
    import math
    
    if mean <= 0:
        return 0.5
    
    variance = sigma ** 2
    
    # If variance <= mean, fall back to Poisson (no overdispersion)
    if variance <= mean:
        return poisson_probability(mean, line, direction)
    
    # NegBin parameters: r (dispersion) and p (success probability)
    # variance = mean + mean²/r  →  r = mean² / (variance - mean)
    r = mean ** 2 / (variance - mean)
    p = r / (r + mean)  # probability of success per trial
    
    def negbin_pmf(k: int) -> float:
        """Negative Binomial PMF using log-gamma for numerical stability."""
        if k < 0:
            return 0.0
        try:
            log_pmf = (math.lgamma(k + r) - math.lgamma(k + 1) - math.lgamma(r)
                       + r * math.log(p) + k * math.log(1 - p))
            return math.exp(log_pmf)
        except (OverflowError, ValueError):
            return 0.0
    
    def negbin_cdf(k: int) -> float:
        """Cumulative distribution function P(X <= k)."""
        if k < 0:
            return 0.0
        # Sum up to k, with safety limit for very high lines
        max_k = min(k, int(mean * 5) + 100)
        total = sum(negbin_pmf(i) for i in range(max_k + 1))
        return min(1.0, total)
    
    if direction == "higher":
        target = int(math.floor(line))
        prob = 1 - negbin_cdf(target)
    else:
        target = int(math.ceil(line)) - 1
        prob = negbin_cdf(target)
    
    return max(0.0, min(1.0, prob))


def apply_cbb_gates(edges: List[Dict]) -> List[Dict]:
    """
    Apply CBB hard gates:
    0. direction_gate (FUOOM FIX 2026-02-15: >65% same direction → ABORT)
    1. roster_gate (player on active roster)
    2. min_mpg_gate (≥20 mpg)
    3. games_played_gate (≥5 games)
    4. blowout_gate (>25% spread = skip overs)
    """
    print("\n[3/5] APPLY GATES")
    print("-" * 40)
    
    # DEBUG: Check edges before gate
    print(f"  [DEBUG] Edges before direction gate: {len(edges)}")
    if edges:
        sample = edges[0]
        print(f"  [DEBUG] Sample edge keys: {list(sample.keys())}")
        print(f"  [DEBUG] Sample direction: {sample.get('direction', 'MISSING')}")
    
    # ═══════════════════════════════════════════════════════════
    # DIRECTION GATE v2.0 — GRADUATED FILTER (SMART GATE)
    # Replaces binary abort with confidence compression
    # Preserves individual edges, penalizes skew, protects counter-direction picks
    # ═══════════════════════════════════════════════════════════
    from sports.cbb.direction_gate_v2 import apply_direction_gate_v2
    import logging
    
    print(f"  [DEBUG] Calling apply_direction_gate_v2() — graduated filter...")
    edges, gate_report = apply_direction_gate_v2(edges, context={})
    
    # Display gate results
    print(f"\n  {'='*60}")
    print(f"  DIRECTION GATE v2.0: {gate_report['status']}")
    print(f"  {'='*60}")
    print(f"  Skew:       {gate_report['skew']:.1%} {gate_report.get('majority_direction', 'N/A')}")
    print(f"             ({gate_report.get('over_count', 0)} OVER / {gate_report.get('under_count', 0)} UNDER)")
    print(f"  Action:     {gate_report['action']}")
    print(f"  Surviving:  {gate_report.get('surviving', len(edges))} of {gate_report.get('total', 0)} edges")
    
    if gate_report['status'] == 'WARNING':
        print(f"  Compressed: {gate_report.get('compressed', 0)} majority picks (-5% confidence)")
        if gate_report.get('killed_by_compression', 0) > 0:
            print(f"  Killed:     {gate_report.get('killed_by_compression', 0)} (fell below 55% floor)")
    elif gate_report['status'] == 'HARD_FILTER':
        print(f"  Killed:     {gate_report.get('killed', 0)} majority LEAN picks")
        print(f"  Survivors:  {gate_report.get('high_conf_survivors', 0)} high-confidence + all counter-direction")
    
    print(f"  {'='*60}\n")
    
    if not edges:
        logging.critical("⛔ Direction gate v2 filtered all picks — no survivors")
        print("  ⛔ No picks survived graduated filter")
        print("  This likely means genuine model miscalibration\n")
        return []  # ABORT — propagate empty list to caller
    
    print(f"  ✓ Direction Gate v2 COMPLETE: {len(edges)} picks proceeding to scoring")
    print("-" * 40)
    
    passed = []
    failed = []
    
    try:
        from sports.cbb.gates.edge_gates import get_gates
        gates = get_gates()
        
        # Fetch today's games ONCE (outside loop) to avoid 135+ ESPN calls
        todays_games = []
        if not _cbb_offline_mode():
            try:
                from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
                provider = CBBDataProvider()
                todays_games = provider.get_todays_games()
                print(f"  [ESPN] Loaded {len(todays_games)} games for spread lookup")
            except Exception as e:
                print(f"  [ESPN] Could not fetch today's games: {e}")
                print(f"  [ESPN] Continuing without spread data (spread_status=MISSING)")
        
        # ─── PRE-PASS: Enrich opponent from ESPN schedule ───────────────
        # Underdog paste rarely includes matchup info → edges have opponent="UNK".
        # Match each edge's team abbreviation to the ESPN scoreboard to set the
        # real opponent, spread, and total BEFORE gates run.
        _abbr_to_game = {}  # team_abbr → CBBGame
        for game in todays_games:
            if game.home_abbr:
                _abbr_to_game[game.home_abbr.upper()] = game
            if game.away_abbr:
                _abbr_to_game[game.away_abbr.upper()] = game

        _enriched = 0
        for edge in edges:
            _team_upper = (edge.get("team") or "").upper()
            _matched_game = _abbr_to_game.get(_team_upper)
            if _matched_game:
                # Set real opponent (the OTHER team in the game)
                if _matched_game.home_abbr.upper() == _team_upper:
                    edge["opponent"] = _matched_game.away_abbr
                    edge["opponent_full"] = _matched_game.away_team
                else:
                    edge["opponent"] = _matched_game.home_abbr
                    edge["opponent_full"] = _matched_game.home_team
                _enriched += 1
        if _enriched:
            print(f"  [ENRICH] Backfilled opponent for {_enriched}/{len(edges)} edges from ESPN")
        # ──────────────────────────────────────────────────────────────────

        for edge in edges:
            # Get game context for blowout gate
            game_context = None
            spread_status = "MISSING"
            
            # Match edge to today's game for spread
            # FIX: Compare against abbreviations (home_abbr/away_abbr), NOT full
            # display names, because edge["team"] is always an abbreviation.
            for game in todays_games:
                if (edge.get("team", "").upper() in [game.home_abbr.upper(), game.away_abbr.upper()] or
                    edge.get("opponent", "").upper() in [game.home_abbr.upper(), game.away_abbr.upper()]):
                    spread_status = "FOUND"
                    
                    # v3.0: Determine if player's team is favorite (for game script gate)
                    # game.spread is HOME team spread: negative = home favored
                    player_team = edge.get("team", "")
                    is_home = player_team.upper() in (game.home_team.upper(), game.home_abbr.upper())
                    if game.spread is not None:
                        is_favorite = (is_home and game.spread <= 0) or (not is_home and game.spread > 0)
                        team_spread = abs(game.spread)
                    else:
                        is_favorite = True
                        team_spread = 0
                    
                    game_context = {
                        "spread": team_spread,
                        "total": game.total if game.total else None,
                        "is_favorite": is_favorite,
                        "is_home": is_home,
                        "raw_spread": game.spread,
                    }
                    break

            edge["spread_status"] = spread_status
            
            # Run gates
            all_passed, passed_gates, failed_gates = gates.check_all_gates(edge, game_context)
            
            edge["gates_passed"] = passed_gates
            edge["gates_failed"] = failed_gates
            edge["gates_all_passed"] = all_passed

            # =================================================================
            # v3.0: GAME SCRIPT GATE — Config-driven (gates/game_script_gate.py)
            # Reads thresholds from gate_thresholds.yaml + cbb_runtime.json.
            # When a team is trailing, their best players' stats inflate.
            # UNDER picks on those players are structurally -EV.
            # =================================================================
            if game_context and game_context.get("spread") is not None and all_passed:
                try:
                    from sports.cbb.gates.game_script_gate import (
                        game_script_gate as run_game_script_gate,
                        apply_spread_lambda_adjustment,
                        calculate_game_script_penalty,
                    )

                    gs_spread = game_context.get("spread", 0)
                    gs_is_fav = game_context.get("is_favorite", True)
                    player_usage = edge.get("player_usage", 0.20)

                    # --- Run the gate ---
                    gs_passed, gs_reason = run_game_script_gate(
                        edge=edge,
                        game_context=game_context,
                        player_data={"usage_rate": player_usage},
                    )

                    # --- Calculate soft penalty for non-blocked edges ---
                    gs_penalty = calculate_game_script_penalty(
                        spread=gs_spread,
                        is_favorite=gs_is_fav,
                        stat_type=edge.get("stat", ""),
                        player_usage=player_usage,
                    )

                    edge["game_script_gate"] = {
                        "passed": gs_passed,
                        "reason": gs_reason,
                        "penalty_factor": gs_penalty,
                        "spread": gs_spread,
                        "is_favorite": gs_is_fav,
                    }
                    
                    if not gs_passed:
                        # HARD BLOCK — mark as failed
                        all_passed = False
                        failed_gates.append(f"game_script")
                        edge["gates_failed"] = failed_gates
                        edge["gates_all_passed"] = False
                        edge["game_script_block"] = gs_reason
                        print(f"    [GAME SCRIPT] BLOCKED: {edge.get('player', '?')} "
                              f"{edge.get('stat', '?')} {edge.get('direction', '?')} — {gs_reason}")
                    elif gs_penalty > 1.0:
                        # SOFT PENALTY — inflate lambda, recalculate probability
                        old_prob = edge.get("probability", 0.0)
                        old_lambda = edge.get("player_mean", float(edge.get("line", 0)))

                        # Also apply spread-based lambda adjustment
                        adj_lambda, adj_factor = apply_spread_lambda_adjustment(
                            raw_lambda=old_lambda,
                            game_context=game_context,
                            direction=edge.get("direction", "higher"),
                        )

                        new_lambda = adj_lambda * gs_penalty
                        new_sigma = edge.get("projected_sigma", get_cbb_sigma(edge.get("stat", ""), new_lambda))
                        
                        # Recalculate with inflated lambda
                        new_prob, _ = hybrid_probability_router(
                            mean=new_lambda,
                            sigma=new_sigma,
                            line=float(edge["line"]),
                            direction=edge["direction"],
                            stat=edge.get("stat", ""),
                            game_logs=None,
                            sample_n=0,
                        )
                        
                        # Re-apply caps
                        _gs_stat_caps = {
                            "points": 0.75, "pts": 0.75,
                            "rebounds": 0.72, "reb": 0.72,
                            "assists": 0.70, "ast": 0.70,
                            "3pm": 0.65, "pra": 0.75,
                            "pts+reb": 0.73, "pr": 0.73,
                            "pts+ast": 0.72, "pa": 0.72,
                            "reb+ast": 0.70, "ra": 0.70,
                        }
                        _gs_cap = _gs_stat_caps.get(edge.get("stat", "").lower(), 0.72)
                        new_prob = min(new_prob, 0.79, _gs_cap)
                        
                        edge["probability"] = round(new_prob, 4)
                        edge["game_script_adjustment"] = {
                            "old_probability": round(old_prob, 4),
                            "new_probability": round(new_prob, 4),
                            "old_lambda": round(old_lambda, 2),
                            "new_lambda": round(new_lambda, 2),
                            "penalty_factor": gs_penalty,
                            "spread_lambda_factor": adj_factor,
                            "reason": gs_reason,
                        }
                        print(f"    [GAME SCRIPT] ADJUSTED: {edge.get('player', '?')} "
                              f"{edge.get('stat', '?')} {edge.get('direction', '?')} "
                              f"prob {old_prob:.3f} → {new_prob:.3f} (λ ×{gs_penalty:.2f}, spread ×{adj_factor:.2f})")
                except Exception as e:
                    pass  # Fail open — don't crash pipeline for game script gate

            # v2.2: Spread status does NOT affect player prop confidence.
            # Spread only matters for team totals / game-level bets.
            # Previously this set UNVERIFIED on all HIGHER props when spread was
            # missing, which incorrectly penalized 3PM/REB/AST OVER edges.
            # Removed: spread_status != "FOUND" → UNVERIFIED downgrade.

            # v2.0: NO_DATA is risk, not silent
            gate_status = edge.get("gate_status", []) or []
            has_core_no_data = any(
                (gs.get("status") == "NO_DATA") and (gs.get("gate") in ("minutes", "games"))
                for gs in gate_status
            )
            if has_core_no_data:
                edge["confidence_flag"] = "NO_DATA"
            
            if all_passed:
                passed.append(edge)
            else:
                # Still include but mark as gated
                edge["tier"] = "SKIP"
                edge["skip_reason"] = f"GATE_FAIL: {', '.join(failed_gates)}"
                failed.append(edge)
        
        print(f"  Passed: {len(passed)}, Failed: {len(failed)}")
        
        # Return all (passed first, then failed for transparency)
        return passed + failed
        
    except ImportError as e:
        print(f"  [!] Gates not available: {e}")
        print("  → Applying placeholder gates")
        
        # Fallback: pass all through with placeholder
        for edge in edges:
            edge["gates_passed"] = ["placeholder"]
            edge["gates_failed"] = []
            edge["gates_all_passed"] = True
            passed.append(edge)
        
        print(f"  Passed: {len(passed)}, Failed: {len(failed)}")
        return passed


def score_cbb_edges(edges: List[Dict], use_sdg: bool = True) -> List[Dict]:
    """
    Score edges and assign tiers.
    
    CBB Tiers (no SLAM):
    - STRONG: ≥68% (v2.1 adjusted for SDG)
    - LEAN: ≥60%
    - SKIP: <60%
    
    v2.1: SDG (Stat Deviation Gate) integration — prices variance instead of blocking.
    """
    print("\n[4/5] SCORE EDGES")
    print("-" * 40)
    
    # v2.1: Run SDG pipeline if enabled
    if use_sdg:
        try:
            from sports.cbb.gates.sdg_integration import run_full_sdg_pipeline
            from sports.cbb.config import SDG_ENABLED
            
            if SDG_ENABLED:
                print("  [SDG v2.1] Applying Stat Deviation Gate...")
                result = run_full_sdg_pipeline(edges, verbose=True)
                return _apply_calibration_cap(result)
            else:
                print("  [SDG] Disabled via config — using legacy scoring")
        except ImportError as e:
            print(f"  [SDG] Import error: {e} — using legacy scoring")
        except Exception as e:
            print(f"  [SDG] Error: {e} — using legacy scoring")
    
    # LEGACY SCORING (fallback)
    print("  [LEGACY] Using v2.0 scoring logic")
    
    scored = []
    
    for edge in edges:
        prob = edge.get("probability", 0.0)

        # Respect hard gate failures (do NOT re-tier gated edges)
        if edge.get("gates_all_passed") is False:
            edge["tier"] = "SKIP"
            scored.append(edge)
            continue
        
        # Assign tier (CBB caps - no SLAM)
        if prob >= 0.70:
            edge["tier"] = "STRONG"
        elif prob >= 0.60:
            edge["tier"] = "LEAN"
        else:
            edge["tier"] = "SKIP"

        # v2.0: FALLBACK / NO_DATA / UNVERIFIED cannot be STRONG
        if edge.get("tier") == "STRONG":
            if edge.get("mean_source") == "FALLBACK" or edge.get("confidence_flag") in ("UNVERIFIED", "NO_DATA"):
                edge["tier"] = "LEAN"
                edge["tier_cap_reason"] = f"TIER_CAPPED ({edge.get('mean_source')}/{edge.get('confidence_flag')})"
        
        scored.append(edge)
    
    # Count by tier
    tier_counts = {}
    for e in scored:
        tier = e["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    for tier, count in sorted(tier_counts.items()):
        print(f"  {tier}: {count}")
    
    return _apply_calibration_cap(scored)


def _apply_calibration_cap(edges: List[Dict]) -> List[Dict]:
    """
    v3.0 Fix 8: Cap STRONG → LEAN during calibration period.
    
    After model changes (distribution detection, game script gate),
    we need to validate predictions against real outcomes before
    trusting STRONG confidence levels again.
    
    Set CALIBRATION_MODE = False in config.py to disable after validation.
    """
    try:
        from sports.cbb.config import CALIBRATION_MODE, CALIBRATION_START_DATE, CALIBRATION_DAYS
    except ImportError:
        return edges
    
    if not CALIBRATION_MODE:
        return edges
    
    # Check if still within calibration window
    from datetime import datetime, timedelta
    try:
        start = datetime.strptime(CALIBRATION_START_DATE, "%Y-%m-%d")
        end = start + timedelta(days=CALIBRATION_DAYS)
        now = datetime.now()
        
        if now < start:
            # Calibration period hasn't started yet
            return edges
        
        if now > end:
            print(f"  [CALIBRATION] Period ended ({CALIBRATION_START_DATE} + {CALIBRATION_DAYS}d)")
            print(f"  [CALIBRATION] Set CALIBRATION_MODE = False in config.py to re-enable STRONG")
            return edges
    except Exception:
        return edges
    
    capped_count = 0
    for edge in edges:
        if edge.get("tier") == "STRONG":
            edge["tier"] = "LEAN"
            edge["tier_cap_reason"] = f"CALIBRATION_CAP (until {end.strftime('%Y-%m-%d')})"
            edge["calibration_capped"] = True
            capped_count += 1
    
    if capped_count > 0:
        days_remaining = (end - now).days
        print(f"  [CALIBRATION] Capped {capped_count} STRONG → LEAN ({days_remaining}d remaining)")
    
    return edges


def validate_cbb_output(edges: List[Dict]) -> bool:
    """
    HARD GATE validation.
    
    Checks:
    - Required fields present
    - Tier thresholds correct
    - No duplicate edge_ids
    """
    print("\n[5/5] VALIDATE — HARD GATE")
    print("-" * 40)
    
    errors = []
    
    # Required fields
    required = ["edge_id", "sport", "player", "stat", "line", "direction", "tier"]
    
    for edge in edges:
        for field in required:
            if field not in edge:
                errors.append(f"Missing {field} in {edge.get('player', 'unknown')}")
    
    # Check for duplicates
    edge_ids = [e["edge_id"] for e in edges]
    duplicates = set([x for x in edge_ids if edge_ids.count(x) > 1])
    for dup in duplicates:
        errors.append(f"Duplicate edge_id: {dup}")
    
    if errors:
        print(f"\n⛔ VALIDATION FAILED — {len(errors)} errors:")
        for err in errors[:10]:
            print(f"  • {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return False
    
    print("  [OK] All checks passed")
    return True


def render_cbb_report(edges: List[Dict]) -> str:
    """
    Render CBB analysis report with Matchup Context and Rosters.
    """
    print("\n[6/5] RENDER REPORT")
    print("-" * 40)
    
    provider = CBBDataProvider()
    if _cbb_offline_mode():
        todays_games = []
    else:
        try:
            todays_games = provider.get_todays_games()
        except Exception as e:
            print(f"  [Warning] Could not fetch today's games: {e}")
            todays_games = []

    # Filter actionable
    actionable = [e for e in edges if e["tier"] in ["STRONG", "LEAN"]]
    skipped = [e for e in edges if e["tier"] == "SKIP"]
    
    lines = [
        "",
        "=" * 65,
        "[CBB] COLLEGE BASKETBALL STRATEGIC REPORT",
        f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"   Total edges: {len(edges)} | Actionable: {len(actionable)}",
        "=" * 65,
        ""
    ]
    
    if not actionable:
        lines.append("\n  [!] NO ACTIONABLE EDGES FOUND")
        lines.append("\n" + "=" * 65)
        # Show skips anyway so user knows what happened
        if skipped:
             lines.append(f"  SKIP ({len(skipped)}) - below thresholds")
             for e in skipped[:10]:
                 # Include v2.0 tags if present
                 tags = []
                 if e.get("mean_source"):
                     tags.append(f"mean_source={e.get('mean_source')}")
                 if e.get("confidence_flag"):
                     tags.append(f"confidence={e.get('confidence_flag')}")
                 if e.get("signal_flag"):
                     tags.append(f"signal={e.get('signal_flag')}")
                 tag_str = (" | " + " ".join(tags)) if tags else ""
                 lines.append(f"  - {e['player']} {e['stat']} {e['direction']} {e['line']} ({e.get('tier','SKIP')}){tag_str}")
        
        report = '\n'.join(lines)

        # v2.0: always persist the report so user doesn't see stale latest output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = OUTPUTS_DIR / f"cbb_report_{timestamp}.txt"
        report_path.write_text(report, encoding="utf-8")
        latest_path = OUTPUTS_DIR / "cbb_report_latest.txt"
        latest_path.write_text(report, encoding="utf-8")
        print(f"  Saved to: {report_path}")

        return report

    # 1. GROUP EDGES BY GAME
    # Map team -> Game
    team_to_game = {}
    for g in todays_games:
        team_to_game[g.home_abbr] = g
        team_to_game[g.away_abbr] = g
        # Also map full names if needed? 
    
    # Group edges
    games_with_edges = {}
    
    # Bucket for edges that don't match a known game
    unknown_game_key = "UNKNOWN_MATCHUP"
    
    for edge in actionable:
        team = edge['team']
        game = team_to_game.get(team)
        
        if game:
            game_key = game.id
        else:
            game_key = f"UNKNOWN_{team}"
            
        if game_key not in games_with_edges:
            games_with_edges[game_key] = {
                "game": game,
                "edges": []
            }
        games_with_edges[game_key]["edges"].append(edge)

    # 2. RENDER EACH GAME SECTION
    matchup_engine = MatchupEngine()
    
    for g_id, data in games_with_edges.items():
        game = data["game"]
        game_edges = data["edges"]
        
        # Header
        lines.append("")
        lines.append("=" * 60)
        if game:
            lines.append(f" {game.away_abbr} @ {game.home_abbr}  [{game.time} ET]")
        else:
            # Fallback if game not matched
            teams = sorted(list(set(e['team'] for e in game_edges)))
            lines.append(f" {' / '.join(teams)}")
        lines.append("=" * 60)
        
        # Game Context (spread / total / blowout / implied totals)
        if game and (game.spread or game.total):
            try:
                from core.game_context import GameContext, format_game_context_section
                # Determine which team is "ours" — pick from first edge
                _pt = game_edges[0].get("team", game.home_abbr)
                _is_home = _pt in (game.home_team, game.home_abbr)
                _opp = game.away_abbr if _is_home else game.home_abbr
                _gc = GameContext(
                    spread=game.spread,
                    total=game.total if game.total else None,
                    player_team=_pt,
                    opponent=_opp,
                    is_home=_is_home,
                    sport="CBB",
                )
                gc_lines = format_game_context_section(_gc, edges=game_edges)
                for gl in gc_lines:
                    lines.append(gl)
            except Exception:
                pass  # Fail open

        # Context
        if game:
            context_notes = matchup_engine.analyze_matchup(game)
            lines.append("[MATCHUP ANALYSIS]")
            for note in context_notes:
                # ASCII-only bullet to avoid Windows console mojibake.
                lines.append(f"  - {note}")
            lines.append("")

        # Roster Keys (Teams involved in edges)
        teams_in_game = sorted(list(set([e['team'] for e in game_edges])))
        for t_abbr in teams_in_game:
            # Generate mini roster table
            roster_lines = generate_roster_table(t_abbr, provider, active_edges=actionable)
            for rl in roster_lines:
                lines.append(f"  {rl}")
            lines.append("")

        # Edges
        lines.append("[EDGES]")
        from ai_commentary import generate_pick_commentary
        from add_quick_analysis import generate_analysis
        from add_deepseek_analysis import call_deepseek, generate_analysis_prompt
        for e in game_edges:
            prob = e.get("probability", 0)
            star = "*" if e['tier'] == "STRONG" else " "
            line_str = f"  {star} {e['player']:<18} {e['stat']:<10} {e['direction']} {e['line']:<5} ({e['tier']})"
            lines.append(line_str)
            model_str = f"Probability: {prob:.1%}"
            ms = e.get("mean_source")
            cf = e.get("confidence_flag")
            sf = e.get("signal_flag")
            ss = e.get("spread_status")
            if ms or cf or sf or ss:
                model_str += f" | mean_source={ms} | confidence={cf} | signal={sf} | spread={ss}"
            if e.get("dedupe_dropped"):
                dd = e["dedupe_dropped"]
                model_str += f" | dedupe_dropped={dd.get('direction')}@{dd.get('probability'):.3f}"
            if e.get("notes"):
                 model_str += f" | {e['notes']}"
            lines.append(f"      {model_str}")

            # v3.1: Game Context impact annotation
            gs_gate = e.get("game_script_gate", {})
            gs_adj = e.get("game_script_adjustment", {})
            if gs_gate or gs_adj:
                gs_parts = []
                gs_sp = gs_gate.get("spread")
                if gs_sp is not None:
                    side = "FAV" if gs_gate.get("is_favorite") else "DOG"
                    gs_parts.append(f"{side} {gs_sp:.1f}")
                if not gs_gate.get("passed", True):
                    gs_parts.append("BLOCKED by game script")
                elif gs_adj:
                    old_p = gs_adj.get("old_probability", 0)
                    new_p = gs_adj.get("new_probability", 0)
                    gs_parts.append(f"adj {old_p:.1%}->{new_p:.1%}")
                    lam_f = gs_adj.get("spread_lambda_factor", 1.0)
                    pen_f = gs_adj.get("penalty_factor", 1.0)
                    if lam_f != 1.0 or pen_f != 1.0:
                        gs_parts.append(f"lam x{lam_f:.2f} pen x{pen_f:.2f}")
                if gs_parts:
                    lines.append(f"      [GAME SCRIPT] {' | '.join(gs_parts)}")

            # v2.0: Decision Trace (first-class)
            dt = e.get("decision_trace") or {}
            if dt:
                mean_dt = dt.get("mean", {})
                adj_dt = dt.get("adjustment", {})
                caps_dt = dt.get("caps", {})
                fin_dt = dt.get("final", {})
                lines.append(
                    f"      TRACE: lambda={mean_dt.get('lambda')} ({mean_dt.get('mean_source')}/{mean_dt.get('confidence_flag')})"
                )
                lines.append(
                    f"             raw={dt.get('poisson',{}).get('raw_prob')} adj_mult={adj_dt.get('multiplier')} adj={adj_dt.get('adjusted_prob')}"
                )
                lines.append(
                    f"             caps: stat_cap={caps_dt.get('stat_cap')} global_cap={caps_dt.get('global_cap')} cap_hit={caps_dt.get('cap_hit')} final={fin_dt.get('final_prob')}"
                )

            # AI Math Commentary
            try:
                math_comment = generate_pick_commentary(e)
                lines.append(f"      [AI Math] {math_comment}")
            except Exception as ex:
                lines.append(f"      [AI Math] Commentary unavailable: {ex}")

            # Quick Analysis Commentary
            try:
                quick_comment = generate_analysis(e)
                lines.append(f"      [Quick Analysis] {quick_comment}")
            except Exception as ex:
                lines.append(f"      [Quick Analysis] Commentary unavailable: {ex}")

            # DeepSeek AI Commentary
            try:
                prompt = generate_analysis_prompt(e)
                deepseek_comment = call_deepseek(prompt, max_tokens=60)
                lines.append(f"      [DeepSeek AI] {deepseek_comment}")
            except Exception as ex:
                lines.append(f"      [DeepSeek AI] Commentary unavailable: {ex}")

            if e.get("goblin"):
                lines.append("      [GOBLIN]")
            lines.append("")
            
    # Summary of Skips
    if skipped:
        lines.append("-" * 30)
        lines.append(f"Skipped {len(skipped)} plays (low confidence / blowout)")

    lines.append("")
    lines.append("=" * 65)
    lines.append("[i] CBB = PRODUCTION - 12% market gate, L10 stats, stricter caps than NBA")
    lines.append("=" * 65)

    report = '\n'.join(lines)
    
    # Save report (UTF-8 encoding for emoji support)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUTS_DIR / f"cbb_report_{timestamp}.txt"
    report_path.write_text(report, encoding="utf-8")
    
    latest_path = OUTPUTS_DIR / "cbb_report_latest.txt"
    latest_path.write_text(report, encoding="utf-8")
    
    print(f"  Saved to: {report_path}")
    
    return report


def run_full_pipeline(skip_ingest: bool = False, props_override: Optional[List[Dict]] = None) -> bool:
    """
    Run the complete CBB analysis pipeline.
    
    Args:
        skip_ingest: If True, skip interactive ingest
        props_override: Optional list of props to use (bypasses ingest/load)
    
    Returns: True if successful, False if validation failed
    """
    clear_screen()
    print_cbb_header()

    _write_run_state({
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ended_at": None,
        "mode": "override" if props_override else ("full" if not skip_ingest else "latest"),
        "offline": _cbb_offline_mode(),
        "props": None,
        "raw_edges": None,
        "dedup_edges": None,
        "passed": None,
        "failed": None,
        "skipped": None,
        "actionable": None,
        "status": "STARTED",
        "reason": None,
    })
    

    # Step 1: Ingest
    if props_override:
        props = props_override
        print(f"\n[1/5] Using generated slate: {len(props)} props")
    elif not skip_ingest:
        print("\n[1/5] INGEST SLATE")
        print("-" * 40)
        props = ingest_cbb_slate()
        if not props:
            print("\n⛔ PIPELINE ABORTED — No slate ingested")
            _write_run_state({
                "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ABORTED",
                "reason": "NO_SLATE",
            })
            return False
    else:
        props = load_latest_slate(INPUTS_DIR)
        if not props:
            print("\n⛔ PIPELINE ABORTED — No existing slate found")
            _write_run_state({
                "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ABORTED",
                "reason": "NO_EXISTING_SLATE",
            })
            return False
        print(f"\n[1/5] Using existing slate: {len(props)} props")

    # Automated roster validation: flag props for players not on current team roster
    print("[AUTO] Validating CBB roster for all props...")
    from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
    provider = CBBDataProvider()
    flagged_count = 0
    for prop in props:
        player = prop.get("player")
        team = prop.get("team")
        if not player or not team:
            prop["roster_flag"] = "MISSING_PLAYER_OR_TEAM"
            flagged_count += 1
            continue
        roster = provider.get_team_roster(team)
        found = False
        for p in roster:
            if p.name.strip().lower() == player.strip().lower():
                found = True
                break
        if not found:
            prop["roster_flag"] = "NOT_ON_ROSTER"
            flagged_count += 1
    if flagged_count:
        print(f"[AUTO] [!] {flagged_count} prop(s) flagged: player not found on current team roster.")
    else:
        print("[AUTO] All props matched to current team rosters.")

    _write_run_state({"props": len(props), "status": "INGEST_OK"})
    
    # Step 2: Generate edges
    edges = generate_cbb_edges(props)
    if not edges:
        print("\n⛔ PIPELINE ABORTED — No edges generated")
        _write_run_state({
            "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ABORTED",
            "reason": "NO_EDGES",
            "raw_edges": 0,
            "dedup_edges": 0,
        })
        return False

    _write_run_state({
        "raw_edges": len(props),
        "dedup_edges": len(edges),
        "status": "EDGES_OK",
    })
    
    # Step 3: Apply gates
    edges = apply_cbb_gates(edges)

    try:
        passed_ct = sum(1 for e in edges if e.get("gates_all_passed"))
        failed_ct = len(edges) - passed_ct
    except Exception:
        passed_ct = None
        failed_ct = None

    _write_run_state({
        "passed": passed_ct,
        "failed": failed_ct,
        "status": "GATES_OK",
    })
    
    # Step 4: Score
    edges = score_cbb_edges(edges)

    skipped_ct = sum(1 for e in edges if e.get("tier") == "SKIP")
    actionable_ct = sum(1 for e in edges if e.get("tier") in ("LEAN", "STRONG"))
    _write_run_state({
        "skipped": skipped_ct,
        "actionable": actionable_ct,
        "status": "SCORED",
    })
    
    # Step 5: Validate (HARD GATE)
    valid = validate_cbb_output(edges)
    if not valid:
        print("\n⛔ PIPELINE ABORTED — Validation failed")
        _write_run_state({
            "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ABORTED",
            "reason": "VALIDATION_FAILED",
        })
        return False

    # Step 5.5: Write RISK_FIRST JSON output for advanced menu features
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        risk_first_path = OUTPUTS_DIR / f"cbb_RISK_FIRST_{timestamp}_FROM_UD.json"
        # Save all actionable picks/edges (NBA saves all, so mirror that)
        with open(risk_first_path, "w", encoding="utf-8") as f:
            json.dump({
                "picks": edges,
                "generated": datetime.now().isoformat(),
                "source": "CBB_PIPELINE"
            }, f, indent=2)
        print(f"\n  [OK] RISK_FIRST output saved: {risk_first_path.name}")
    except Exception as e:
        print(f"\n  [X] Failed to write RISK_FIRST output: {e}")

    # Step 6: Render
    report = render_cbb_report(edges)

    # --- ENHANCED SUMMARY PATCH ---
    # Import stat_rank_explainer and prepend enhanced summary
    try:
        from sports.cbb.analysis.stat_rank_explainer import rank_picks_by_stat, format_enhanced_report
        rankings = rank_picks_by_stat(edges)
        enhanced_summary = format_enhanced_report(rankings)
        combined_report = enhanced_summary + "\n\n" + report
    except Exception as e:
        print(f"[WARN] Could not generate enhanced summary: {e}")
        combined_report = report

    print(combined_report)

    # Save combined report (UTF-8 encoding for emoji support)
    from pathlib import Path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUTS_DIR / f"cbb_report_{timestamp}.txt"
    report_path.write_text(combined_report, encoding="utf-8")
    latest_path = OUTPUTS_DIR / "cbb_report_latest.txt"
    latest_path.write_text(combined_report, encoding="utf-8")
    print(f"  Saved to: {report_path}")

    _write_run_state({
        "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "COMPLETED",
        "reason": None,
    })

    # === CROSS-SPORT DATABASE: Save top 5 CBB picks ===
    try:
        from engine.daily_picks_db import save_top_picks
        from sports.cbb.generate_professional_report import has_real_opponent
        # Filter: tier + opponent (matches professional report filter)
        actionable = [e for e in edges if e.get("tier") in ("LEAN", "STRONG") and has_real_opponent(e)]
        if actionable:
            # Sort by probability descending
            actionable.sort(key=lambda x: x.get("probability", x.get("final_probability", 0)), reverse=True)
            cbb_edges = []
            for edge in actionable[:10]:  # Take top 10 for selection
                cbb_edges.append({
                    "player": edge.get("player", edge.get("entity", "")),
                    "stat": edge.get("stat", edge.get("market", "")),
                    "line": edge.get("line", 0),
                    "direction": edge.get("direction", "").upper(),
                    "probability": edge.get("probability", edge.get("final_probability", 0.5)),
                    "tier": edge.get("tier", "LEAN"),
                    "team": edge.get("team", ""),
                })
            save_top_picks(cbb_edges, "CBB", top_n=5)
            print(f"\n  ✅ Cross-Sport DB: Saved top 5 CBB picks")
    except ImportError:
        pass  # Cross-sport module not available
    except Exception as e:
        print(f"\n  ⚠️ Cross-Sport DB save: {e}")

    print("\n" + "=" * 65)
    print("[OK] CBB PIPELINE COMPLETE")
    print("=" * 65)

    return True


def quick_analyze(raw_text: str) -> bool:
    """
    Quick analysis from raw paste (skips interactive ingest).
    """
    print("\n[CBB] QUICK ANALYSIS")
    print("-" * 40)

    if not (raw_text or "").strip():
        print("✗ No input received (paste was empty)")
        print("\nAccepted formats (examples):")
        print("  Otega Oweh points lower 18.5")
        print("  Denzel Aberdeen 3pm higher 1.5")
        print("  Cooper Flagg (Duke) rebounds higher 7.5")
        print("\nTip: After choosing [3], paste the props, then press Enter twice.")
        return False
    
    props = parse_text(raw_text)
    if not props:
        print("✗ No valid props parsed")
        print("\nAccepted formats (examples):")
        print("  Otega Oweh points lower 18.5")
        print("  Denzel Aberdeen 3pm higher 1.5")
        print("  Cooper Flagg (Duke) rebounds higher 7.5")
        print("\nIf you're pasting from Underdog UI, include the full block (player, team line, matchup, line, stat, Higher/Lower).")
        return False
    
    print(f"✓ Parsed {len(props)} props")
    save_slate(props, INPUTS_DIR)
    
    return run_full_pipeline(skip_ingest=True, props_override=props)


def view_latest_report():
    """Display the latest CBB report."""
    clear_screen()
    print("\n" + "=" * 65)
    print("  VIEW LATEST CBB REPORT")
    print("=" * 65)
    
    report_path = OUTPUTS_DIR / "cbb_report_latest.txt"
    
    if report_path.exists():
        print(report_path.read_text(encoding="utf-8", errors="replace"))
    else:
        print("\n[X] No report found")
        print(f"  Expected: {report_path}")


def manage_player_overrides():
    """
    Interactive menu to set manual player averages when ESPN doesn't have data.
    """
    clear_screen()
    print("\n" + "=" * 65)
    print("  PLAYER OVERRIDES (Manual Averages)")
    print("=" * 65)
    print("\n  Use this when ESPN doesn't have player stats.")
    print("  Overrides are saved and persist between sessions.")
    print()
    
    provider = CBBDataProvider()
    
    # Show current overrides
    overrides = provider.list_overrides()
    if overrides:
        print("  Current overrides:")
        for key, stats in overrides.items():
            ppg = stats.get("points_avg", 0)
            rpg = stats.get("rebounds_avg", 0)
            print(f"    - {key}: PPG={ppg}, RPG={rpg}")
        print()
    
    print("  [1] Add single player override")
    print("  [2] Add from today's slate (auto-fill from lines)")
    print("  [3] Clear all overrides")
    print("  [0] Back")
    print()
    
    choice = input("  Choice: ").strip()
    
    if choice == "1":
        print("\n  Enter player details:")
        name = input("    Player name: ").strip()
        team = input("    Team abbr (e.g., DUKE): ").strip().upper()
        
        try:
            ppg = float(input("    Points avg: ").strip() or "0")
            rpg = float(input("    Rebounds avg: ").strip() or "0")
            apg = float(input("    Assists avg: ").strip() or "0")
        except ValueError:
            print("\n  [X] Invalid number")
            return
        
        provider.set_player_override(name, team, points=ppg, rebounds=rpg, assists=apg)
        print(f"\n  [OK] Override set for {name} ({team})")
        
    elif choice == "2":
        # Auto-fill from slate
        props = load_latest_slate(INPUTS_DIR)
        if not props:
            print("\n  [X] No slate found. Ingest a slate first.")
            return
        
        print(f"\n  Found {len(props)} props in slate.")
        print("  Setting overrides using line values as estimated averages...")
        print("  (This assumes lines are close to actual averages)")
        print()
        
        # Group by player
        players = {}
        for p in props:
            key = (p["player"], p["team"])
            if key not in players:
                players[key] = {"points": 0, "rebounds": 0, "assists": 0}
            
            stat = p["stat"].lower()
            line = p["line"]
            
            if stat == "points":
                players[key]["points"] = line
            elif stat == "rebounds":
                players[key]["rebounds"] = line
            elif stat == "assists":
                players[key]["assists"] = line
        
        # Set overrides
        for (name, team), stats in players.items():
            provider.set_player_override(
                name, team,
                points=stats["points"],
                rebounds=stats["rebounds"],
                assists=stats["assists"]
            )
        
        print(f"\n  [OK] Set overrides for {len(players)} players")
        
    elif choice == "3":
        confirm = input("  Clear all overrides? (y/N): ").strip().lower()
        if confirm == "y":
            # Clear the overrides file
            override_file = CACHE_DIR / "player_overrides.json"
            if override_file.exists():
                override_file.write_text("{}")
            print("  [OK] All overrides cleared")


# ============================================================================
# NEW NBA-STYLE INSIGHTS HANDLERS (v1.1)
# ============================================================================

def run_cbb_stat_rankings():
    """
    [T] Stat Rankings - Top-5 picks per stat category (NBA-style).
    """
    clear_screen()
    print("\n" + "=" * 70)
    print("  [T] CBB STAT RANKINGS — Top 5 Per Category")
    print("=" * 70)
    
    # Find latest RISK_FIRST JSON (excluding _STAT_RANKINGS files)
    from pathlib import Path
    json_files = [
        f for f in OUTPUTS_DIR.glob("*RISK_FIRST*.json")
        if "_STAT_RANKINGS" not in f.name
    ]
    
    if not json_files:
        print("\n[X] No RISK_FIRST output found.")
        print("    Run [2] ANALYZE SLATE first.")
        return
    
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"\n  Source: {latest_file.name}")
    
    try:
        with open(latest_file) as f:
            data = json.load(f)
        
        picks = data.get("picks", data.get("edges", []))
        if not picks:
            print("\n[X] No picks found in file.")
            return
        
        # Import the CBB stat rank explainer
        try:
            from sports.cbb.analysis.stat_rank_explainer import (
                rank_picks_by_stat,
                format_enhanced_report
            )
        except ImportError:
            print("\n[X] CBB stat_rank_explainer module not found.")
            print("    Module expected at: sports/cbb/analysis/stat_rank_explainer.py")
            return
        
        # Rank picks
        result = rank_picks_by_stat(picks)
        
        # Format options
        print("\n  Format:")
        print("  [1] Standard (top 5 per stat)")
        print("  [2] Enhanced (full details + explanations)")
        print("  [0] Cancel")
        
        fmt_choice = input("\n  Choice: ").strip()
        
        if fmt_choice == "0":
            return
        
        print("\n" + "=" * 70)
        
        if fmt_choice == "2":
            # Enhanced format
            report = format_enhanced_report(result)
            print(report)
        else:
            # Standard format - use top_5_by_stat (CBB stat rank explainer attribute)
            for stat, ranked in result.top_5_by_stat.items():
                if not ranked:
                    continue
                print(f"\n  ━━━ {stat.upper()} ━━━")
                for i, pick in enumerate(ranked[:5], 1):
                    direction = (pick.direction or "?").upper()[:1]
                    tier = getattr(pick, 'edge_quality', None) or getattr(pick, 'tier', None) or "?"
                    prob = pick.probability * 100
                    print(f"    {i}. {pick.player:<20} {direction} {pick.line:<5} {tier:<6} {prob:.0f}%")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n[X] Error: {e}")


def run_cbb_archetype_filter():
    """
    [A] Archetype Filter - Filter by CBB player roles.
    """
    clear_screen()
    print("\n" + "=" * 70)
    print("  [A] CBB ARCHETYPE FILTER")
    print("=" * 70)
    
    # CBB archetypes (different from NBA due to college rotations)
    archetypes = {
        "1": ("SCORER", ["points", "pts+reb", "pts+ast"]),
        "2": ("REBOUNDER", ["rebounds", "pts+reb", "reb+ast"]),
        "3": ("PLAYMAKER", ["assists", "pts+ast", "reb+ast"]),
        "4": ("SHOOTER", ["3pm"]),
        "5": ("COMBO", ["pra", "pts+reb+ast"]),
    }
    
    print("\n  CBB Archetypes:")
    for key, (name, _) in archetypes.items():
        print(f"    [{key}] {name}")
    print("    [0] Back")
    
    choice = input("\n  Select archetype: ").strip()
    
    if choice == "0" or choice not in archetypes:
        return
    
    archetype_name, stat_patterns = archetypes[choice]
    
    # Find latest RISK_FIRST JSON
    json_files = [
        f for f in OUTPUTS_DIR.glob("*RISK_FIRST*.json")
        if "_STAT_RANKINGS" not in f.name
    ]
    
    if not json_files:
        print("\n[X] No RISK_FIRST output found.")
        return
    
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    
    try:
        with open(latest_file) as f:
            data = json.load(f)
        
        picks = data.get("picks", data.get("edges", []))
        
        # Filter by archetype
        filtered = []
        for pick in picks:
            stat = (pick.get("stat") or "").lower()
            if any(pat in stat for pat in stat_patterns):
                filtered.append(pick)
        
        print(f"\n  [{archetype_name}] {len(filtered)} picks found:")
        print("  " + "-" * 60)
        
        # Sort by probability
        filtered.sort(key=lambda p: p.get("probability", 0), reverse=True)
        
        for pick in filtered[:15]:
            player = pick.get("player", "?")
            stat = pick.get("stat", "?")
            line = pick.get("line", "?")
            direction = (pick.get("direction") or "?").upper()[:1]
            tier = pick.get("tier", "?")
            prob = pick.get("probability", 0) * 100
            
            print(f"    {player:<22} {stat:<12} {direction} {line:<5} {tier:<6} {prob:.0f}%")
        
        if len(filtered) > 15:
            print(f"\n    ... and {len(filtered) - 15} more")
        
    except Exception as e:
        print(f"\n[X] Error: {e}")


def run_cbb_monte_carlo():
    """
    [P] Monte Carlo - Entry optimization for CBB.
    """
    clear_screen()
    print("\n" + "=" * 70)
    print("  [P] CBB MONTE CARLO — Entry Optimization")
    print("=" * 70)
    
    # Find latest RISK_FIRST JSON
    json_files = [
        f for f in OUTPUTS_DIR.glob("*RISK_FIRST*.json")
        if "_STAT_RANKINGS" not in f.name
    ]
    
    if not json_files:
        print("\n[X] No RISK_FIRST output found.")
        print("    Run [2] ANALYZE SLATE first.")
        return
    
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"\n  Source: {latest_file.name}")
    
    try:
        with open(latest_file) as f:
            data = json.load(f)
        
        picks = data.get("picks", data.get("edges", []))
        if not picks:
            print("\n[X] No picks found.")
            return
        
        # Filter actionable picks
        # GOVERNANCE: Use canonical thresholds from config/thresholds.py
        from config.thresholds import get_tier_threshold
        lean_thresh = get_tier_threshold("LEAN", "CBB")
        actionable = [
            p for p in picks
            if p.get("tier") in ("STRONG", "LEAN") and p.get("probability", 0) >= lean_thresh
        ]
        
        if not actionable:
            print(f"\n[X] No actionable picks found (need STRONG/LEAN with >={lean_thresh*100:.0f}% probability).")
            return
        
        print(f"\n  Found {len(actionable)} actionable picks for Monte Carlo.")
        print("\n  Entry size:")
        print("    [2] 2-leg parlay")
        print("    [3] 3-leg parlay")
        print("    [4] 4-leg parlay")
        print("    [5] 5-leg parlay")
        print("    [0] Cancel")
        
        size_choice = input("\n  Choice: ").strip()
        
        if size_choice == "0" or size_choice not in ("2", "3", "4", "5"):
            return
        
        entry_size = int(size_choice)
        
        # Simple Monte Carlo: find best combinations by joint probability
        from itertools import combinations
        import random
        
        # Limit combinations to prevent explosion
        if len(actionable) > 20:
            # Sample top picks
            actionable = sorted(actionable, key=lambda p: p.get("probability", 0), reverse=True)[:20]
        
        # Generate all combinations of size entry_size
        combos = list(combinations(actionable, entry_size))
        
        if len(combos) > 1000:
            # Sample if too many
            combos = random.sample(combos, 1000)
        
        # Score each combo by joint probability (product)
        scored = []
        for combo in combos:
            joint_prob = 1.0
            for pick in combo:
                joint_prob *= pick.get("probability", 0.5)
            
            # Check for correlation (same player = penalty)
            players = [p.get("player") for p in combo]
            has_dupe = len(players) != len(set(players))
            if has_dupe:
                joint_prob *= 0.7  # Correlation penalty
            
            scored.append((joint_prob, combo))
        
        # Sort by joint probability
        scored.sort(key=lambda x: x[0], reverse=True)
        
        print(f"\n  Top 5 {entry_size}-leg entries (by joint probability):")
        print("  " + "=" * 65)
        
        for rank, (joint_prob, combo) in enumerate(scored[:5], 1):
            print(f"\n  #{rank} — Joint Probability: {joint_prob*100:.1f}%")
            print("  " + "-" * 50)
            for pick in combo:
                player = pick.get("player", "?")
                stat = pick.get("stat", "?")
                line = pick.get("line", "?")
                direction = (pick.get("direction") or "?").upper()[:1]
                prob = pick.get("probability", 0) * 100
                print(f"    • {player:<20} {stat:<10} {direction} {line} ({prob:.0f}%)")
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mc_file = OUTPUTS_DIR / f"cbb_monte_carlo_{entry_size}leg_{timestamp}.txt"
        
        with open(mc_file, "w") as f:
            f.write(f"CBB MONTE CARLO — {entry_size}-Leg Entries\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Source: {latest_file.name}\n")
            f.write("=" * 65 + "\n\n")
            
            for rank, (joint_prob, combo) in enumerate(scored[:10], 1):
                f.write(f"#{rank} — Joint Probability: {joint_prob*100:.1f}%\n")
                f.write("-" * 50 + "\n")
                for pick in combo:
                    player = pick.get("player", "?")
                    stat = pick.get("stat", "?")
                    line = pick.get("line", "?")
                    direction = (pick.get("direction") or "?").upper()[:1]
                    prob = pick.get("probability", 0) * 100
                    f.write(f"  {player:<20} {stat:<10} {direction} {line} ({prob:.0f}%)\n")
                f.write("\n")
        
        print(f"\n  Saved to: {mc_file.name}")
        
    except Exception as e:
        print(f"\n[X] Error: {e}")


def run_cbb_auto_ingest():
    """🔌 Auto-ingest CBB props via Playwright (DK Pick6/PrizePicks/Underdog)."""
    print("\n" + "=" * 70)
    print("  🔌 AUTO-INGEST CBB PROPS (Playwright)")
    print("=" * 70)
    print("\n  This uses the universal Playwright scraper.")
    print("  Tip: Persistent profile mode keeps you logged in.")
    
    print("\n  ⚠️  IMPORTANT: When scraping CBB props:")
    print("     1. Navigate to COLLEGE BASKETBALL section")
    print("     2. Scroll through ALL games (both today and future dates)")
    print("     3. Toggle BOTH 'Higher' AND 'Lower' to see all prop sides")
    print("     4. Press Ctrl+C when done browsing")
    
    try:
        from ingestion.prop_ingestion_pipeline import interactive_browse_persistent, run_pipeline
    except Exception as e:
        print(f"\n  ❌ Could not import ingestion pipeline: {e}")
        print("     Expected: ingestion/prop_ingestion_pipeline.py")
        return
    
    print("\n  Choose ingest mode:")
    print("    [1] Persistent browser (recommended) — login once, navigate to CBB props")
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
    
    print(f"\n  ✅ Successfully ingested {len(props)} CBB props!")
    print("\n  📁 Props saved to: outputs/props_latest.json")
    
    # ── AUTO-ANALYSIS PROMPT (Cohesive Pipeline) ──────────────────────────
    print(f"\n  🔬 Run CBB analysis now? [Y/n]: ", end="", flush=True)
    analyze_choice = input().strip().lower()
    
    if analyze_choice in ['n', 'no']:
        print("\n  ➡️ Next: Use [2] Analyze Slate to process these props")
        return
    
    # Convert JSON props to CBB slate format and save
    print(f"\n  📋 Converting {len(props)} props to CBB format...")
    try:
        cbb_props = []
        for prop in props:
            player = prop.get('player', '')
            stat = prop.get('stat', '')
            line = prop.get('line', 0)
            direction = prop.get('direction', 'higher')
            source = prop.get('source', 'Underdog')
            matchup = prop.get('matchup', {})  # Extract matchup context
            
            # Map stat names to CBB format
            stat_map = {
                'points': 'PTS',
                'rebounds': 'REB',
                'assists': 'AST',
                'threes': '3PM',
                '3pm': '3PM',
                'pts_rebs_asts': 'PRA',
                'pra': 'PRA',
                'points+rebounds+assists': 'PRA',
                'pts+reb+ast': 'PRA',
                'points+assists': 'PTS+AST',
                'pts+ast': 'PTS+AST',
                'points+rebounds': 'PTS+REB',
                'pts+reb': 'PTS+REB',
                'rebounds+assists': 'REB+AST',
                'reb+ast': 'REB+AST',
                'blocks': 'BLK',
                'steals': 'STL',
                'turnovers': 'TO',
                'blocks+steals': 'BLK+STL',
            }
            stat_formatted = stat_map.get(stat.lower().replace('_', ' ').replace('+', ' '), stat.upper())
            
            # Try to resolve team from matchup context
            team = 'UNK'
            opponent = 'UNK'
            if matchup:
                # matchup is {'team1': 'ISU', 'team2': 'HOU'}
                team1 = matchup.get('team1', '').strip().upper()
                team2 = matchup.get('team2', '').strip().upper()
                
                # Use team1 as primary team (may be corrected by roster validation)
                # Store both teams separately so projection model can use single team abbrev
                if team1:
                    team = team1
                    opponent = team2 or 'UNK'
                elif team2:
                    team = team2
                    opponent = 'UNK'
            
            cbb_props.append({
                'player': player,
                'team': team,  # Single team abbreviation for projection model
                'opponent': opponent,  # Opponent for context
                'stat': stat_formatted,
                'line': float(line),
                'direction': direction,
                'source': source,
            })
        
        if not cbb_props:
            print("  ✗ No valid props after conversion")
            return
        
        # Save to CBB inputs directory
        output_path = save_slate(cbb_props, INPUTS_DIR, filename_prefix="cbb_slate_playwright")
        print(f"  ✓ Saved {len(cbb_props)} props to CBB slate format")
        
    except Exception as e:
        print(f"  ✗ Conversion failed: {e}")
        return
    
    # Run full CBB pipeline
    print(f"\n  🚀 Running CBB analysis pipeline...")
    try:
        ok = run_full_pipeline(skip_ingest=True)
        if ok:
            print("\n  ✅ Analysis complete! Check [V] View Results or [R] Export Report")
        else:
            print("\n  ⚠️ Analysis completed with warnings. Check output above.")
    except Exception as e:
        print(f"\n  ✗ Analysis failed: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# NEW FEATURES - NBA Feature Parity
# ============================================================================

def run_cbb_resolve_picks():
    """[6] Resolve CBB picks after games - update calibration history."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [6] RESOLVE CBB PICKS - Update Calibration History")
    print("=" * 70)
    
    print("""
  OPTIONS:
    [1] Resolve today's picks (manual entry)
    [2] Resolve specific date  
    [3] View calibration history
    [0] Back
""")
    
    try:
        choice = input("  Choice: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return
    
    if choice in ("", "0"):
        return
    
    if choice == "3":
        # View calibration history
        print("\n" + "=" * 70)
        print("  CALIBRATION HISTORY (CBB)")
        print("=" * 70)
        
        cal_file = PROJECT_ROOT / "calibration" / "calibration_history.csv"
        if not cal_file.exists():
            print("\n  No calibration history found.")
            return
        
        try:
            import pandas as pd
            df = pd.read_csv(cal_file)
            cbb_picks = df[df['sport'] == 'CBB'].tail(20) if 'sport' in df.columns else df.tail(20)
            
            if cbb_picks.empty:
                print("\n  No CBB picks in calibration history.")
            else:
                print(f"\n  Last {len(cbb_picks)} CBB picks:\\n")
                for _, row in cbb_picks.iterrows():
                    result = "\u2713" if row.get('result') == 'W' else "\u2717"
                    print(f"  {result} {row.get('date', 'N/A')} | {row.get('player', 'N/A')} {row.get('stat', 'N/A')} {row.get('line', 'N/A')} | {row.get('tier', 'N/A')} {row.get('probability', 0):.1%}")
        except Exception as e:
            print(f"\n  Error reading calibration history: {e}")
    
    else:
        print("\n  [!] Manual result entry not yet implemented for CBB.")
        print("      Use NBA menu [6] Resolve Picks and filter by sport.")


def run_cbb_calibration():
    """[7] Calibration backtest - historical accuracy."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [7] CBB CALIBRATION BACKTEST")
    print("=" * 70)
    
    try:
        import subprocess
        print("\n  Running calibration report for CBB...")
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "calibration" / "unified_tracker.py"), 
             "--report", "--sport", "cbb"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"\n  \u26a0\ufe0f Calibration backtest failed (exit code {result.returncode})")
    
    except Exception as e:
        print(f"\n  Error running calibration: {e}")


def run_cbb_drift_detector():
    """[DR] Drift Detector - calibration monitoring."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [DR] CBB DRIFT DETECTOR")
    print("=" * 70)
    
    print("\n  [!] Drift detector analyzes calibration stability over time.")
    print("      Checking for tier inflation/deflation...\\n")
    
    try:
        from calibration.drift_detector import detect_calibration_drift
        drift_report = detect_calibration_drift(sport="CBB")
        print(drift_report if drift_report else "  No drift detected.")
    except ImportError:
        print("\n  [!] drift_detector.py not found in calibration/")
        print("      This feature requires calibration tracking to be set up.")
    except Exception as e:
        print(f"\n  Error: {e}")


def run_cbb_interactive_filter():
    """[I] Interactive Filter - custom filter combinations."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [I] CBB INTERACTIVE FILTER")
    print("=" * 70)
    
    try:
        import subprocess
        
        # Auto-detect latest CBB RISK_FIRST file
        out_dir = OUTPUTS_DIR
        risk_first_files = sorted(out_dir.glob("cbb_RISK_FIRST_*.json"), 
                                  key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not risk_first_files:
            print("\n  [!] No CBB analysis output found.")
            print("      Run [2] ANALYZE SLATE first.")
            return
        
        input_file = str(risk_first_files[0])
        print(f"\n  Using: {risk_first_files[0].name}\\n")
        
        subprocess.run([sys.executable, "interactive_filter_menu.py", input_file])
    
    except Exception as e:
        print(f"\n  Error: {e}")


def run_cbb_probability_breakdown():
    """[P2] Probability Breakdown - confidence composition."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [P2] CBB PROBABILITY BREAKDOWN")
    print("=" * 70)
    
    print("\n  [!] Shows what drives each pick's confidence (transparency).")
    print("      Not yet implemented for CBB - use NBA menu [P] as reference.\\n")


def run_cbb_distribution_preview():
    """[K] Distribution Preview - Monte Carlo visualization."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [K] CBB DISTRIBUTION PREVIEW")
    print("=" * 70)
    
    print("\n  [!] Monte Carlo simulation visualization for variance understanding.")
    print("      Not yet implemented for CBB - use NBA menu [K] as reference.\\n")


def run_cbb_loss_expectation():
    """[X] Loss Expectation - worst-case scenarios."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [X] CBB LOSS EXPECTATION")
    print("=" * 70)
    
    print("\n  [!] Worst-case scenario modeling and loss frequency analysis.")
    print("      Not yet implemented for CBB - use NBA menu [X] as reference.\\n")


def run_cbb_ban_manager():
    """[9] Ban List Manager - manage player+stat bans."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [9] CBB BAN LIST MANAGER")
    print("=" * 70)
    
    ban_file = PROJECT_ROOT / "player_stat_memory.json"
    
    if not ban_file.exists():
        print("\n  No ban list found. Creating...\\n")
        ban_file.write_text(json.dumps({"bans": {}, "warnings": {}}, indent=2))
    
    data = json.loads(ban_file.read_text())
    
    # Handle nested format
    if "bans" not in data:
        data = {"bans": {}, "warnings": {}}
    
    bans_dict = data.get("bans", {})
    warnings_dict = data.get("warnings", {})
    
    # Filter CBB bans (if tagged)
    cbb_bans = {k: v for k, v in bans_dict.items() if v.get("sport") == "CBB"}
    
    print(f"\n  CBB BANNED ({len(cbb_bans)} entries):")
    print("  " + "-" * 50)
    for i, (key, info) in enumerate(list(cbb_bans.items())[:15], 1):
        fails = info.get("fails_10", info.get("fail_count", 0))
        reason = info.get("reason", "")
        reason_str = f" - {reason}" if reason else ""
        print(f"  {i:2}. {key} (fails: {fails}){reason_str}")
    
    if not cbb_bans:
        print("  (No CBB-specific bans)")
    
    print("\n  [A] Add ban  [R] Remove ban  [B] Back")
    
    try:
        choice = input("\n  Choice: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return
    
    if choice == "A":
        try:
            player = input("  Player name: ").strip()
            stat = input("  Stat (e.g., PTS, AST): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if player and stat:
            key = f"{player}|{stat}"
            data["bans"][key] = {
                "fails_10": 99, 
                "fails_30": 99, 
                "last_fail": datetime.now().strftime("%Y-%m-%d"),
                "banned": True,
                "reason": "Manual CBB ban",
                "sport": "CBB"
            }
            ban_file.write_text(json.dumps(data, indent=2))
            print(f"\n  \u2713 Added CBB ban: {key}")
    
    elif choice == "R":
        try:
            key = input("  Enter exact key to remove (Player|stat): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if key in data["bans"]:
            del data["bans"][key]
            ban_file.write_text(json.dumps(data, indent=2))
            print(f"\n  \u2713 Removed: {key}")
        else:
            print("\n  Key not found.")


# Global settings for CBB (persisted across sessions)
_CBB_SETTINGS = {
    "soft_gates": False,
    "balanced_report": False,
    "quant_modules": False,
    "jiggy": False,
}


def load_cbb_settings():
    """Load CBB settings from config file."""
    global _CBB_SETTINGS
    settings_file = CONFIG_DIR / "cbb_settings.json"
    if settings_file.exists():
        try:
            _CBB_SETTINGS = json.loads(settings_file.read_text())
        except Exception:
            pass  # Use defaults
    return _CBB_SETTINGS


def save_cbb_settings():
    """Save CBB settings to config file."""
    settings_file = CONFIG_DIR / "cbb_settings.json"
    settings_file.write_text(json.dumps(_CBB_SETTINGS, indent=2))


def run_cbb_settings():
    """[10] Settings Toggle - soft gates, balanced reports, etc."""
    global _CBB_SETTINGS
    
    while True:
        clear_screen()
        print("\n" + "=" * 70)
        print("  [10] CBB SETTINGS")
        print("=" * 70)
        
        print(f"""
  [1] Soft Gates:      {"ON " if _CBB_SETTINGS["soft_gates"] else "OFF"} - Relaxed defense/role gates
  [2] Balanced Report: {"ON " if _CBB_SETTINGS["balanced_report"] else "OFF"} - Team-balanced output
  [3] Quant Modules:   {"ON " if _CBB_SETTINGS["quant_modules"] else "OFF"} - MC/Bayes auto-run
  [4] JIGGY Mode:      {"ON " if _CBB_SETTINGS["jiggy"] else "OFF"} - UNGOVERNED testing
  
  [S] Save & Back
  [B] Back without saving
""")
        
        try:
            choice = input("  Toggle setting: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            break
        
        if choice == "1":
            _CBB_SETTINGS["soft_gates"] = not _CBB_SETTINGS["soft_gates"]
        elif choice == "2":
            _CBB_SETTINGS["balanced_report"] = not _CBB_SETTINGS["balanced_report"]
        elif choice == "3":
            _CBB_SETTINGS["quant_modules"] = not _CBB_SETTINGS["quant_modules"]
        elif choice == "4":
            _CBB_SETTINGS["jiggy"] = not _CBB_SETTINGS["jiggy"]
        elif choice == "S":
            save_cbb_settings()
            print("\n  \u2713 Settings saved!")
            pause()
            break
        elif choice == "B":
            break


def run_cbb_jiggy_toggle():
    """[J] JIGGY Mode Toggle - UNGOVERNED testing."""
    global _CBB_SETTINGS
    
    _CBB_SETTINGS["jiggy"] = not _CBB_SETTINGS.get("jiggy", False)
    save_cbb_settings()
    
    state = "ON" if _CBB_SETTINGS["jiggy"] else "OFF"
    
    clear_screen()
    if _CBB_SETTINGS["jiggy"]:
        print(f"\n\u26a0\ufe0f  CBB JIGGY (UNGOVERNED) mode is now {state}!")
        print("    \u2192 Probability lineage tracking: DISABLED")
        print("    \u2192 Calibration updates: DISABLED")
        print("    \u2192 All outputs tagged as UNGOVERNED")
        print("    \u2192 Perfect for testing graduated gate v2.0")
    else:
        print(f"\n\u2713 CBB JIGGY mode is now {state} \u2014 Full governance restored")


def run_cbb_cheatsheet():
    """[H] Cheat Sheet - quick reference report."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [H] CBB CHEAT SHEET")
    print("=" * 70)
    
    try:
        import subprocess
        print("\n  Generating CBB cheat sheet...")
        result = subprocess.run(
            [sys.executable, 
             str(PROJECT_ROOT / "scripts" / "generate_consolidated_cheatsheet.py"), 
             "--sport", "cbb"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n  \u2713 Cheat sheet generated successfully!")
        else:
            print(f"\n  \u26a0\ufe0f Failed (exit code {result.returncode})")
    
    except Exception as e:
        print(f"\n  Error: {e}")


# ============================================================================
# END NEW FEATURES
# ============================================================================


def show_menu():
    """Interactive CBB menu (NBA-style command center layout)."""
    while True:
        clear_screen()
        _print_cbb_command_center_menu()
        
        choice = input("  Select option: ").strip().upper()
        
        if choice == "1B":
            # Auto-ingest props via Playwright (DK/PrizePicks/Underdog)
            run_cbb_auto_ingest()
            pause()
        
        elif choice == "8":
            # Odds API no-scrape ingest
            run_cbb_odds_api_ingest()
            pause()
        
        elif choice == "1":
            ingest_cbb_slate()
            pause()
        
        elif choice == "2":
            # Analyze from latest slate (no interactive ingest)
            ok = run_full_pipeline(skip_ingest=True)
            if not ok:
                print("\n[!] Analysis did not complete (see messages above).")
            pause()

        elif choice == "3":
            print("\n" + "-" * 50)
            print("Paste Underdog CBB props below.")
            print("Press Enter twice when done.")
            print("-" * 50 + "\n")
            
            lines = []
            empty_count = 0
            while empty_count < 2:
                try:
                    line = input()
                    if not line.strip():
                        empty_count += 1
                    else:
                        empty_count = 0
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            
            if lines:
                quick_analyze('\n'.join(lines))
            pause()

        elif choice == "4":
            # Roster averages from ANALYSIS OUTPUT (the actual computed data)
            clear_screen()
            print("\n" + "=" * 70)
            print("  [4] ROSTER AVERAGES (FROM ANALYSIS)")
            print("=" * 70)

            # Load the analysis output (not raw slate)
            analysis_files = sorted(OUTPUTS_DIR.glob("cbb_RISK_FIRST_*.json"), reverse=True)
            if not analysis_files:
                print("\n[X] No analysis output found. Run [2] ANALYZE SLATE first.")
                pause()
                continue

            with open(analysis_files[0]) as f:
                analysis_data = json.load(f)
            
            picks = analysis_data.get("picks", [])
            if not picks:
                print("\n[X] Analysis output has no picks.")
                pause()
                continue

            teams = sorted({(p.get("team") or "UNK").upper() for p in picks if (p.get("team") or "UNK") != "UNK"})
            if not teams:
                print("\n[X] Could not detect any teams in the analysis.")
                pause()
                continue

            print(f"\n[i] Showing stats from: {analysis_files[0].name}")
            print(f"[i] Total picks analyzed: {len(picks)} | Teams: {len(teams)}")
            print("[i] '>' marks players with LEAN/STRONG picks\n")

            for t in teams:
                roster_lines = _render_roster_from_analysis(t, picks)
                print("\n" + "=" * 60)
                for rl in roster_lines:
                    print(rl)
            pause()

        elif choice == "F":
            toggle_cbb_offline_mode()
            # No pause: return to menu immediately with updated status line
            continue

        elif choice == "S":
            clear_screen()
            print("\n" + "=" * 70)
            print("  [S] VIEW SLATE")
            print("=" * 70)
            
            props = load_latest_slate(INPUTS_DIR)
            if props:
                # Deduplicate for display: show unique player/stat/line combos
                seen = set()
                unique_props = []
                for p in props:
                    key = (p['player'], p['team'], p['stat'], p['line'])
                    if key not in seen:
                        seen.add(key)
                        unique_props.append(p)
                
                print(f"\nLatest slate: {len(unique_props)} unique props ({len(props)} raw including both directions)\n")
                for i, p in enumerate(unique_props[:30], 1):
                    print(f"  {i:2}. {p['player']} ({p['team']}) - {p['stat']} {p['line']}")
                if len(unique_props) > 30:
                    print(f"\n  ... and {len(unique_props) - 30} more")
            else:
                print("\n✗ No slate found")
            pause()

        elif choice == "V":
            view_latest_report()
            pause()

        elif choice == "R":
            export_latest_cbb_report()
            pause()
        
        elif choice == "R2":
            # Generate Professional Report (NBA-style)
            generate_professional_cbb_report()
            pause()
        
        elif choice == "C":
            clear_screen()
            print("\n" + "=" * 65)
            print("  CBB CONFIGURATION")
            print("=" * 65)
            
            # Show config files
            print("\nConfig files:")
            for cfg_file in CONFIG_DIR.glob("*.yaml"):
                print(f"  - {cfg_file.name}")
            for cfg_file in CONFIG_DIR.glob("*.json"):
                print(f"  - {cfg_file.name}")
            
            # Show key thresholds
            print("\nKey Thresholds:")
            print("  - STRONG tier: >=70%")
            print("  - LEAN tier: >=60%")
            print("  - No SLAM tier (max 79%)")
            print("  - Min MPG gate: 20")
            print("  - Blowout skip: >25% spread")
            pause()
        
        elif choice == "O":
            manage_player_overrides()
            pause()
        
        elif choice == "T":
            # Stat Rankings (NBA-style)
            run_cbb_stat_rankings()
            pause()
        
        elif choice == "M":
            # Matchup Memory (placeholder)
            clear_screen()
            print("\n" + "=" * 70)
            print("  [M] MATCHUP MEMORY")
            print("=" * 70)
            print("\n  [!] CBB Matchup Memory is not yet implemented.")
            print("      College schedules change rapidly - historical matchups")
            print("      are less reliable than NBA.")
            pause()
        
        elif choice == "A":
            # Archetype Filter (placeholder)
            run_cbb_archetype_filter()
            pause()
        
        elif choice == "P":
            # Monte Carlo entry optimization
            run_cbb_monte_carlo()
            pause()
        
        elif choice == "6":
            # Resolve Picks
            run_cbb_resolve_picks()
            pause()
        
        elif choice == "7":
            # Calibration Backtest
            run_cbb_calibration()
            pause()
        
        elif choice == "DR":
            # Drift Detector
            run_cbb_drift_detector()
            pause()
        
        elif choice == "I":
            # Interactive Filter
            run_cbb_interactive_filter()
            pause()
        
        elif choice == "P2":
            # Probability Breakdown
            run_cbb_probability_breakdown()
            pause()
        
        elif choice == "K":
            # Distribution Preview
            run_cbb_distribution_preview()
            pause()
        
        elif choice == "X":
            # Loss Expectation
            run_cbb_loss_expectation()
            pause()
        
        elif choice == "9":
            # Ban List Manager
            run_cbb_ban_manager()
            pause()
        
        elif choice == "10":
            # Settings Toggle
            run_cbb_settings()
            # No pause - returns to menu with updated display
            continue
        
        elif choice == "J":
            # JIGGY Mode Toggle
            run_cbb_jiggy_toggle()
            pause()
        
        elif choice == "H":
            # Cheat Sheet
            run_cbb_cheatsheet()
            pause()
        
        elif choice == "D":
            # Diagnosis All
            from sports.cbb.diagnostics import run_diagnostics
            run_diagnostics()
            pause()
        
        elif choice == "T2":
            # Send Top 7 CBB picks to Telegram
            send_cbb_top7_telegram()
            pause()
        
        elif choice == "0":
            break
        
        else:
            print(f"\n✗ Invalid choice: {choice}")
            pause()


if __name__ == "__main__":
    # Load CBB settings at startup
    load_cbb_settings()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--full":
            run_full_pipeline()
        elif sys.argv[1] == "--latest":
            run_full_pipeline(skip_ingest=True)
        elif sys.argv[1] == "--menu":
            show_menu()
        elif sys.argv[1] == "--help":
            print("Usage: python cbb_main.py [--full|--latest|--menu|--help]")
    else:
        show_menu()
