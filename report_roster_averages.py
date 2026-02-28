#!/usr/bin/env python3
"""Generate per-player stat averages for teams in a slate.

Uses the daily NBA mu/sigma cache produced by stats_last10_cache.py (L10/L5 blend).

By default, treats "roster" as the set of unique players appearing in the provided slate.

Output columns are per-game means (mu). Shows L5, L10, and Season averages.

Now includes INJURY STATUS check from ESPN API - filters out players who are OUT.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import numpy as np
from datetime import date


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass
class PlayerRow:
    player: str
    team: str
    mu: Dict[str, float] = field(default_factory=dict)  # Blended (current)
    sigma: Dict[str, float] = field(default_factory=dict)
    mu_l5: Dict[str, float] = field(default_factory=dict)  # Last 5 games
    mu_l10: Dict[str, float] = field(default_factory=dict)  # Last 10 games
    mu_season: Dict[str, float] = field(default_factory=dict)  # Full season
    series: Dict[str, List[float]] = field(default_factory=dict)  # Raw game data
    injury_status: str = "Active"  # Active, Out, Questionable, Doubtful, Probable
    injury_detail: str = ""  # e.g., "Ankle", "Knee"


BASE_STATS: Tuple[str, ...] = (
    "points",
    "rebounds",
    "assists",
    "3pm",
    "turnovers",
    "steals",
    "blocks",
)


# =====================
# Specialist tag rules
# =====================
# These tags are intentionally simple and derived from per-game averages available
# in the cache (L5/L10/Season). They are meant to highlight exploitable player roles
# (e.g., 3PM shooters, stocks specialists) and volatility risks (turnovers, iso-ish).
TAG_THRESHOLDS = {
    # Volume shooters
    "3P_ELITE": 2.8,   # elite 3PM per game
    "3P_GOOD": 1.9,    # solid 3PM per game
    # Stocks
    "BLK_ELITE": 1.3,
    "BLK_GOOD": 1.0,
    "STL_ELITE": 1.6,
    "STL_GOOD": 1.3,
    # Turnover pressure (risk)
    "TOV_HIGH": 3.0,
    "TOV_MED": 2.5,
    # ISO heuristic (we do not have true iso frequency in this report)
    # This is intentionally conservative and labeled as a heuristic.
    "ISO_PTS": 24.0,
    "ISO_AST_MAX": 6.0,
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_cache_for_date(date_iso: str) -> Optional[Path]:
    cache_dir = PROJECT_ROOT / "outputs" / "stats_cache"
    if not cache_dir.exists():
        return None

    # Prefer the auto blend cache (most recent methodology)
    preferred = cache_dir / f"nba_mu_sigma_L10_L5_blend0.65_auto_{date_iso}.json"
    if preferred.exists():
        return preferred

    # Fallback: any cache containing that date
    candidates = sorted(cache_dir.glob(f"*{date_iso}.json"))
    return candidates[0] if candidates else None


def _missing_players(
    slate_players: Sequence[Tuple[str, str]],
    *,
    overlay: Dict[Tuple[str, str], Tuple[float, float]],
    series: Dict[Tuple[str, str], List[float]],
    required_stats: Sequence[str],
) -> Dict[str, List[str]]:
    """Return {player: [missing_stat, ...]} for any player missing overlay or series."""
    req = [s for s in required_stats if isinstance(s, str) and s]
    out: Dict[str, List[str]] = {}
    for player, _team in slate_players:
        miss: List[str] = []
        for stat in req:
            if (player, stat) not in overlay:
                miss.append(stat)
            if (player, stat) not in series or not series.get((player, stat)):
                miss.append(stat)
        if miss:
            out[player] = sorted(set(miss))
    return out


def _load_cache(cache_path: Path) -> Tuple[Dict[Tuple[str, str], Tuple[float, float]], Dict[str, str], Dict[Tuple[str, str], List[float]]]:
    raw = _read_json(cache_path)

    overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for item in raw.get("stats", []) or []:
        p = item.get("player")
        s = item.get("stat")
        mu = item.get("mu")
        sigma = item.get("sigma")
        if isinstance(p, str) and isinstance(s, str) and isinstance(mu, (int, float)) and isinstance(sigma, (int, float)):
            overlay[(p, s)] = (float(mu), float(sigma))

    team_map: Dict[str, str] = {}
    for item in raw.get("teams", []) or []:
        p = item.get("player")
        t = item.get("team")
        if isinstance(p, str) and isinstance(t, str) and p:
            team_map[p] = t

    # Load series data for L5/L10/Season computation
    series: Dict[Tuple[str, str], List[float]] = {}
    for item in raw.get("series", []) or []:
        p = item.get("player")
        s = item.get("stat")
        vals = item.get("values", [])
        if isinstance(p, str) and isinstance(s, str) and isinstance(vals, list):
            series[(p, s)] = [float(v) for v in vals if isinstance(v, (int, float))]

    return overlay, team_map, series


def _players_from_slate(slate_path: Path, *, teams: Optional[Sequence[str]] = None) -> List[Tuple[str, str]]:
    raw = _read_json(slate_path)
    
    # Handle multiple slate formats: plays, picks, or raw list
    plays = []
    if isinstance(raw, list):
        plays = raw
    elif isinstance(raw, dict):
        plays = raw.get("plays", []) or raw.get("picks", []) or raw.get("results", []) or []

    want = None
    if teams:
        want = {t.strip().upper() for t in teams if isinstance(t, str) and t.strip()}

    seen: set[Tuple[str, str]] = set()
    out: List[Tuple[str, str]] = []
    for p in plays:
        if not isinstance(p, dict):
            continue
        player = p.get("player")
        team = p.get("team")
        if not isinstance(player, str) or not player.strip():
            continue
        if not isinstance(team, str) or not team.strip():
            continue
        team_u = team.strip().upper()
        if want is not None and team_u not in want:
            continue
        key = (player.strip(), team_u)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)

    # stable sort by team then player
    out.sort(key=lambda x: (x[1], x[0]))
    return out


def _fmt_num(x: Optional[float], width: int = 5, prec: int = 1) -> str:
    if x is None:
        return " " * width
    return f"{x:>{width}.{prec}f}"


def _compute_composites(mu: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    pts = mu.get("points")
    reb = mu.get("rebounds")
    ast = mu.get("assists")
    stl = mu.get("steals")
    blk = mu.get("blocks")

    if pts is not None and reb is not None and ast is not None:
        out["pra"] = pts + reb + ast
    if pts is not None and reb is not None:
        out["pr"] = pts + reb
    if pts is not None and ast is not None:
        out["pa"] = pts + ast
    if reb is not None and ast is not None:
        out["ra"] = reb + ast
    if stl is not None and blk is not None:
        out["stl+blk"] = stl + blk

    return out


def _pick_best_window_value(row: PlayerRow, stat: str) -> Optional[float]:
    """Prefer season, then L10, then L5 for role tagging."""
    if stat in row.mu_season:
        return row.mu_season.get(stat)
    if stat in row.mu_l10:
        return row.mu_l10.get(stat)
    if stat in row.mu_l5:
        return row.mu_l5.get(stat)
    return row.mu.get(stat)


def _player_specialist_tags(row: PlayerRow) -> List[str]:
    """Return short specialist tags for the player.

    Tags:
      - 3P: strong 3PM volume shooter
      - BLK: block specialist
      - STL: steal specialist
            - TO: turnover-prone (risk)
      - ISO: iso-ish / on-ball scorer heuristic (not true iso rate)
    """
    tags: List[str] = []

    pts = _pick_best_window_value(row, "points")
    ast = _pick_best_window_value(row, "assists")
    threes = _pick_best_window_value(row, "3pm")
    stl = _pick_best_window_value(row, "steals")
    blk = _pick_best_window_value(row, "blocks")
    tov = _pick_best_window_value(row, "turnovers")

    # 3PM specialist
    if isinstance(threes, (int, float)):
        if threes >= TAG_THRESHOLDS["3P_ELITE"]:
            tags.append("3P")
        elif threes >= TAG_THRESHOLDS["3P_GOOD"]:
            tags.append("3P")

    # Stocks specialists
    if isinstance(blk, (int, float)):
        if blk >= TAG_THRESHOLDS["BLK_GOOD"]:
            tags.append("BLK")
    if isinstance(stl, (int, float)):
        if stl >= TAG_THRESHOLDS["STL_GOOD"]:
            tags.append("STL")

    # Turnovers (risk)
    if isinstance(tov, (int, float)):
        if tov >= TAG_THRESHOLDS["TOV_HIGH"]:
            tags.append("TO")
        elif tov >= TAG_THRESHOLDS["TOV_MED"] and "ISO" not in tags:
            # medium TO only matters when player is a primary handler (heuristic below)
            pass

    # ISO-ish heuristic:
    # High scoring + lower assists tends to correlate with isolation/self-creation load.
    # This is not play-type data, but it helps flag coach/rotation sensitivity.
    if isinstance(pts, (int, float)) and isinstance(ast, (int, float)):
        if pts >= TAG_THRESHOLDS["ISO_PTS"] and ast <= TAG_THRESHOLDS["ISO_AST_MAX"]:
            tags.append("ISO")
            if isinstance(tov, (int, float)) and tov >= TAG_THRESHOLDS["TOV_MED"] and "TO" not in tags:
                tags.append("TO")

    # Keep ordering stable for scanability
    order = {"3P": 1, "BLK": 2, "STL": 3, "ISO": 4, "TO": 5}
    tags.sort(key=lambda t: order.get(t, 999))
    return tags


def _fmt_tags(tags: List[str], width: int = 10) -> str:
    if not tags:
        return "".ljust(width)
    s = "/".join(tags)
    if len(s) > width:
        s = s[: max(0, width - 1)] + "…"
    return f"{s:<{width}}"


def _build_rows(
    players: Iterable[Tuple[str, str]], 
    overlay: Dict[Tuple[str, str], Tuple[float, float]],
    series: Dict[Tuple[str, str], List[float]] = None
) -> List[PlayerRow]:
    series = series or {}
    rows: List[PlayerRow] = []
    
    for player, team in players:
        mu: Dict[str, float] = {}
        sigma: Dict[str, float] = {}
        mu_l5: Dict[str, float] = {}
        mu_l10: Dict[str, float] = {}
        mu_season: Dict[str, float] = {}
        player_series: Dict[str, List[float]] = {}
        
        for stat in BASE_STATS:
            # Blended average (current methodology)
            if (player, stat) in overlay:
                m, s = overlay[(player, stat)]
                mu[stat] = m
                sigma[stat] = s
            
            # Compute L5, L10, Season from series if available
            if (player, stat) in series:
                vals = series[(player, stat)]
                player_series[stat] = vals
                
                if len(vals) >= 5:
                    mu_l5[stat] = float(np.mean(vals[:5]))
                elif len(vals) > 0:
                    mu_l5[stat] = float(np.mean(vals))
                
                if len(vals) >= 10:
                    mu_l10[stat] = float(np.mean(vals[:10]))
                elif len(vals) > 0:
                    mu_l10[stat] = float(np.mean(vals))
                
                if len(vals) > 0:
                    mu_season[stat] = float(np.mean(vals))
        
        # Compute composites for each window
        mu.update(_compute_composites(mu))
        mu_l5.update(_compute_composites(mu_l5))
        mu_l10.update(_compute_composites(mu_l10))
        mu_season.update(_compute_composites(mu_season))
        
        rows.append(PlayerRow(
            player=player, 
            team=team, 
            mu=mu, 
            sigma=sigma,
            mu_l5=mu_l5,
            mu_l10=mu_l10,
            mu_season=mu_season,
            series=player_series
        ))
    return rows


def _render_team(rows: List[PlayerRow], team: str, *, include_sigma: bool, show_out_players: bool = False) -> str:
    team_rows = [r for r in rows if r.team == team]
    
    # Separate by injury status
    active_rows = [r for r in team_rows if r.injury_status not in ["Out", "Injured Reserve"]]
    out_rows = [r for r in team_rows if r.injury_status in ["Out", "Injured Reserve"]]
    questionable_rows = [r for r in team_rows if r.injury_status in ["Questionable", "Doubtful", "Day-To-Day"]]

    # sort by points mu desc (fallback 0)
    active_rows.sort(key=lambda r: (r.mu.get("points", 0.0)), reverse=True)

    TAG_W = 10
    header = (
        f"{'PLAYER':<22} {'TAGS':<{TAG_W}} {'STATUS':<8} {'WINDOW':<7} "
        f"{'PTS':>6} {'REB':>6} {'AST':>6} {'3PM':>6} {'STL':>6} {'BLK':>6} {'PRA':>8}"
    )
    rule = "=" * len(header)
    sep = "-" * len(header)

    lines: List[str] = []
    lines.append(f"\n{team} (players in slate: {len(team_rows)}, active: {len(active_rows)}, OUT: {len(out_rows)})")
    lines.append(rule)
    lines.append(header)
    lines.append(rule)
    
    # Show OUT players first with warning
    if out_rows:
        for r in out_rows:
            detail = f" ({r.injury_detail})" if r.injury_detail else ""
            tags = _fmt_tags(_player_specialist_tags(r), width=TAG_W)
            lines.append(
                f"{('❌ ' + r.player):<22} {tags} {'OUT':<8} {'---':<7} "
                f"{'---':>6} {'---':>6} {'---':>6} {'---':>6} {'---':>5} {'---':>5} {'---':>7} {detail}"
            )
        lines.append(sep)
    
    # Show Questionable/GTD players with warning flag
    for r in [r for r in active_rows if r.injury_status in ["Questionable", "Doubtful", "Day-To-Day"]]:
        status_icon = "⚠️ " if r.injury_status in ["Questionable", "Doubtful", "Day-To-Day"] else ""
        detail = f" ({r.injury_detail})" if r.injury_detail else ""
        status_display = r.injury_status[:7] if len(r.injury_status) > 7 else r.injury_status
        tags = _fmt_tags(_player_specialist_tags(r), width=TAG_W)
        
        # L5 row
        lines.append(
            f"{(status_icon + r.player):<22} {tags} {status_display:<8} {'L5':<7} "
            f"{_fmt_num(r.mu_l5.get('points')):>6} "
            f"{_fmt_num(r.mu_l5.get('rebounds')):>6} "
            f"{_fmt_num(r.mu_l5.get('assists')):>6} "
            f"{_fmt_num(r.mu_l5.get('3pm')):>6} "
            f"{_fmt_num(r.mu_l5.get('steals')):>5} "
            f"{_fmt_num(r.mu_l5.get('blocks')):>5} "
            f"{_fmt_num(r.mu_l5.get('pra'), width=7):>7}{detail}"
        )
        # L10 row
        lines.append(
            f"{'':<22} {'':<{TAG_W}} {'':<8} {'L10':<7} "
            f"{_fmt_num(r.mu_l10.get('points')):>6} "
            f"{_fmt_num(r.mu_l10.get('rebounds')):>6} "
            f"{_fmt_num(r.mu_l10.get('assists')):>6} "
            f"{_fmt_num(r.mu_l10.get('3pm')):>6} "
            f"{_fmt_num(r.mu_l10.get('steals')):>5} "
            f"{_fmt_num(r.mu_l10.get('blocks')):>5} "
            f"{_fmt_num(r.mu_l10.get('pra'), width=7):>7}"
        )
        # Season row
        lines.append(
            f"{'':<22} {'':<{TAG_W}} {'':<8} {'SEASON':<7} "
            f"{_fmt_num(r.mu_season.get('points')):>6} "
            f"{_fmt_num(r.mu_season.get('rebounds')):>6} "
            f"{_fmt_num(r.mu_season.get('assists')):>6} "
            f"{_fmt_num(r.mu_season.get('3pm')):>6} "
            f"{_fmt_num(r.mu_season.get('steals')):>5} "
            f"{_fmt_num(r.mu_season.get('blocks')):>5} "
            f"{_fmt_num(r.mu_season.get('pra'), width=7):>7}"
        )
        lines.append(sep)
    
    # Show healthy/active players
    for r in [r for r in active_rows if r.injury_status not in ["Questionable", "Doubtful", "Day-To-Day"]]:
        tags = _fmt_tags(_player_specialist_tags(r), width=TAG_W)
        # L5 row
        lines.append(
            f"{r.player:<22} {tags} {'Active':<8} {'L5':<7} "
            f"{_fmt_num(r.mu_l5.get('points')):>6} "
            f"{_fmt_num(r.mu_l5.get('rebounds')):>6} "
            f"{_fmt_num(r.mu_l5.get('assists')):>6} "
            f"{_fmt_num(r.mu_l5.get('3pm')):>6} "
            f"{_fmt_num(r.mu_l5.get('steals')):>5} "
            f"{_fmt_num(r.mu_l5.get('blocks')):>5} "
            f"{_fmt_num(r.mu_l5.get('pra'), width=7):>7}"
        )
        # L10 row
        lines.append(
            f"{'':<22} {'':<{TAG_W}} {'':<8} {'L10':<7} "
            f"{_fmt_num(r.mu_l10.get('points')):>6} "
            f"{_fmt_num(r.mu_l10.get('rebounds')):>6} "
            f"{_fmt_num(r.mu_l10.get('assists')):>6} "
            f"{_fmt_num(r.mu_l10.get('3pm')):>6} "
            f"{_fmt_num(r.mu_l10.get('steals')):>5} "
            f"{_fmt_num(r.mu_l10.get('blocks')):>5} "
            f"{_fmt_num(r.mu_l10.get('pra'), width=7):>7}"
        )
        # Season row
        lines.append(
            f"{'':<22} {'':<{TAG_W}} {'':<8} {'SEASON':<7} "
            f"{_fmt_num(r.mu_season.get('points')):>6} "
            f"{_fmt_num(r.mu_season.get('rebounds')):>6} "
            f"{_fmt_num(r.mu_season.get('assists')):>6} "
            f"{_fmt_num(r.mu_season.get('3pm')):>6} "
            f"{_fmt_num(r.mu_season.get('steals')):>5} "
            f"{_fmt_num(r.mu_season.get('blocks')):>5} "
            f"{_fmt_num(r.mu_season.get('pra'), width=7):>7}"
        )
        lines.append(sep)

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Roster-style per-player averages for teams in a slate")
    ap.add_argument("--slate", required=True, help="Path to slate JSON (e.g., slates/CLE_PHI_....json)")
    ap.add_argument("--teams", default="CLE,PHI", help="Comma-separated team abbreviations to include")
    ap.add_argument("--cache", default="", help="Optional path to a specific stats_cache json")
    ap.add_argument(
        "--cache-only",
        action="store_true",
        help="Only use existing stats cache (no live NBA API calls).",
    )
    ap.add_argument(
        "--force-live",
        action="store_true",
        help="Force live NBA API refresh (may be slow).",
    )
    ap.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail if any slate player is missing required stats (prevents blank tables).",
    )
    ap.add_argument("--include-sigma", action="store_true", help="Also include sigma snapshot in report")
    ap.add_argument("--out", default="", help="Optional output path (txt)")
    ap.add_argument("--skip-injury-check", action="store_true", help="Skip ESPN injury status check")
    ap.add_argument("--show-out-players", action="store_true", help="Include OUT players in full report")

    args = ap.parse_args()

    slate_path = (PROJECT_ROOT / args.slate).resolve() if not Path(args.slate).is_absolute() else Path(args.slate)
    if not slate_path.exists():
        raise SystemExit(f"Slate not found: {slate_path}")

    slate_raw = _read_json(slate_path)
    
    # Handle both list format (array of picks) and dict format (with metadata)
    if isinstance(slate_raw, list):
        date_iso = ""
    else:
        date_iso = str(slate_raw.get("date", "")).strip()
    
    # Try to infer date from filename if not in JSON (e.g., "..._20260117.json")
    if not date_iso:
        import re
        match = re.search(r'(\d{8})', slate_path.name)
        if match:
            raw_date = match.group(1)
            date_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    
    if not date_iso:
        # Fallback to today's date
        date_iso = date.today().isoformat()
        print(f"[WARN] No date found, using today: {date_iso}")

    # Accept both comma-separated ("CLE,PHI") and whitespace-separated ("CLE PHI") team lists.
    import re
    teams = [t.strip().upper() for t in re.split(r"[\s,]+", str(args.teams).strip()) if t.strip()]

    slate_players = _players_from_slate(slate_path, teams=teams)
    
    if not slate_players:
        print(f"[ERROR] No players found in slate for teams: {teams}")
        raise SystemExit(1)
    
    print(f"[INFO] Found {len(slate_players)} players for teams: {', '.join(teams)}")

    try:
        from nba_active_players import ACTIVE_NBA_PLAYERS
    except ImportError:
        ACTIVE_NBA_PLAYERS = set()
    # Prefer cached stats for speed/reliability (menu UX).
    overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
    series: Dict[Tuple[str, str], List[float]] = {}
    cache_path: Optional[Path] = None

    # NOTE: nba stats cache is generated per *run day* (today). If the slate date differs,
    # we still prefer to use today's cache unless an explicit cache path is provided.
    cache_date_iso = date.today().isoformat()

    if args.cache:
        cache_path = (PROJECT_ROOT / args.cache).resolve() if not Path(args.cache).is_absolute() else Path(args.cache)
    else:
        cache_path = _find_cache_for_date(cache_date_iso) or _find_cache_for_date(date_iso)

    if cache_path and cache_path.exists():
        try:
            overlay, _team_map, series = _load_cache(cache_path)
            players_with_data = len(set(p for p, _s in overlay.keys()))
            print(f"[INFO] Loaded cache: {cache_path.name} (players with data: {players_with_data})")
        except Exception as e:
            print(f"[WARN] Could not load cache {cache_path}: {e}")
            overlay, series = {}, {}
            cache_path = None

    # Ensure cache completeness (hydrate missing players without clobbering existing cache).
    all_player_names = [p for p, _t in slate_players]
    if not args.cache_only:
        try:
            from stats_last10_cache import ensure_daily_last10_mu_sigma

            result = ensure_daily_last10_mu_sigma(
                players=all_player_names,
                required_stats=BASE_STATS,
                season="2025-26",
                last_n_games=10,
                short_n_games=5,
                mode="blend",
                blend_weight=0.65,
                force_live_missing=bool(args.force_live),
            )

            overlay = result.overlay or overlay
            series = result.series or series

            # Prefer today's cache path for metadata after ensure
            cache_path = _find_cache_for_date(cache_date_iso) or cache_path

            if result.warnings:
                for w in result.warnings[:5]:
                    print(f"[WARN] {w}")
        except Exception as e:
            print(f"[WARN] Could not ensure cache completeness: {e}")

    missing = _missing_players(
        slate_players,
        overlay=overlay,
        series=series,
        required_stats=BASE_STATS,
    )

    if missing:
        print(f"[WARN] Missing required stats for {len(missing)}/{len(slate_players)} players")
        if args.require_complete:
            sample = list(missing.items())[:8]
            detail = "; ".join([f"{p}({','.join(stats[:4])}{'…' if len(stats) > 4 else ''})" for p, stats in sample])
            print(f"[ERROR] Incomplete cache: {detail}")
            print("[HINT] Re-run with --force-live, or run the daily cache refresh first.")
            raise SystemExit(2)

    rows = _build_rows(slate_players, overlay, series)
    
    # Fetch injury status from ESPN
    injury_map: Dict[str, Tuple[str, str]] = {}  # player -> (status, detail)
    if not args.skip_injury_check:
        print("[INFO] Checking ESPN injury reports...")
        try:
            from ufa.ingest.espn_nba_context import check_slate_injuries
            injury_results = check_slate_injuries(slate_players)
            for player, inj in injury_results.items():
                injury_map[player] = (inj.status, inj.injury_type or "")
            
            # Count issues
            out_count = sum(1 for p, (s, d) in injury_map.items() if s in ["Out", "Injured Reserve"])
            gtd_count = sum(1 for p, (s, d) in injury_map.items() if s in ["Questionable", "Doubtful", "Day-To-Day"])
            if out_count > 0:
                print(f"[WARN] {out_count} player(s) are OUT")
            if gtd_count > 0:
                print(f"[INFO] {gtd_count} player(s) are Questionable/GTD")
        except Exception as e:
            print(f"[WARN] Could not check injury status: {e}")
    
    # Apply injury status to rows
    for row in rows:
        if row.player in injury_map:
            row.injury_status, row.injury_detail = injury_map[row.player]

    report_lines: List[str] = []
    cache_info = str(cache_path) if cache_path else ("Cache-only (no cache found)" if args.cache_only else "Live/Ensure-cache")
    report_lines.append(f"Roster Averages Report (L5 / L10 / Season)\nDate: {date_iso}\nTeams: {', '.join(teams)}\nCache: {cache_info}\n")
    report_lines.append("NOTE: 'Roster' = players present in the slate file (not full 15-man roster).")
    report_lines.append("      L5 = Last 5 games, L10 = Last 10 games, SEASON = Full season average")
    report_lines.append("      ❌ = OUT (ruled out), ⚠️ = Questionable/GTD (game-time decision)\n")
    report_lines.append("TAGS: 3P=3pt volume shooter, BLK=block specialist, STL=steal specialist, TO=turnover risk, ISO=iso-ish (heuristic).")
    report_lines.append("      Coaching/role awareness: tags can flip fast with rotation/usage changes, pace, opponent scheme, and foul trouble.\n")

    for team in teams:
        report_lines.append(_render_team(rows, team, include_sigma=bool(args.include_sigma), show_out_players=bool(args.show_out_players)))

    report = "\n".join(report_lines).rstrip() + "\n"

    if args.out:
        out_path = (PROJECT_ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    else:
        out_path = PROJECT_ROOT / "outputs" / f"{teams[0]}_{teams[1]}_roster_averages_{date_iso.replace('-', '')}.txt"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
