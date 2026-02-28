"""Generate L10 form patches from Sackmann match CSVs.

This script reads Jeff Sackmann-style ATP/WTA match CSVs from
`tennis/data/` and produces per-player L10 patches compatible with the
`l10_form_engine` + `TennisStatsAPI` patch lane.

Usage (examples):
    python tennis/scripts/generate_l10_patches_from_sackmann.py
    python tennis/scripts/generate_l10_patches_from_sackmann.py --year 2024 --window 10
    python tennis/scripts/generate_l10_patches_from_sackmann.py --surface HARD
    python tennis/scripts/generate_l10_patches_from_sackmann.py --dry-run

The output is written to:
    tennis/stats_cache/l10_patches/{Player_Name}.json

Schema per player:
    {
        "player": "Jannik Sinner",
        "surface": "HARD" | "ALL",
        "matches_used": 10,
        "last_match_date": "20240101",
        "metrics": {
            "aces": [...],
            "double_faults": [...],
            "games_won": [...],
            "total_games": [...],
            "sets_won": [...],
            "sets_played": [...],
            "tiebreakers": [...]
        }
    }

`TennisStatsAPI` will then blend these L10 series with season baselines to
update the *_l10 and *_std fields consumed by the Monte Carlo engine.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TENNIS_DIR = Path(__file__).parent.parent
DATA_DIR = TENNIS_DIR / "data"
STATS_CACHE_DIR = TENNIS_DIR / "stats_cache"
L10_PATCH_DIR = STATS_CACHE_DIR / "l10_patches"


def load_matches_for_year(year: int, tours: List[str]) -> List[dict]:
    """Load Sackmann matches (ATP/WTA) for a given year.

    Mirrors the naming convention used by `fetch_sackmann_data.py`.
    """

    matches: List[dict] = []

    for tour in tours:
        filename = f"{tour.lower()}_matches_{year}.csv"
        csv_path = DATA_DIR / filename

        if not csv_path.exists():
            # Fallback to raw/ directory if present
            alt_path = DATA_DIR / "raw" / filename
            if alt_path.exists():
                csv_path = alt_path
            else:
                print(f"[WARN] {filename} not found in data/ or data/raw/")
                continue

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    matches.append(row)
        except Exception as e:
            print(f"[WARN] Error reading {csv_path}: {e}")

    return matches


def _parse_set_games(token: str) -> Optional[Tuple[int, int, bool]]:
    """Parse a single set token like '7-6(5)' or '6-4' into (g1, g2, has_tb).

    g1 = games for the match winner in this row
    g2 = games for the match loser in this row
    has_tb = True if the set contained a tiebreak.
    """

    token = token.strip()
    if not token or token in {"RET", "W/O", "W/O", "Walkover"}:
        return None

    # Strip any trailing retirement markers
    for marker in ("RET", "ret"):
        if token.endswith(marker):
            token = token[: -len(marker)].strip()

    # Basic pattern: \d-\d with optional tiebreak in parentheses
    # Examples: '7-6(5)', '6-4', '10-8'
    try:
        core = token.split("(", 1)[0]
        parts = core.split("-")
        if len(parts) != 2:
            return None
        g1 = int(parts[0])
        g2 = int(parts[1])
        has_tb = "(" in token
        return g1, g2, has_tb
    except Exception:
        return None


def extract_match_metrics_for_player(player: str, match: dict) -> Optional[dict]:
    """Extract per-match metrics for a given player from one match row.

    Returns a dict with numeric values or None if the player is not involved
    or the score is unusable (RET/W/O without clear games).
    """

    player_lower = player.lower()
    winner = (match.get("winner_name", "") or "").lower()
    loser = (match.get("loser_name", "") or "").lower()

    if player_lower in winner:
        orient = "winner"
    elif player_lower in loser:
        orient = "loser"
    else:
        return None

    score = (match.get("score", "") or "").strip()
    if not score or "RET" in score.upper() or "W/O" in score.upper():
        # Skip retirements / walkovers for L10 form
        return None

    # Parse set-level games
    games_for = 0
    total_games = 0
    sets_won = 0
    sets_played = 0
    tiebreakers = 0

    for token in score.split():
        parsed = _parse_set_games(token)
        if not parsed:
            continue
        g1, g2, has_tb = parsed
        sets_played += 1

        if orient == "winner":
            games_for += g1
            total_games += g1 + g2
            if g1 > g2:
                sets_won += 1
        else:
            games_for += g2
            total_games += g1 + g2
            if g2 > g1:
                sets_won += 1

        if has_tb:
            tiebreakers += 1

    if sets_played == 0:
        return None

    # Aces / double faults from Sackmann fields
    if orient == "winner":
        aces = int(match.get("w_ace", 0) or 0)
        double_faults = int(match.get("w_df", 0) or 0)
    else:
        aces = int(match.get("l_ace", 0) or 0)
        double_faults = int(match.get("l_df", 0) or 0)

    surface = (match.get("surface", "Hard") or "Hard").upper()
    tourney_date = match.get("tourney_date", "00000000")

    return {
        "aces": aces,
        "double_faults": double_faults,
        "games_won": games_for,
        "total_games": total_games,
        "sets_won": sets_won,
        "sets_played": sets_played,
        "tiebreakers": tiebreakers,
        "surface": surface,
        "tourney_date": tourney_date,
    }


def compute_player_series(
    player: str,
    matches: List[dict],
    window: int = 10,
    surface_filter: Optional[str] = None,
) -> Optional[dict]:
    """Compute per-metric L10 series for a player.

    Returns a dict ready to be written as an L10 patch or None if not enough
    matches are available.
    """

    # Collect all matches involving this player
    player_matches: List[dict] = []
    player_lower = player.lower()

    for m in matches:
        winner = (m.get("winner_name", "") or "").lower()
        loser = (m.get("loser_name", "") or "").lower()
        if player_lower in winner or player_lower in loser:
            if surface_filter:
                surf = (m.get("surface", "Hard") or "Hard").upper()
                if surf != surface_filter.upper():
                    continue
            player_matches.append(m)

    # Sort by date DESC (most recent first)
    player_matches.sort(key=lambda x: x.get("tourney_date", "00000000"), reverse=True)

    series = defaultdict(list)
    dates_used: List[str] = []

    for m in player_matches:
        metrics = extract_match_metrics_for_player(player, m)
        if not metrics:
            continue

        for k in ("aces", "double_faults", "games_won", "total_games", "sets_won", "sets_played", "tiebreakers"):
            series[k].append(metrics[k])
        dates_used.append(metrics["tourney_date"])

        if len(dates_used) >= window:
            break

    if len(dates_used) == 0:
        return None

    patch = {
        "player": player,
        "surface": surface_filter.upper() if surface_filter else "ALL",
        "matches_used": len(dates_used),
        "last_match_date": max(dates_used),
        "metrics": {k: v for k, v in series.items()},
    }

    return patch


def generate_patches(
    matches: List[dict],
    window: int = 10,
    surface: Optional[str] = None,
    min_matches: int = 3,
) -> Dict[str, dict]:
    """Generate L10 patches for all players present in the match list."""

    players: set[str] = set()
    for m in matches:
        w = m.get("winner_name", "") or ""
        l = m.get("loser_name", "") or ""
        if w:
            players.add(w)
        if l:
            players.add(l)

    patches: Dict[str, dict] = {}

    for player in sorted(players):
        patch = compute_player_series(player, matches, window=window, surface_filter=surface)
        if not patch:
            continue
        if patch["matches_used"] < min_matches:
            continue
        patches[player] = patch

    return patches


def write_patches(patches: Dict[str, dict], dry_run: bool = False) -> None:
    """Write per-player patches to `stats_cache/l10_patches`.

    Respects `dry_run` to only print a summary without touching disk.
    """

    L10_PATCH_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n[SUMMARY] Generated patches for {len(patches)} players")

    if dry_run:
        sample = list(patches.items())[:5]
        print("\n[DRY-RUN] Sample patches:")
        for player, patch in sample:
            print(f"\n{player} — matches_used={patch['matches_used']}, last_date={patch['last_match_date']}")
            for k, v in patch["metrics"].items():
                print(f"  {k}: {v}")
        print("\n[DRY-RUN] No files written. Remove --dry-run to apply.")
        return

    for player, patch in patches.items():
        key = player.replace(" ", "_")
        path = L10_PATCH_DIR / f"{key}.json"
        try:
            path.write_text(json.dumps(patch, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] Failed to write patch for {player}: {e}")

    print(f"\n[✓] Wrote patches to {L10_PATCH_DIR}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate L10 form patches from Sackmann data")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Year to analyze (default: current year)")
    parser.add_argument("--window", type=int, default=10, help="Rolling window size (default: 10)")
    parser.add_argument("--surface", type=str, default=None, help="Surface filter (HARD/CLAY/GRASS/INDOOR)")
    parser.add_argument("--tour", type=str, default="both", choices=["atp", "wta", "both"], help="Tours to include")
    parser.add_argument("--min-matches", type=int, default=3, help="Minimum matches required to generate a patch")
    parser.add_argument("--dry-run", action="store_true", help="Preview patches without writing files")

    args = parser.parse_args()

    tours: List[str]
    if args.tour == "both":
        tours = ["atp", "wta"]
    else:
        tours = [args.tour]

    print("\n=== GENERATE L10 PATCHES (SACKMANN) ===")
    print(f"Year: {args.year}")
    print(f"Window: L{args.window}")
    print(f"Tours: {', '.join(t.upper() for t in tours)}")
    print(f"Surface: {args.surface or 'ALL'}")

    matches = load_matches_for_year(args.year, tours)
    print(f"\n[LOAD] Matches loaded: {len(matches)}")

    if not matches:
        print("[ERROR] No matches found. Run fetch_sackmann_data.py first.")
        return 1

    patches = generate_patches(
        matches,
        window=args.window,
        surface=args.surface,
        min_matches=args.min_matches,
    )

    write_patches(patches, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
