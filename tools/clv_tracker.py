"""
Closing Line Value (CLV) Tracker — Measure edge quality over time.

Uses The Odds API /v4/historical/sports/{sport}/odds endpoint to fetch
closing-line snapshots and compare them against the model's predicted
probabilities at pick time.

**Why CLV matters**: If our model consistently beats closing lines,
the edge is real (not noise).  CLV > 0 across 100+ picks = sharp model.

Usage:
    python tools/clv_tracker.py --sport NBA --date 2026-02-18
    python tools/clv_tracker.py --sport NHL --date 2026-02-18 --market player_points
    python tools/clv_tracker.py --report

Quota cost:
    - /historical/odds: 1 per market × region combo (~cheap for h2h/totals)
    - /historical/events/{id}/odds: 10× multiplier (EXPENSIVE — not used by default)
"""

import argparse
import csv
import json
import math
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

CLV_DIR = ROOT / "outputs" / "clv"
CLV_DIR.mkdir(parents=True, exist_ok=True)

CLV_HISTORY_FILE = CLV_DIR / "clv_history.csv"
CLV_HISTORY_FIELDS = [
    "date", "sport", "event_id", "player", "stat", "line",
    "direction", "model_prob", "market_prob_open", "market_prob_close",
    "clv_pct", "bookmaker", "market_key", "fetched_at",
]

# ─────────────────────────────────────────────────────────────────
# Odds ↔ Probability Conversion
# ─────────────────────────────────────────────────────────────────

def american_to_implied_prob(odds: float) -> float:
    """Convert American odds to implied probability (0-1 range, no vig removal)."""
    if odds == 0:
        return 0.50
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)


def decimal_to_implied_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if odds <= 0:
        return 0.50
    return 1.0 / odds


# ─────────────────────────────────────────────────────────────────
# Historical Odds Fetching
# ─────────────────────────────────────────────────────────────────

def fetch_closing_odds(
    sport_tag: str,
    date_iso: str,
    markets: str = "h2h,totals",
    regions: str = "us",
    bookmakers: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch historical odds snapshot closest to game time.

    Args:
        sport_tag: Sport tag (NBA, NHL, etc.)
        date_iso: ISO-8601 datetime string for the snapshot
        markets: comma-sep market keys
        regions: regions filter
        bookmakers: optional bookmaker filter

    Returns:
        (list_of_event_odds, meta)
    """
    client = OddsApiClient.from_env()
    if not client:
        print("[ERROR] ODDS_API_KEY not configured in .env")
        return [], {}

    sport_key = oddsapi_sport_key_for_tag(sport_tag)
    if not sport_key:
        print(f"[ERROR] No Odds API sport key for '{sport_tag}'")
        return [], {}

    print(f"[CLV] Fetching historical odds for {sport_key} @ {date_iso}")
    print(f"      Markets: {markets} | Regions: {regions}")

    try:
        data, quota = client.get_historical_odds(
            sport_key=sport_key,
            regions=regions,
            date=date_iso,
            markets=markets,
            bookmakers=bookmakers,
        )
    except OddsApiError as e:
        print(f"[ERROR] Odds API error: {e}")
        return [], {}

    events = data.get("data", [])
    meta = {
        "sport_key": sport_key,
        "snapshot_timestamp": data.get("timestamp"),
        "previous_timestamp": data.get("previous_timestamp"),
        "next_timestamp": data.get("next_timestamp"),
        "events_returned": len(events),
        "quota_remaining": getattr(quota, "remaining", None),
    }

    print(f"[CLV] Got {len(events)} events | Snapshot: {data.get('timestamp', '?')}")
    if quota and quota.remaining is not None:
        print(f"[QUOTA] Remaining: {quota.remaining}")

    return events, meta


# ─────────────────────────────────────────────────────────────────
# CLV Calculation
# ─────────────────────────────────────────────────────────────────

def extract_market_odds(
    events: List[Dict[str, Any]],
    target_bookmakers: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Extract odds from historical snapshot into a lookup structure.

    Returns:
        {
            "event_id": {
                "home_team": str,
                "away_team": str,
                "h2h": {"home_prob": float, "away_prob": float, "bookmaker": str},
                "totals": {"over_line": float, "over_prob": float, "under_prob": float},
                ...
            }
        }
    """
    result: Dict[str, Dict[str, Any]] = {}

    for event in events:
        eid = event.get("id", "")
        entry: Dict[str, Any] = {
            "home_team": event.get("home_team", ""),
            "away_team": event.get("away_team", ""),
        }

        for bm in event.get("bookmakers", []):
            bm_key = bm.get("key", "")
            if target_bookmakers and bm_key not in target_bookmakers:
                continue

            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                outcomes = market.get("outcomes", [])

                if mkey == "h2h":
                    for o in outcomes:
                        price = o.get("price", 0)
                        prob = american_to_implied_prob(price)
                        name = o.get("name", "")
                        if name == event.get("home_team"):
                            entry.setdefault("h2h", {})["home_prob"] = prob
                            entry["h2h"]["bookmaker"] = bm_key
                        elif name == event.get("away_team"):
                            entry.setdefault("h2h", {})["away_prob"] = prob
                            entry["h2h"]["bookmaker"] = bm_key

                elif mkey == "totals":
                    for o in outcomes:
                        price = o.get("price", 0)
                        point = o.get("point", 0)
                        prob = american_to_implied_prob(price)
                        side = (o.get("name") or "").lower()
                        entry.setdefault("totals", {})["line"] = point
                        entry["totals"]["bookmaker"] = bm_key
                        if side == "over":
                            entry["totals"]["over_prob"] = prob
                        elif side == "under":
                            entry["totals"]["under_prob"] = prob

                elif mkey == "spreads":
                    for o in outcomes:
                        price = o.get("price", 0)
                        point = o.get("point", 0)
                        prob = american_to_implied_prob(price)
                        name = o.get("name", "")
                        entry.setdefault("spreads", {})["bookmaker"] = bm_key
                        if name == event.get("home_team"):
                            entry["spreads"]["home_line"] = point
                            entry["spreads"]["home_prob"] = prob
                        elif name == event.get("away_team"):
                            entry["spreads"]["away_line"] = point
                            entry["spreads"]["away_prob"] = prob

        if entry.get("h2h") or entry.get("totals") or entry.get("spreads"):
            result[eid] = entry

    return result


def compute_clv(
    model_prob: float,
    market_close_prob: float,
) -> float:
    """Compute CLV as percentage edge over closing line.

    CLV = model_prob - market_close_prob

    Positive = our model had an edge the market didn't price in.
    """
    return model_prob - market_close_prob


# ─────────────────────────────────────────────────────────────────
# CLV History Persistence
# ─────────────────────────────────────────────────────────────────

def append_clv_records(records: List[Dict[str, Any]], dry_run: bool = False):
    """Append CLV records to history CSV."""
    if not records:
        return

    if dry_run:
        print(f"[DRY RUN] Would append {len(records)} CLV records to {CLV_HISTORY_FILE}")
        return

    file_exists = CLV_HISTORY_FILE.exists()
    with open(CLV_HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLV_HISTORY_FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(records)

    print(f"[CLV] Appended {len(records)} records to {CLV_HISTORY_FILE}")


# ─────────────────────────────────────────────────────────────────
# CLV Report
# ─────────────────────────────────────────────────────────────────

def generate_clv_report() -> Dict[str, Any]:
    """Generate aggregate CLV report from history."""
    if not CLV_HISTORY_FILE.exists():
        print("[WARN] No CLV history found. Run tracking first.")
        return {}

    records: List[Dict[str, Any]] = []
    with open(CLV_HISTORY_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["clv_pct"] = float(row.get("clv_pct", 0))
                row["model_prob"] = float(row.get("model_prob", 0))
                row["market_prob_close"] = float(row.get("market_prob_close", 0))
                records.append(row)
            except (ValueError, TypeError):
                continue

    if not records:
        print("[WARN] No valid CLV records found.")
        return {}

    # Overall stats
    clv_values = [r["clv_pct"] for r in records]
    avg_clv = sum(clv_values) / len(clv_values)
    positive_clv = sum(1 for c in clv_values if c > 0)

    # By sport
    by_sport: Dict[str, List[float]] = {}
    for r in records:
        sport = r.get("sport", "UNK")
        by_sport.setdefault(sport, []).append(r["clv_pct"])

    # By direction
    by_dir: Dict[str, List[float]] = {}
    for r in records:
        d = (r.get("direction") or "").lower()
        by_dir.setdefault(d, []).append(r["clv_pct"])

    print(f"\n{'='*60}")
    print(f"  CLOSING LINE VALUE (CLV) REPORT")
    print(f"{'='*60}")
    print(f"\n  Total Picks Tracked:  {len(records)}")
    print(f"  Average CLV:          {avg_clv:+.2f}%")
    print(f"  CLV > 0 (sharp):      {positive_clv}/{len(records)} "
          f"({100*positive_clv/len(records):.1f}%)")

    if len(clv_values) >= 2:
        variance = sum((c - avg_clv) ** 2 for c in clv_values) / len(clv_values)
        std = math.sqrt(variance)
        print(f"  CLV Std Dev:          {std:.2f}%")

    print(f"\n  --- By Sport ---")
    for sport, vals in sorted(by_sport.items()):
        sport_avg = sum(vals) / len(vals)
        sport_pos = sum(1 for v in vals if v > 0)
        print(f"  {sport:>8s}: avg CLV {sport_avg:+.2f}% | "
              f"{sport_pos}/{len(vals)} sharp ({100*sport_pos/len(vals):.0f}%)")

    if by_dir:
        print(f"\n  --- By Direction ---")
        for d, vals in sorted(by_dir.items()):
            d_avg = sum(vals) / len(vals)
            print(f"  {d:>8s}: avg CLV {d_avg:+.2f}% ({len(vals)} picks)")

    report = {
        "total_picks": len(records),
        "avg_clv": avg_clv,
        "positive_clv_pct": 100 * positive_clv / len(records) if records else 0,
        "by_sport": {s: sum(v) / len(v) for s, v in by_sport.items()},
    }
    return report


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CLV Tracker — Closing Line Value Analysis")
    parser.add_argument("--sport", default="NBA", help="Sport tag (NBA, NHL, NFL...)")
    parser.add_argument("--date", help="Date for historical snapshot (YYYY-MM-DD or ISO-8601)")
    parser.add_argument("--markets", default="h2h,totals", help="Comma-sep market keys")
    parser.add_argument("--regions", default="us", help="Regions (us, us_dfs, etc.)")
    parser.add_argument("--report", action="store_true", help="Show aggregate CLV report")
    parser.add_argument("--dry-run", action="store_true", help="Don't write records")
    args = parser.parse_args()

    if args.report:
        generate_clv_report()
        return

    if not args.date:
        # Default: yesterday at noon UTC
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        args.date = yesterday.strftime("%Y-%m-%dT12:00:00Z")
    elif len(args.date) == 10:
        # Convert YYYY-MM-DD to ISO-8601 with noon UTC
        args.date = f"{args.date}T12:00:00Z"

    events, meta = fetch_closing_odds(
        sport_tag=args.sport,
        date_iso=args.date,
        markets=args.markets,
        regions=args.regions,
    )

    if not events:
        print("[INFO] No historical odds data returned.")
        return

    # Extract and display
    odds_map = extract_market_odds(events)
    print(f"\n--- Closing Lines ({len(odds_map)} events) ---")
    for eid, edata in odds_map.items():
        home = edata.get("home_team", "?")
        away = edata.get("away_team", "?")
        print(f"\n  {away} @ {home}")

        if "h2h" in edata:
            h = edata["h2h"]
            print(f"    ML: {home} {h.get('home_prob', 0):.1%} | "
                  f"{away} {h.get('away_prob', 0):.1%} "
                  f"[{h.get('bookmaker', '?')}]")

        if "totals" in edata:
            t = edata["totals"]
            print(f"    Total: {t.get('line', '?')} | "
                  f"Over {t.get('over_prob', 0):.1%} / "
                  f"Under {t.get('under_prob', 0):.1%} "
                  f"[{t.get('bookmaker', '?')}]")

        if "spreads" in edata:
            s = edata["spreads"]
            print(f"    Spread: {home} {s.get('home_line', '?')} ({s.get('home_prob', 0):.1%}) | "
                  f"{away} {s.get('away_line', '?')} ({s.get('away_prob', 0):.1%}) "
                  f"[{s.get('bookmaker', '?')}]")

    print(f"\n[INFO] To compare against model predictions, load picks from calibration_history.csv")
    print(f"       and compute CLV = model_prob - closing_prob for each matching pick.")


if __name__ == "__main__":
    main()
