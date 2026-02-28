"""
Odds API Auto-Resolve — Fetch completed game scores to resolve picks.

Uses the /v4/sports/{sport}/scores endpoint to get final scores,
then matches against unresolved picks in calibration_history.csv.

Usage:
    python tools/odds_api_resolve.py --sport NBA
    python tools/odds_api_resolve.py --sport NBA --days 2 --dry-run
    python tools/odds_api_resolve.py --sport NHL --days 1

NOTE: This resolves game-level outcomes (moneyline, totals, spreads).
      Player prop resolution still requires box-score data (nba_api, ESPN, etc.).
      For player props, this module flags games as COMPLETED so the main
      resolve pipeline knows which games to fetch box scores for.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sources.odds_api import OddsApiClient, oddsapi_sport_key_for_tag, OddsApiError

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

CALIBRATION_FILE = ROOT / "calibration_history.csv"
COMPLETED_GAMES_DIR = ROOT / "outputs" / "scores"
COMPLETED_GAMES_DIR.mkdir(parents=True, exist_ok=True)

# Stat types that are game-level (can be resolved from final scores)
GAME_LEVEL_STATS = {
    "moneyline", "ml", "spread", "puck_line", "puckline",
    "total", "totals", "over_under", "game_total",
}

# ─────────────────────────────────────────────────────────────────
# Score Fetching
# ─────────────────────────────────────────────────────────────────

def fetch_completed_scores(
    sport_tag: str,
    days_from: int = 1,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch completed game scores from The Odds API.

    Args:
        sport_tag: Sport tag (NBA, NHL, NFL, etc.)
        days_from: How many days back to look (1-3).

    Returns:
        (completed_games, meta_dict)
    """
    client = OddsApiClient.from_env()
    if not client:
        print("[ERROR] ODDS_API_KEY not configured in .env")
        return [], {}

    sport_key = oddsapi_sport_key_for_tag(sport_tag)
    if not sport_key:
        print(f"[ERROR] No Odds API sport key for '{sport_tag}'")
        return [], {}

    print(f"[SCORES] Fetching scores for {sport_key} (last {days_from} day(s))...")
    try:
        scores, quota = client.get_scores(sport_key=sport_key, days_from=days_from)
    except OddsApiError as e:
        print(f"[ERROR] Odds API error: {e}")
        return [], {}

    # Separate completed vs. in-progress
    completed = [g for g in scores if g.get("completed")]
    in_progress = [g for g in scores if not g.get("completed") and g.get("scores")]
    upcoming = [g for g in scores if not g.get("completed") and not g.get("scores")]

    meta = {
        "sport_key": sport_key,
        "days_from": days_from,
        "total_events": len(scores),
        "completed": len(completed),
        "in_progress": len(in_progress),
        "upcoming": len(upcoming),
        "quota_remaining": getattr(quota, "remaining", None),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    print(f"[SCORES] {len(completed)} completed, {len(in_progress)} live, {len(upcoming)} upcoming")
    if quota and quota.remaining is not None:
        print(f"[QUOTA]  Remaining: {quota.remaining} | Used: {quota.used}")

    return completed, meta


def parse_final_score(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a completed game into a structured result.

    Returns:
        {
            "event_id": str,
            "home_team": str,
            "away_team": str,
            "home_score": int,
            "away_score": int,
            "total": int,
            "winner": str,  # home_team or away_team name
            "commence_time": str,
            "completed": True,
        }
    """
    if not game.get("completed"):
        return None

    scores_list = game.get("scores") or []
    if len(scores_list) < 2:
        return None

    home = game.get("home_team", "")
    away = game.get("away_team", "")

    # Build score lookup by team name
    score_map: Dict[str, int] = {}
    for s in scores_list:
        name = s.get("name", "")
        try:
            score_map[name] = int(s.get("score", 0))
        except (ValueError, TypeError):
            score_map[name] = 0

    home_score = score_map.get(home, 0)
    away_score = score_map.get(away, 0)

    return {
        "event_id": game.get("id", ""),
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "total": home_score + away_score,
        "winner": home if home_score > away_score else away,
        "commence_time": game.get("commence_time", ""),
        "completed": True,
    }


# ─────────────────────────────────────────────────────────────────
# Pick Resolution
# ─────────────────────────────────────────────────────────────────

def resolve_game_level_picks(
    completed_games: List[Dict[str, Any]],
    unresolved_picks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Resolve game-level picks (moneyline, totals, spreads) against final scores.

    Returns list of resolved pick dicts ready for calibration update.
    """
    # Build lookup: team → game result
    results_by_team: Dict[str, Dict[str, Any]] = {}
    for game in completed_games:
        parsed = parse_final_score(game)
        if not parsed:
            continue
        results_by_team[parsed["home_team"].lower()] = parsed
        results_by_team[parsed["away_team"].lower()] = parsed

    resolved = []
    for pick in unresolved_picks:
        stat = (pick.get("stat") or "").lower().replace(" ", "_")
        if stat not in GAME_LEVEL_STATS:
            continue

        team = (pick.get("team") or "").lower()
        opponent = (pick.get("opponent") or "").lower()

        # Try to match by team or opponent name
        game_result = results_by_team.get(team) or results_by_team.get(opponent)
        if not game_result:
            continue

        # Determine result
        actual_value = None
        hit = None
        line = float(pick.get("line", 0))
        direction = (pick.get("direction") or "").lower()

        if stat in {"moneyline", "ml"}:
            winner = game_result["winner"].lower()
            hit = (winner == team)
            actual_value = 1. if hit else 0.

        elif stat in {"total", "totals", "over_under", "game_total"}:
            actual_value = float(game_result["total"])
            if direction in {"higher", "over", "o"}:
                hit = actual_value > line
            else:
                hit = actual_value < line

        elif stat in {"spread", "puck_line", "puckline"}:
            # Spread: team_score - opponent_score vs. spread line
            if team == game_result["home_team"].lower():
                margin = game_result["home_score"] - game_result["away_score"]
            else:
                margin = game_result["away_score"] - game_result["home_score"]
            actual_value = float(margin)
            # For spread picks, "higher" means covers
            hit = (margin + line) > 0 if direction in {"higher", "over"} else (margin + line) < 0

        if actual_value is not None and hit is not None:
            resolved.append({
                **pick,
                "actual_value": actual_value,
                "outcome": "hit" if hit else "miss",
                "resolved_via": "odds_api_scores",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            })

    return resolved


# ─────────────────────────────────────────────────────────────────
# Completed-Game Flag File (for player-prop resolvers)
# ─────────────────────────────────────────────────────────────────

def save_completed_games(
    sport_tag: str,
    completed_games: List[Dict[str, Any]],
) -> Path:
    """Write completed games to a JSON flag file.

    Downstream player-prop resolvers (resolve_picks.py, etc.) can read this
    to know which games are final before fetching box scores.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = COMPLETED_GAMES_DIR / f"{sport_tag.lower()}_completed_{ts}.json"

    results = []
    for g in completed_games:
        parsed = parse_final_score(g)
        if parsed:
            results.append(parsed)

    payload = {
        "sport": sport_tag.upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "games": results,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[SAVED] {len(results)} completed games → {out_path}")
    return out_path


def load_unresolved_picks(sport: str) -> List[Dict[str, Any]]:
    """Load unresolved picks from calibration_history.csv for a given sport."""
    if not CALIBRATION_FILE.exists():
        print(f"[WARN] {CALIBRATION_FILE} not found")
        return []

    unresolved = []
    with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            league = (row.get("league") or "").strip().lower()
            if league != sport.lower():
                continue
            outcome = (row.get("outcome") or "").strip().lower()
            if outcome in {"hit", "miss"}:
                continue  # already resolved
            unresolved.append(row)

    return unresolved


# ─────────────────────────────────────────────────────────────────
# Main Pipeline
# ─────────────────────────────────────────────────────────────────

def run_auto_resolve(
    sport_tag: str = "NBA",
    days_from: int = 1,
    dry_run: bool = False,
    resolve_game_level: bool = True,
    save_flag_file: bool = True,
) -> Dict[str, Any]:
    """Full auto-resolve pipeline.

    1. Fetch completed scores from Odds API
    2. Save completed-games flag file (for downstream resolvers)
    3. Resolve game-level picks (moneyline, totals, spreads)
    4. Report results

    Returns:
        Summary dict.
    """
    print(f"\n{'='*60}")
    print(f"  ODDS API AUTO-RESOLVE — {sport_tag.upper()}")
    print(f"{'='*60}\n")

    # Step 1: Fetch scores
    completed, meta = fetch_completed_scores(sport_tag, days_from=days_from)
    if not completed:
        print("[INFO] No completed games found.")
        return {"status": "no_games", "meta": meta}

    # Step 2: Save flag file
    flag_path = None
    if save_flag_file:
        flag_path = save_completed_games(sport_tag, completed)

    # Step 3: Display completed games
    print(f"\n--- Completed Games ({len(completed)}) ---")
    for g in completed:
        parsed = parse_final_score(g)
        if parsed:
            print(f"  {parsed['away_team']} {parsed['away_score']}  @  "
                  f"{parsed['home_team']} {parsed['home_score']}  "
                  f"(Total: {parsed['total']})")

    # Step 4: Resolve game-level picks
    resolved_count = 0
    if resolve_game_level:
        unresolved = load_unresolved_picks(sport_tag)
        print(f"\n[RESOLVE] Found {len(unresolved)} unresolved {sport_tag} picks")

        game_resolved = resolve_game_level_picks(completed, unresolved)
        resolved_count = len(game_resolved)

        if game_resolved:
            if dry_run:
                print(f"\n[DRY RUN] Would resolve {resolved_count} game-level picks:")
                for r in game_resolved:
                    print(f"  {r.get('outcome','?').upper()}: {r.get('player','')} "
                          f"{r.get('stat','')} {r.get('direction','')} {r.get('line','')} "
                          f"→ actual: {r.get('actual_value','')}")
            else:
                # TODO: Write resolved picks back to calibration_history.csv
                print(f"\n[RESOLVED] {resolved_count} game-level picks")
                for r in game_resolved:
                    print(f"  {r.get('outcome','?').upper()}: {r.get('player','')} "
                          f"{r.get('stat','')} {r.get('direction','')} {r.get('line','')} "
                          f"→ actual: {r.get('actual_value','')}")
        else:
            print("[INFO] No game-level picks to resolve (most picks are player props)")

    # Summary
    summary = {
        "status": "ok",
        "sport": sport_tag.upper(),
        "completed_games": len(completed),
        "resolved_picks": resolved_count,
        "flag_file": str(flag_path) if flag_path else None,
        "dry_run": dry_run,
        "meta": meta,
    }

    print(f"\n--- Summary ---")
    print(f"  Completed games:  {summary['completed_games']}")
    print(f"  Resolved picks:   {summary['resolved_picks']}")
    print(f"  Quota remaining:  {meta.get('quota_remaining', '?')}")
    if flag_path:
        print(f"  Flag file:        {flag_path}")

    return summary


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Odds API Auto-Resolve")
    parser.add_argument("--sport", default="NBA", help="Sport tag (NBA, NHL, NFL, etc.)")
    parser.add_argument("--days", type=int, default=1, help="Days back to fetch (1-3)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--no-flag", action="store_true", help="Skip saving flag file")
    args = parser.parse_args()

    result = run_auto_resolve(
        sport_tag=args.sport,
        days_from=min(args.days, 3),
        dry_run=args.dry_run,
        save_flag_file=not args.no_flag,
    )

    if result.get("status") == "no_games":
        print("\nNo completed games to process.")


if __name__ == "__main__":
    main()
