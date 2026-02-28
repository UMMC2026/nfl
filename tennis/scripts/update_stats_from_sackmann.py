"""
Update player_stats.json with rolling windows from Sackmann data.
Computes L10 (last 10 matches) stats for accuracy boost.

Usage:
    python tennis/scripts/update_stats_from_sackmann.py
    python tennis/scripts/update_stats_from_sackmann.py --window 15
    python tennis/scripts/update_stats_from_sackmann.py --dry-run
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TENNIS_DIR = Path(__file__).parent.parent
DATA_DIR = TENNIS_DIR / "data"


def load_sackmann_matches(tour: str, year: int) -> List[dict]:
    """Load matches from Sackmann CSV (main tour + ITF/Qual/Chall)."""
    matches = []
    
    # Main tour file
    filename = f"{tour.lower()}_matches_{year}.csv"
    csv_path = DATA_DIR / filename
    
    if not csv_path.exists():
        # Try raw directory
        csv_path = DATA_DIR / "raw" / filename
    
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                matches.append(row)
    else:
        print(f"[WARN] {filename} not found. Run fetch_sackmann_data.py first.")
    
    # Also load ITF/Qualifier data if available (for lower-ranked players)
    itf_patterns = [
        f"{tour.lower()}_matches_qual_itf_{year}.csv",
        f"{tour.lower()}_matches_qual_chall_{year}.csv",
        f"{tour.lower()}_matches_futures_{year}.csv",
    ]
    
    for pattern in itf_patterns:
        itf_path = DATA_DIR / "raw" / pattern
        if itf_path.exists():
            try:
                with open(itf_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    itf_count = 0
                    for row in reader:
                        matches.append(row)
                        itf_count += 1
                    if itf_count > 0:
                        print(f"       + {itf_count:,} ITF/Qual matches from {pattern}")
            except Exception as e:
                print(f"[WARN] Error loading {pattern}: {e}")
    
    return matches


def compute_player_L10_stats(player_name: str, matches: List[dict], window: int = 10) -> dict:
    """
    Compute rolling window stats for a player.
    
    Returns dict with:
    - ace_pct_L10
    - first_serve_pct_L10
    - hold_pct_L10
    - straight_set_pct_L10
    - surface_form_L10 (win %)
    """
    # Find all matches for this player
    player_matches = []
    for m in matches:
        winner = m.get("winner_name", "").lower()
        loser = m.get("loser_name", "").lower()
        
        if player_name.lower() in winner or player_name.lower() in loser:
            player_matches.append(m)
    
    # Sort by date (most recent first)
    player_matches.sort(key=lambda x: x.get("tourney_date", "20260101"), reverse=True)
    
    # Take last N matches
    recent = player_matches[:window]
    
    if len(recent) < 3:
        return {}  # Not enough data
    
    stats = {
        "matches_analyzed": len(recent),
        "last_match_date": recent[0].get("tourney_date") if recent else None,
    }
    
    # Ace % (aces per service point)
    total_aces = 0
    total_svpt = 0
    
    # First serve %
    total_1st_in = 0
    total_1st_att = 0
    
    # Win rate
    wins = 0
    
    # Surface-specific tracking
    surface_wins = defaultdict(int)
    surface_matches = defaultdict(int)
    
    for m in recent:
        is_winner = player_name.lower() in m.get("winner_name", "").lower()
        surface = m.get("surface", "Hard").upper()
        
        if is_winner:
            wins += 1
            aces = int(m.get("w_ace", 0) or 0)
            svpt = int(m.get("w_svpt", 0) or 0)
            first_in = int(m.get("w_1stIn", 0) or 0)
            first_att = int(m.get("w_1stWon", 0) or 0) + int(m.get("w_1stIn", 0) or 0)
            surface_wins[surface] += 1
        else:
            aces = int(m.get("l_ace", 0) or 0)
            svpt = int(m.get("l_svpt", 0) or 0)
            first_in = int(m.get("l_1stIn", 0) or 0)
            first_att = int(m.get("l_1stWon", 0) or 0) + int(m.get("l_1stIn", 0) or 0)
        
        surface_matches[surface] += 1
        total_aces += aces
        total_svpt += svpt
        total_1st_in += first_in
        total_1st_att += first_att
    
    # Calculate percentages
    if total_svpt > 0:
        stats["ace_pct_L10"] = round(total_aces / total_svpt, 4)
    
    if total_1st_att > 0:
        stats["first_serve_pct_L10"] = round(total_1st_in / total_1st_att, 4)
    
    stats["win_pct_L10"] = round(wins / len(recent), 4)
    
    # Surface-specific form
    stats["surface_form_L10"] = {}
    for surface, count in surface_matches.items():
        win_count = surface_wins[surface]
        stats["surface_form_L10"][surface] = round(win_count / count, 4)
    
    return stats


def update_player_stats_file(L10_data: Dict[str, dict], dry_run: bool = False):
    """Merge L10 stats into player_stats.json."""
    stats_file = DATA_DIR / "player_stats.json"
    
    if not stats_file.exists():
        print("[ERROR] player_stats.json not found")
        return
    
    # Load existing stats
    current = json.loads(stats_file.read_text(encoding="utf-8"))
    
    updated_count = 0
    new_count = 0
    
    for player, L10_stats in L10_data.items():
        player_key = player.lower()
        
        if player_key in current:
            # Update existing player
            current[player_key].update(L10_stats)
            current[player_key]["stats_updated"] = datetime.now().isoformat()
            updated_count += 1
        else:
            # Add new player (minimal record)
            current[player_key] = {
                "name": player,
                "tour": "ATP",  # Default, can be refined
                **L10_stats,
                "stats_updated": datetime.now().isoformat(),
            }
            new_count += 1
    
    print(f"\n[SUMMARY] Updated: {updated_count} | New: {new_count}")
    
    if dry_run:
        print("\n[DRY-RUN] Changes not saved. Remove --dry-run to apply.")
        # Show sample
        sample = list(L10_data.items())[:3]
        for player, stats in sample:
            print(f"\n{player}:")
            for k, v in stats.items():
                print(f"  {k}: {v}")
    else:
        # Save
        stats_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[✓] Saved to {stats_file}")


def main():
    parser = argparse.ArgumentParser(description="Update player stats from Sackmann data")
    parser.add_argument("--window", type=int, default=10, help="Rolling window size (default: 10)")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Year to analyze")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    
    args = parser.parse_args()
    
    print("\n=== PLAYER STATS UPDATER ===")
    print(f"Window: L{args.window}")
    print(f"Year: {args.year}\n")
    
    # Load matches
    print("[LOAD] ATP matches...")
    atp_matches = load_sackmann_matches("atp", args.year)
    print(f"       {len(atp_matches)} matches")
    
    print("[LOAD] WTA matches...")
    wta_matches = load_sackmann_matches("wta", args.year)
    print(f"       {len(wta_matches)} matches")
    
    all_matches = atp_matches + wta_matches
    
    if not all_matches:
        print("\n[ERROR] No match data found. Run fetch_sackmann_data.py first.")
        return 1
    
    # Extract unique players
    players = set()
    for m in all_matches:
        winner = m.get("winner_name", "")
        loser = m.get("loser_name", "")
        if winner:
            players.add(winner)
        if loser:
            players.add(loser)
    
    print(f"\n[COMPUTE] Processing {len(players)} players...")
    
    L10_data = {}
    for player in sorted(players):
        stats = compute_player_L10_stats(player, all_matches, window=args.window)
        if stats:
            L10_data[player] = stats
    
    print(f"[✓] Computed L{args.window} stats for {len(L10_data)} players")
    
    # Update file
    update_player_stats_file(L10_data, dry_run=args.dry_run)
    
    return 0


if __name__ == "__main__":
    exit(main())
