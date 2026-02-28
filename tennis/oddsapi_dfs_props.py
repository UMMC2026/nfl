"""tennis/oddsapi_dfs_props.py

Odds API (no-scrape) ingestion for TENNIS DFS-style *player props*.

Why this exists
- Underdog / PrizePicks / Pick6 props are sometimes exposed via The Odds API under
  regions=us_dfs.
- Tennis coverage varies a lot by tournament and by day. This module is built to:
  1) Try ingestion safely (no-scrape)
  2) Persist a timestamped raw slate artifact for audit
  3) If props exist, run the calibrated Tennis Abstract Monte Carlo analyzer
  4) Export governed quant artifacts so Telegram/parlays can treat signals as truth.

Important limitations
- The Odds API does NOT guarantee tennis DFS player-prop coverage.
- Sleeper is not an Odds API bookmaker key (so you cannot get Sleeper lines from Odds API).

Config
- ODDS_API_KEY
- ODDS_API_TENNIS_ATP_SPORT_KEY / ODDS_API_TENNIS_WTA_SPORT_KEY (tournament-specific)
- ODDS_API_TENNIS_DFS_REGIONS (default us_dfs)
- ODDS_API_TENNIS_DFS_BOOKMAKERS (default prizepicks,underdog)
- ODDS_API_TENNIS_DFS_MARKETS (default player_aces,player_double_faults,...)

"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Load .env from project root (best-effort). This is required for Odds API
# ingestion when launching from menus/terminal where env vars may not be preloaded.
try:
    from dotenv import load_dotenv  # type: ignore

    _PROJECT_ROOT = Path(__file__).resolve().parents[1]
    _ENV_PATH = _PROJECT_ROOT / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass


def _try_import_odds_api():
    """Best-effort import of the Odds API adapter from src/sources/odds_api.py."""
    try:
        project_root = Path(__file__).resolve().parents[1]
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from sources.odds_api import (  # type: ignore
            OddsApiError,
            oddsapi_fetch_player_props,
            oddsapi_sport_key_for_tag,
        )

        return OddsApiError, oddsapi_fetch_player_props, oddsapi_sport_key_for_tag
    except Exception:
        return None


def _split_csv(s: str) -> List[str]:
    return [t.strip() for t in (s or "").split(",") if t.strip()]


def _infer_opponent(player: str, raw: Dict[str, Any]) -> str:
    home = str(raw.get("home_team") or "").strip()
    away = str(raw.get("away_team") or "").strip()
    p = str(player or "").strip().lower()

    # For "Player1 vs Player2" match names (total_games), parse directly
    if " vs " in str(player):
        parts = str(player).split(" vs ", 1)
        if len(parts) == 2:
            return parts[1].strip()

    if home and away:
        if p == home.strip().lower():
            return away
        if p == away.strip().lower():
            return home
        # If we can't match by string equality, still provide context.
        return f"{home} vs {away}"

    return ""


def ingest_oddsapi_tennis_dfs_props(
    *,
    tour: str = "WTA",
    max_events: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Path]:
    """Ingest tennis DFS player props via Odds API and write a raw artifact."""

    imported = _try_import_odds_api()
    if not imported:
        raise RuntimeError("Odds API adapter import failed (expected src/sources/odds_api.py)")

    OddsApiError, oddsapi_fetch_player_props, oddsapi_sport_key_for_tag = imported

    tour_u = (tour or "WTA").strip().upper()
    if tour_u not in {"ATP", "WTA"}:
        raise ValueError("tour must be ATP or WTA")

    sport_tag = "TENNIS_ATP" if tour_u == "ATP" else "TENNIS_WTA"
    sport_key = oddsapi_sport_key_for_tag(sport_tag)
    if not sport_key:
        raise RuntimeError(
            "Missing tennis Odds API sport_key mapping. Set ODDS_API_TENNIS_ATP_SPORT_KEY / "
            "ODDS_API_TENNIS_WTA_SPORT_KEY in .env"
        )

    regions = (os.getenv("ODDS_API_TENNIS_DFS_REGIONS") or os.getenv("ODDS_API_REGIONS") or "us_dfs").strip()
    bookmakers_s = (os.getenv("ODDS_API_TENNIS_DFS_BOOKMAKERS") or os.getenv("ODDS_API_BOOKMAKERS") or "").strip()
    markets_s = (os.getenv("ODDS_API_TENNIS_DFS_MARKETS") or "player_aces,player_double_faults,player_games_won,player_sets_won").strip()

    bookmakers = tuple(_split_csv(bookmakers_s)) if bookmakers_s else None
    markets = tuple(_split_csv(markets_s))

    props, meta = oddsapi_fetch_player_props(
        sport="TENNIS",
        sport_key=sport_key,
        regions=regions,
        markets=markets,
        bookmakers=bookmakers,
        max_events=max_events,
    )

    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = outputs_dir / f"oddsapi_tennis_dfs_props_raw_{tour_u.lower()}_{ts}.json"
    latest_path = outputs_dir / "oddsapi_tennis_dfs_props_raw_latest.json"

    payload = {
        "sport": "TENNIS",
        "tour": tour_u,
        "ingested_at": datetime.utcnow().isoformat() + "Z",
        "sport_key": sport_key,
        "regions": regions,
        "bookmakers": list(bookmakers) if bookmakers else None,
        "markets": list(markets),
        "total_props": len(props),
        "props": props,
        "meta": meta,
    }

    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return props, meta, raw_path


def ingest_oddsapi_tennis_match_markets(
    *,
    tour: str = "WTA",
    max_events: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Path]:
    """Ingest tennis MATCH-LEVEL markets (totals, spreads) via Odds API.

    The Odds API does NOT support tennis player props (player_aces, etc.)
    on any region as of Feb 2026. However, match-level totals (total games
    over/under) and spreads (game handicap) ARE available on US sportsbooks.

    This function fetches those markets and converts them into the standard
    prop format for downstream analysis by the tennis pipeline.
    """

    imported = _try_import_odds_api()
    if not imported:
        raise RuntimeError("Odds API adapter import failed (expected src/sources/odds_api.py)")

    OddsApiError, _, oddsapi_sport_key_for_tag = imported

    from src.sources.odds_api import OddsApiClient

    tour_u = (tour or "WTA").strip().upper()
    if tour_u not in {"ATP", "WTA"}:
        raise ValueError("tour must be ATP or WTA")

    sport_tag = "TENNIS_ATP" if tour_u == "ATP" else "TENNIS_WTA"
    sport_key = oddsapi_sport_key_for_tag(sport_tag)
    if not sport_key:
        raise RuntimeError(
            "Missing tennis Odds API sport_key mapping. Set ODDS_API_TENNIS_ATP_SPORT_KEY / "
            "ODDS_API_TENNIS_WTA_SPORT_KEY in .env"
        )

    client = OddsApiClient.from_env()
    if client is None:
        raise RuntimeError("ODDS_API_KEY is not set")

    # Fetch events list
    events, q_events = client.get_events(sport_key=sport_key)
    if max_events is not None:
        events = events[: max(0, int(max_events))]

    props: List[Dict[str, Any]] = []
    raw_event_odds: List[Dict[str, Any]] = []
    markets_to_fetch = "totals,spreads,h2h"
    region = "us"  # US sportsbooks have totals+spreads for tennis

    import time
    for ev in events:
        event_id = ev.get("id")
        if not event_id:
            continue

        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        commence = ev.get("commence_time", "")

        # Fetch each market SEPARATELY — combined requests can hide bookmakers
        # that only support a subset of markets (e.g., bovada has totals but
        # DraftKings only has h2h; combined request may omit bovada's totals).
        for single_market in ["totals", "spreads"]:
            try:
                odds_json, _ = client.get_event_odds(
                    sport_key=sport_key,
                    event_id=str(event_id),
                    regions=region,
                    markets=single_market,
                )
            except Exception:
                continue

            raw_event_odds.append(odds_json)

            # Use first bookmaker that has this market
            for bm in odds_json.get("bookmakers", []) or []:
                bm_key = bm.get("key", "")
                for mkt in bm.get("markets", []) or []:
                    mkt_key = mkt.get("key", "")
                    for outcome in mkt.get("outcomes", []) or []:
                        name = str(outcome.get("name") or "").strip()
                        point = outcome.get("point")
                        price = outcome.get("price")

                        if mkt_key == "totals" and point is not None:
                            # Total games over/under
                            direction = "higher" if name.lower() == "over" else "lower"
                            props.append({
                                "platform": "oddsapi",
                                "sport": "TENNIS",
                                "player": f"{home} vs {away}",
                                "stat": "total_games",
                                "line": float(point),
                                "direction": direction,
                                "raw": {
                                    "event_id": event_id,
                                    "commence_time": commence,
                                    "home_team": home,
                                    "away_team": away,
                                    "bookmaker_key": bm_key,
                                    "market_key": mkt_key,
                                    "price": price,
                                },
                            })

                        elif mkt_key == "spreads" and point is not None:
                            # Game handicap per player
                            direction = "higher" if float(point) > 0 else "lower"
                            props.append({
                                "platform": "oddsapi",
                                "sport": "TENNIS",
                                "player": name,  # Player name from spread
                                "stat": "game_spread",
                                "line": float(point),
                                "direction": direction,
                                "raw": {
                                    "event_id": event_id,
                                    "commence_time": commence,
                                    "home_team": home,
                                    "away_team": away,
                                    "bookmaker_key": bm_key,
                                    "market_key": mkt_key,
                                    "price": price,
                                    "opponent": away if name == home else home,
                                },
                            })

                break  # Use first bookmaker per market to avoid duplicates

        time.sleep(float(os.getenv("ODDS_API_PACE_S") or "0.15"))

    # Deduplicate: keep one entry per (player, stat, line, direction)
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for p in props:
        key = (p["player"], p["stat"], p["line"], p["direction"])
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    props = deduped

    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = outputs_dir / f"oddsapi_tennis_match_markets_{tour_u.lower()}_{ts}.json"
    latest_path = outputs_dir / "oddsapi_tennis_match_markets_latest.json"

    meta: Dict[str, Any] = {
        "sport": "TENNIS",
        "tour": tour_u,
        "sport_key": sport_key,
        "regions": region,
        "markets": markets_to_fetch,
        "event_count": len(events),
        "props_extracted": len(props),
        "quota": {
            "remaining": q_events.remaining,
            "used": q_events.used,
        },
    }

    payload = {
        "sport": "TENNIS",
        "tour": tour_u,
        "ingested_at": datetime.utcnow().isoformat() + "Z",
        "sport_key": sport_key,
        "regions": region,
        "markets": markets_to_fetch,
        "total_props": len(props),
        "props": props,
        "meta": meta,
    }

    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return props, meta, raw_path


def analyze_ingested_props(
    props: List[Dict[str, Any]],
    *,
    surface: str = "Hard",
    source_label: str = "oddsapi_dfs",
) -> Dict[str, Any]:
    """Run calibrated Monte Carlo analysis over the ingested props."""

    from tennis.calibrated_props_engine import CalibratedTennisPropsEngine

    engine = CalibratedTennisPropsEngine()
    try:
        slate: List[Dict[str, Any]] = []
        for p in props or []:
            player = p.get("player")
            stat = p.get("stat")
            line = p.get("line")
            direction = p.get("direction")
            raw = (p.get("raw") or {}) if isinstance(p.get("raw"), dict) else {}

            if not (player and stat and line is not None and direction):
                continue

            slate.append(
                {
                    "player": player,
                    "stat": stat,
                    "line": float(line),
                    "direction": direction,
                    "opponent": _infer_opponent(str(player), raw),
                }
            )

        results = engine.analyze_slate(slate, surface=str(surface or "Hard"))
        # Attach provenance (safe additive fields)
        results["_source"] = {
            "ingest": source_label,
            "surface": surface,
        }

        # Enrich edges with factual narratives (AI optional via DEEPSEEK_API_KEY)
        try:
            from tennis.tennis_ai_narrative import enrich_edges_with_narrative
            use_ai = bool(os.getenv("DEEPSEEK_API_KEY"))
            edges = results.get("results") or results.get("edges") or []
            enrich_edges_with_narrative(edges, use_ai=use_ai)
        except Exception:
            pass

        return results
    finally:
        try:
            engine.close()
        except Exception:
            pass


def write_analysis_artifacts(results: Dict[str, Any]) -> Dict[str, Path]:
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = outputs_dir / f"oddsapi_tennis_dfs_props_analysis_{ts}.json"
    latest_path = outputs_dir / "oddsapi_tennis_dfs_props_analysis_latest.json"

    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"analysis": out_path, "latest": latest_path}


def export_governed_signals(results: Dict[str, Any]) -> None:
    """Export governed signals so downstream (Telegram/MC) can treat them as truth."""

    try:
        from tennis.tennis_quant_export import export_tennis_props_quant_artifacts

        export_tennis_props_quant_artifacts(
            results,
            source=(results or {}).get("_source") or {"ingest": "oddsapi_dfs"},
        )
    except Exception as e:
        print(f"\n⚠️ Quant export skipped/failed: {e}")


def interactive_run() -> None:
    print("\n" + "=" * 70)
    print("TENNIS ODDS API (NO SCRAPE)")
    print("=" * 70)
    print("Ingests tennis lines from Odds API. Tries DFS player props first,")
    print("then falls back to match-level markets (total games, spreads).")

    tour = (input("Tour [ATP/WTA] (default WTA): ").strip() or "WTA").upper()
    surface = (input("Surface [Hard/Clay/Grass/Indoor] (default Hard): ").strip() or "Hard")
    max_events_s = input("Max events (blank = ALL events): ").strip()
    max_events = int(max_events_s) if max_events_s else None

    # === STEP 1: Try DFS player props (usually returns 0 for tennis) ===
    props: List[Dict[str, Any]] = []
    raw_path: Optional[Path] = None
    try:
        props, meta, raw_path = ingest_oddsapi_tennis_dfs_props(tour=tour, max_events=max_events)
        print(f"\n  DFS player props check: {len(props)} found")
    except Exception as e:
        print(f"\n  DFS props check failed: {e}")

    # === STEP 2: Fall back to match-level markets (totals/spreads) ===
    if not props:
        print("\n  Player props not available -- fetching match-level markets (totals/spreads)...")
        try:
            props, meta, raw_path = ingest_oddsapi_tennis_match_markets(tour=tour, max_events=max_events)
            print(f"  Saved: {raw_path}")
            print(f"  Match-level props: {len(props)}")

            if props:
                total_games = [p for p in props if p.get("stat") == "total_games"]
                spreads = [p for p in props if p.get("stat") == "game_spread"]
                n_matches = len(total_games) // 2 if total_games else 0
                print(f"\n  Total games lines: {n_matches} matches")
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
            print(f"\n  Match markets also failed: {e}")
            input("\nPress Enter to continue...")
            return

    if not props:
        print("\n  0 props from both player props and match markets.")
        print("  Tournament may not have odds posted yet.")
        input("\nPress Enter to continue...")
        return

    # === STEP 3: Analyze ===
    results = analyze_ingested_props(props, surface=surface, source_label="oddsapi_tennis")
    paths = write_analysis_artifacts(results)
    print(f"\n  Analysis saved: {paths['analysis']}")

    export_governed_signals(results)
    input("\nPress Enter to continue...")


if __name__ == "__main__":
    interactive_run()
