import argparse
import json
import os
from collections import Counter
from typing import Optional, List, Dict, Any


DEFAULT_SIGNALS_PATH = 'outputs/signals_latest.json'


def _find_latest_nba_risk_first_file() -> Optional[str]:
    """Best-effort: find the most recent NBA RISK_FIRST json in outputs/.

    Looks for files like:
      - NBA*_RISK_FIRST_*FROM_UD.json
      - ODDSAPI_NBA_*_RISK_FIRST_*FROM_UD.json
    Returns absolute path or None if nothing found.
    """
    import glob

    patterns = [
        os.path.join('outputs', '*NBA*RISK_FIRST*FROM_UD.json'),
        os.path.join('outputs', '*NBA*_RISK_FIRST_*.json'),
    ]

    candidates = []
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))

    if not candidates:
        return None

    # Pick the newest by mtime
    latest = max(candidates, key=os.path.getmtime)
    return latest


def summarize_direction_balance(path: Optional[str] = None):
    # Prefer explicit path; fall back to default; then auto-detect latest NBA file.
    target_path = path or DEFAULT_SIGNALS_PATH

    if not os.path.exists(target_path):
        auto_path = _find_latest_nba_risk_first_file()
        if auto_path is None:
            print(
                "No NBA signals file found. "
                "Expected either outputs/signals_latest.json or an NBA *_RISK_FIRST_* file."
            )
            return
        print(f"signals_latest.json not found; using latest NBA risk-first file: {auto_path}")
        target_path = auto_path

    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {target_path}: {e}")
        return

    # If the file is a dict with a key containing the picks, try to find it
    if isinstance(data, dict):
        # Try common keys for edge lists
        for key in ['edges', 'signals', 'picks', 'data']:
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # Some of the RISK_FIRST files are already a flat list under a sport key
            # or use a generic container. As a fallback, look for the first list value.
            list_value = None
            for value in data.values():
                if isinstance(value, list):
                    list_value = value
                    break
            data = list_value or []

    directions = [edge.get('direction') for edge in data if 'direction' in edge]
    counts = Counter(directions)
    total = sum(counts.values())
    if total == 0:
        print("No picks found in the file.")
        return

    print(f"Total picks: {total}")
    for direction in ['higher', 'lower']:
        count = counts.get(direction, 0)
        pct = (count / total) * 100
        print(f"{direction.title()}: {count} ({pct:.1f}%)")
    print("\nDirection mix (higher vs lower):")

    # --- Per-stat breakdown ---
    by_market = {}
    for edge in data:
        direction = edge.get('direction')
        if direction not in ('higher', 'lower'):
            continue
        market = edge.get('market') or edge.get('stat') or 'UNKNOWN'
        stats_entry = by_market.setdefault(market, Counter())
        stats_entry[direction] += 1

    if by_market:
        print("\nPer-stat direction mix (all markets):")
        # Sort markets by total picks descending
        sorted_markets = sorted(
            by_market.items(),
            key=lambda kv: kv[1]['higher'] + kv[1]['lower'],
            reverse=True,
        )
        for market, mc in sorted_markets:
            total_mkt = mc['higher'] + mc['lower']
            higher_ct = mc['higher']
            lower_ct = mc['lower']
            higher_pct = (higher_ct / total_mkt) * 100 if total_mkt else 0.0
            lower_pct = (lower_ct / total_mkt) * 100 if total_mkt else 0.0
            print(
                f"  {market}: total={total_mkt}, "
                f"Higher={higher_ct} ({higher_pct:.1f}%), "
                f"Lower={lower_ct} ({lower_pct:.1f}%)"
            )


def list_top_overs(data: List[Dict[str, Any]], top_n: int = 20) -> None:
    """Print top-N 'higher' picks by probability.

    Expects each edge dict to have at least:
      - 'direction'
      - 'probability' (0-1)
      - 'player', 'stat', 'line' (for display)
    """
    overs = [e for e in data if e.get('direction') == 'higher' and 'probability' in e]
    if not overs:
        print("\nNo 'higher' picks with probability found in this file.")
        return

    overs_sorted = sorted(overs, key=lambda e: e['probability'], reverse=True)

    print(f"\nTop {min(top_n, len(overs_sorted))} OVER picks by probability:")
    for edge in overs_sorted[:top_n]:
        player = edge.get('player', 'Unknown')
        stat = edge.get('stat') or edge.get('market', '?')
        line = edge.get('line', '?')
        prob = edge.get('probability', 0.0) * 100
        tier = edge.get('tier', '')
        tier_str = f" | Tier: {tier}" if tier else ""
        print(f"  {player} — {stat} {line} HIGHER | {prob:.1f}%{tier_str}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize NBA over/under direction balance overall and by stat type. "
            "Defaults to outputs/signals_latest.json or latest NBA *_RISK_FIRST_* file."
        )
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="file",
        help=(
            "Path to a specific NBA risk-first JSON file (e.g., "
            "outputs/NBA6PMMOND_RISK_FIRST_20260209_FROM_UD.json)."
        ),
    )
    parser.add_argument(
        "-n",
        "--top-n",
        dest="top_n",
        type=int,
        default=0,
        help="If >0, also print the top-N OVER (higher) picks by probability.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    # Load file once via summarize_direction_balance (for counts)
    summarize_direction_balance(path=args.file)

    if args.top_n and args.top_n > 0:
        # Reload raw data to feed to list_top_overs
        target_path = args.file or DEFAULT_SIGNALS_PATH
        if not os.path.exists(target_path):
            auto_path = _find_latest_nba_risk_first_file()
            if auto_path is None:
                # Nothing to do
                raise SystemExit(0)
            target_path = auto_path
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            raise SystemExit(0)

        if isinstance(data, dict):
            for key in ['edges', 'signals', 'picks', 'data', 'results']:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                list_value = None
                for value in data.values():
                    if isinstance(value, list):
                        list_value = value
                        break
                data = list_value or []

        if isinstance(data, list):
            list_top_overs(data, top_n=args.top_n)
