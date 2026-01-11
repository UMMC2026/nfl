#!/usr/bin/env python3
"""
GAME RESULTS LOADER
===================

Fetches final game stats from ESPN and writes to game_results.json.
This is called AFTER games are FINAL and before generate_resolved_ledger.py.

Output format:
{
    "game_id": {
        "date": "2026-01-02",
        "status": "FINAL",
        "home_team": "CLE",
        "away_team": "NYK",
        "players": {
            "Darius Garland": {
                "team": "CLE",
                "points": 18,
                "rebounds": 2,
                "assists": 6,
                "pra": 26,
                "3pm": 1,
                "steals": 1,
                "blocks": 0,
                "turnovers": 2
            },
            ...
        }
    }
}

Supports NBA games only (can extend to NFL, CFB).
Uses ESPN public APIs (no authentication required).
"""

import json
import ssl
import urllib.request
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from collections import defaultdict


# SSL context for ESPN compatibility
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from URL using urllib."""
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [WARN] Fetch failed for {url}: {e}")
        return {}


def load_picks_for_games(picks_path: Path) -> Dict[str, list]:
    """Extract unique game_ids and pick details from picks.json."""
    games_needed = defaultdict(list)
    
    try:
        with open(picks_path) as f:
            picks = json.load(f)
        
        for pick in picks:
            game_id = pick.get("game_id")
            player = pick.get("player_name")
            if game_id and player:
                games_needed[game_id].append(player)
    except FileNotFoundError:
        print(f"  [WARN] {picks_path} not found")
    
    return games_needed


def fetch_game_result(game_id: str) -> Optional[Dict]:
    """
    Fetch a single NBA game result from ESPN.
    
    Args:
        game_id: ESPN game ID (e.g., "401547819")
        
    Returns:
        Dict with game info and player stats, or None if game not finalized.
    """
    # ESPN NBA game detail endpoint
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?id={game_id}"
    
    data = _fetch_json(url)
    if not data or "article" not in data:
        return None
    
    article = data.get("article", {})
    competition = article.get("competitions", [{}])[0]
    
    # Check game status
    status = competition.get("status", {}).get("type", "").lower()
    if "final" not in status:
        return None  # Game not finished
    
    # Extract game metadata
    date_str = competition.get("date", "").split("T")[0]
    home_team = competition.get("competitors", [{}])[0].get("team", {}).get("abbreviation", "")
    away_team = competition.get("competitors", [{}])[1].get("team", {}).get("abbreviation", "") if len(competition.get("competitors", [])) > 1 else ""
    
    if not (date_str and home_team and away_team):
        return None
    
    # Extract player box scores
    players_stats = {}
    
    # Get box score from article competitors
    for competitor in competition.get("competitors", []):
        team = competitor.get("team", {}).get("abbreviation", "")
        
        for player in competitor.get("players", []):
            player_name = player.get("displayName", "")
            if not player_name:
                continue
            
            # Extract stats from statistics array
            stats = {"team": team}
            for stat_group in player.get("statistics", []):
                for stat in stat_group.get("stats", []):
                    label = stat.get("label", "").lower()
                    value = stat.get("value", 0)
                    
                    # Map ESPN labels to internal schema
                    if label == "points":
                        stats["points"] = float(value)
                    elif label == "rebounds":
                        stats["rebounds"] = float(value)
                    elif label == "assists":
                        stats["assists"] = float(value)
                    elif label == "3-pointers made":
                        stats["3pm"] = float(value)
                    elif label == "steals":
                        stats["steals"] = float(value)
                    elif label == "blocks":
                        stats["blocks"] = float(value)
                    elif label == "turnovers":
                        stats["turnovers"] = float(value)
            
            # Compute PRA if we have components
            if all(k in stats for k in ["points", "rebounds", "assists"]):
                stats["pra"] = stats["points"] + stats["rebounds"] + stats["assists"]
            
            players_stats[player_name] = stats
    
    return {
        "game_id": game_id,
        "date": date_str,
        "status": "FINAL",
        "home_team": home_team,
        "away_team": away_team,
        "players": players_stats
    }


def write_results(results: Dict, output_path: Path):
    """Write game results to JSON (overwrite)."""
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)


def main():
    """Main game results pipeline."""
    print("=" * 70)
    print("GAME RESULTS LOADER")
    print("=" * 70)
    
    workspace = Path.cwd()
    picks_path = workspace / "picks.json"
    output_path = workspace / "outputs" / "game_results.json"
    
    if not picks_path.exists():
        print(f"❌ picks.json not found")
        return 1
    
    # Find games that need resolution
    print("\n🔍 Finding games needing resolution...")
    game_ids = load_picks_for_games(picks_path)
    print(f"   ✓ {len(game_ids)} unique games")
    
    # Fetch results
    print("\n📊 Fetching game results...")
    results = {}
    for game_id in sorted(game_ids):
        result = fetch_game_result(game_id)
        if result:
            results[game_id] = result
            print(f"   ✓ {game_id}")
    
    # Write output
    print(f"\n💾 Writing to {output_path}...")
    write_results(results, output_path)
    print(f"   ✓ {len(results)} games written")
    
    print("\n" + "=" * 70)
    print(f"✅ LOADED {len(results)} FINAL GAMES")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(main())
