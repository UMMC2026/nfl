"""golf/oddsapi_golf_ingest.py

Odds API (no-scrape) ingestion for **golf outright-winner** markets
and (where available) DFS player props.

Coverage:
- Outrights (winner) for 4 majors: Masters, PGA Championship, US Open, The Open
- DFS player props (round strokes, birdies, etc.) are NOT currently on Odds API
  for golf — those still come through paste / PrizePicks / Underdog.

Flow:
  1. Fetch outrights via /v4/sports/{key}/odds?markets=outrights
  2. Convert American/decimal odds → implied win probability
  3. Produce repo-style prop dicts compatible with golf edge generator
  4. Write timestamped artifacts for audit

Config (.env):
  ODDS_API_KEY              — required
  ODDS_API_GOLF_SPORT_KEY   — optional (passthrough for generic GOLF tag)
  ODDS_API_GOLF_REGIONS     — default: us
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Load .env from project root
try:
    from dotenv import load_dotenv  # type: ignore

    _PROJECT_ROOT = Path(__file__).resolve().parents[1]
    _ENV_PATH = _PROJECT_ROOT / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass

# Ensure repo imports work
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

GOLF_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = GOLF_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Odds API imports ────────────────────────────────────────────────

def _import_odds_api():
    try:
        from sources.odds_api import (
            OddsApiClient,
            OddsApiError,
            oddsapi_sport_key_for_tag,
        )
        return OddsApiClient, OddsApiError, oddsapi_sport_key_for_tag
    except Exception:
        return None


# ── Odds → Probability Conversion ──────────────────────────────────

def american_odds_to_implied_prob(odds: float) -> float:
    """Convert American odds to implied probability (0-1).

    Positive odds (e.g., +2500): prob = 100 / (odds + 100)
    Negative odds (e.g., -150):  prob = abs(odds) / (abs(odds) + 100)
    """
    if odds > 0:
        return 100.0 / (odds + 100.0)
    elif odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        return 0.5


def decimal_odds_to_implied_prob(odds: float) -> float:
    """Convert decimal odds to implied probability (0-1)."""
    if odds <= 0:
        return 0.0
    return 1.0 / odds


# ── Golf-specific sport key listing ────────────────────────────────

GOLF_TOURNAMENT_KEYS = {
    "golf_masters_tournament_winner": "The Masters",
    "golf_pga_championship_winner": "PGA Championship",
    "golf_us_open_winner": "US Open",
    "golf_the_open_championship_winner": "The Open Championship",
}


def list_available_golf_tournaments() -> List[Dict[str, Any]]:
    """Return active golf tournaments from Odds API."""
    imported = _import_odds_api()
    if not imported:
        return []

    OddsApiClient, OddsApiError, _ = imported
    client = OddsApiClient.from_env()
    if not client:
        return []

    try:
        sports, _ = client.list_sports()
    except Exception:
        return []

    result = []
    for s in sports:
        key = s.get("key", "")
        if key in GOLF_TOURNAMENT_KEYS or key.startswith("golf_"):
            result.append({
                "key": key,
                "title": s.get("title", GOLF_TOURNAMENT_KEYS.get(key, key)),
                "active": s.get("active", False),
                "has_outrights": s.get("has_outrights", False),
            })
    return result


# ── Outrights Ingestion ────────────────────────────────────────────

def ingest_golf_outrights(
    *,
    sport_key: str = "golf_masters_tournament_winner",
    regions: str = "",
    bookmakers: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Path]:
    """Fetch golf outright winner odds and produce repo-style prop dicts.

    Returns: (props, meta, raw_artifact_path)
    """
    imported = _import_odds_api()
    if not imported:
        raise RuntimeError("Odds API adapter import failed")

    OddsApiClient, OddsApiError, _ = imported
    client = OddsApiClient.from_env()
    if not client:
        raise RuntimeError("Missing ODDS_API_KEY")

    if not regions:
        regions = (os.getenv("ODDS_API_GOLF_REGIONS") or os.getenv("ODDS_API_REGIONS") or "us").strip()

    tournament_name = GOLF_TOURNAMENT_KEYS.get(sport_key, sport_key)

    # Outrights are a "featured" market → use the /odds endpoint
    odds_data, quota = client.get_odds(
        sport_key=sport_key,
        regions=regions,
        markets="outrights",
        odds_format="american",
        bookmakers=bookmakers,
    )

    props: List[Dict[str, Any]] = []
    raw_outcomes: List[Dict[str, Any]] = []

    for event in odds_data:
        event_id = event.get("id", "")
        commence_time = event.get("commence_time")

        for bookmaker in event.get("bookmakers", []):
            bk_key = bookmaker.get("key", "")
            bk_title = bookmaker.get("title", bk_key)

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                if market_key != "outrights":
                    continue

                for outcome in market.get("outcomes", []):
                    player = (outcome.get("name") or "").strip()
                    odds_val = outcome.get("price")

                    if not player or odds_val is None:
                        continue

                    implied_prob = american_odds_to_implied_prob(float(odds_val))

                    raw_outcomes.append({
                        "player": player,
                        "odds": odds_val,
                        "implied_prob": round(implied_prob, 6),
                        "bookmaker": bk_key,
                    })

                    props.append({
                        "platform": "oddsapi",
                        "sport": "GOLF",
                        "player": player,
                        "stat": "outright_winner",
                        "market": "outright_winner",
                        "line": 1,  # "finish position = 1"
                        "direction": "better",
                        "probability": round(implied_prob, 4),
                        "odds_american": odds_val,
                        "tournament": tournament_name,
                        "raw": {
                            "event_id": event_id,
                            "commence_time": commence_time,
                            "bookmaker_key": bk_key,
                            "bookmaker_title": bk_title,
                            "market_key": market_key,
                        },
                    })

    # Deduplicate: keep best odds per player (highest implied prob = shortest odds)
    best_by_player: Dict[str, Dict[str, Any]] = {}
    for p in props:
        player = p["player"]
        if player not in best_by_player or p["probability"] > best_by_player[player]["probability"]:
            best_by_player[player] = p
    deduped_props = sorted(best_by_player.values(), key=lambda x: x["probability"], reverse=True)

    # Write raw artifact
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tournament_slug = sport_key.replace("golf_", "").replace("_winner", "")
    raw_path = OUTPUTS_DIR / f"oddsapi_golf_outrights_{tournament_slug}_{ts}.json"
    latest_path = OUTPUTS_DIR / "oddsapi_golf_outrights_latest.json"

    payload = {
        "sport": "GOLF",
        "sport_key": sport_key,
        "tournament": tournament_name,
        "ingested_at": datetime.utcnow().isoformat() + "Z",
        "regions": regions,
        "total_outcomes": len(raw_outcomes),
        "unique_players": len(deduped_props),
        "props": deduped_props,
        "all_outcomes": raw_outcomes,
        "quota": {
            "remaining": getattr(quota, "remaining", None),
            "used": getattr(quota, "used", None),
            "last_cost": getattr(quota, "last_cost", None),
        },
    }

    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    meta = {
        "sport_key": sport_key,
        "tournament": tournament_name,
        "regions": regions,
        "event_count": len(odds_data),
        "total_outcomes": len(raw_outcomes),
        "unique_players": len(deduped_props),
    }

    return deduped_props, meta, raw_path


# ── Display / Reporting ────────────────────────────────────────────

def display_outrights_table(props: List[Dict[str, Any]], *, top_n: int = 30) -> None:
    """Pretty-print golf outright odds table."""
    tournament = (props[0]["tournament"] if props else "Unknown")
    print(f"\n{'='*65}")
    print(f"⛳ GOLF OUTRIGHTS — {tournament}")
    print(f"{'='*65}")
    print(f"{'#':>3}  {'Player':<30}  {'Odds':>8}  {'Impl.Prob':>9}")
    print(f"{'-'*3}  {'-'*30}  {'-'*8}  {'-'*9}")

    for i, p in enumerate(props[:top_n], 1):
        player = p["player"][:30]
        odds = p.get("odds_american", "?")
        prob = p.get("probability", 0)

        odds_str = f"+{odds}" if isinstance(odds, (int, float)) and odds > 0 else str(odds)
        print(f"{i:>3}  {player:<30}  {odds_str:>8}  {prob:>8.1%}")

    if len(props) > top_n:
        print(f"\n  ... and {len(props) - top_n} more players")

    # Summary
    total_prob = sum(p.get("probability", 0) for p in props)
    print(f"\n  Total implied probability (vig included): {total_prob:.1%}")
    print(f"  Overround: {(total_prob - 1.0) * 100:.1f}%")


# ── Interactive CLI ────────────────────────────────────────────────

def interactive_run() -> None:
    """Interactive golf Odds API ingest from command line or menu."""
    print("\n" + "=" * 65)
    print("⛳ GOLF ODDS API — READABLE REPORTS")
    print("=" * 65)
    
    print("\nSelect Report Type:")
    print("  [1] 📊 Outrights (Tournament Winner)")
    print("  [2] 🥊 Matchups (Head-to-Head)")
    print("  [3] 📈 All Markets (Outrights + Matchups)")
    print("  [4] ⚙️  Convert to Props (for pipeline)")
    print("  [0] 🚪 Cancel")
    
    report_choice = input("\nChoice: ").strip()
    
    if report_choice == "0":
        return
    
    # Check API key
    from dotenv import load_dotenv
    load_dotenv(override=False)
    
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key or api_key == "PUT_YOUR_TOKEN_HERE":
        print("\n❌ ODDS_API_KEY not configured")
        print("   Set ODDS_API_KEY in .env file")
        print("   Get your key at: https://the-odds-api.com/")
        input("\nPress Enter to continue...")
        return
    
    # Import the new parser
    try:
        from golf.ingest.odds_api_parser import (
            fetch_and_convert_majors,
            generate_readable_report,
            parse_outrights,
            parse_matchups,
            fetch_golf_odds,
            get_best_outright_odds,
        )
    except ImportError as e:
        print(f"\n❌ Failed to import odds_api_parser: {e}")
        input("\nPress Enter to continue...")
        return
    
    # Show available tournaments
    print("\nAvailable golf tournaments on Odds API:")
    tournaments = list_available_golf_tournaments()

    if not tournaments:
        print("  No active golf tournaments found.")
        print("  Odds API currently lists majors only (Masters, PGA, US Open, The Open).")
        print("\nTrying all 4 majors anyway...")
        tournaments = [
            {"key": "golf_masters_tournament", "title": "The Masters", "active": False},
            {"key": "golf_pga_championship", "title": "PGA Championship", "active": False},
            {"key": "golf_us_open", "title": "US Open", "active": False},
            {"key": "golf_the_open_championship", "title": "The Open Championship", "active": False},
        ]

    for i, t in enumerate(tournaments, 1):
        status = "✓ Active" if t.get("active") else "✗ Inactive"
        print(f"  [{i}] {t['title']:<40} ({status})")

    print(f"  [A] All active tournaments")
    print(f"  [0] Cancel")

    choice = input("\nSelect tournament: ").strip()
    if choice == "0":
        return

    selected_keys: List[str] = []

    if choice.upper() == "A":
        selected_keys = [t["key"] for t in tournaments]
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tournaments):
                selected_keys = [tournaments[idx]["key"]]
            else:
                print("Invalid selection")
                return
        except ValueError:
            # Allow direct sport_key input
            selected_keys = [choice.strip()]

    # Fetch based on report choice
    all_outrights = []
    all_matchups = []
    all_props = []
    
    for key in selected_keys:
        try:
            print(f"\n[FETCHING] {key}...")
            
            if report_choice in ["1", "3", "4"]:
                # Fetch outrights
                odds_data = fetch_golf_odds(
                    api_key=api_key,
                    sport_key=key,
                    markets="outrights",
                )
                if odds_data:
                    outrights = parse_outrights(odds_data)
                    all_outrights.extend(outrights)
                    print(f"  ✓ Found {len(outrights)} outrights")
            
            if report_choice in ["2", "3"]:
                # Fetch matchups
                odds_data = fetch_golf_odds(
                    api_key=api_key,
                    sport_key=key,
                    markets="h2h",
                )
                if odds_data:
                    matchups = parse_matchups(odds_data)
                    all_matchups.extend(matchups)
                    print(f"  ✓ Found {len(matchups)} matchups")
                    
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Generate readable report
    if report_choice in ["1", "2", "3"]:
        report = generate_readable_report(all_outrights, all_matchups)
        print("\n" + report)
        
        # Save report
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = OUTPUTS_DIR / f"golf_odds_api_report_{ts}.txt"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n✓ Report saved → {report_path.name}")
    
    # Convert to props
    if report_choice == "4":
        from golf.ingest.odds_api_parser import convert_to_finishing_position_props
        props = convert_to_finishing_position_props(all_outrights)
        
        print(f"\n✓ Converted {len(props)} outrights → finishing_position props")
        
        # Save props
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        props_path = OUTPUTS_DIR / f"golf_odds_api_props_{ts}.json"
        props_path.write_text(
            json.dumps({"props": props, "count": len(props)}, indent=2),
            encoding="utf-8"
        )
        print(f"✓ Props saved → {props_path.name}")
        
        # Preview first 5
        print("\n[PREVIEW] First 5 props:")
        for prop in props[:5]:
            player = prop['player']
            odds = prop.get('odds', 0)
            mult = prop.get('better_mult', 0)
            print(f"  {player:<30} {odds:>+5} → {mult:.2f}x")

    if not all_outrights and not all_matchups:
        print("\n⚠️ 0 markets returned. Check your ODDS_API_KEY and that tournaments are active.")

    input("\nPress Enter to continue...")


if __name__ == "__main__":
    interactive_run()
