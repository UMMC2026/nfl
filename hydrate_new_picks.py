#!/usr/bin/env python3
"""
Hydrate newly added picks by appending mu/sigma computed from recent game logs.

Fixes:
- Use PlayerGameLog (per-game) instead of PlayerCareerStats (per-season totals)
- Use correct pick field names ("player", not "player_name")
- Support common stats: points, rebounds, assists, 3pm, pts+reb+ast
- Record hydration meta with the index range hydrated for tonight filtering
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players


def _fetch_player_gamelog_with_retries(player_id: int, season: str = "2024-25", max_retries: int = 2, base_backoff: float = 1.0):
    """Fetch PlayerGameLog with bounded retries/backoff for flaky NBA stats API.

    Returns a DataFrame on success or None on failure (timeout/HTTP errors). Never raises.
    """

    for attempt in range(1, max_retries + 1):
        try:
            gl = playergamelog.PlayerGameLog(player_id=player_id, season=season)
            return gl.get_data_frames()[0]
        except Exception as e:
            if attempt >= max_retries:
                break
            sleep_s = base_backoff * attempt
            print(f"⚠️  Retry {attempt}/{max_retries} in {sleep_s:.1f}s", end=" ", flush=True)
            time.sleep(sleep_s)
    return None

def hydrate_new_picks():
    """Hydrate only newly added picks (append to picks_hydrated.json)."""
    
    picks_file = Path("picks.json")
    hydrated_file = Path("picks_hydrated.json")
    
    # Load all picks
    with open(picks_file) as f:
        all_picks = json.load(f)
    
    # Load existing hydrated picks (or start fresh)
    if hydrated_file.exists():
        with open(hydrated_file) as f:
            hydrated = json.load(f)
    else:
        hydrated = []
    
    print(f"📥 Loaded {len(hydrated)} existing hydrated picks")
    print(f"📥 Total picks: {len(all_picks)}")
    print(f"📊 Need to hydrate: picks {len(hydrated)+1} to {len(all_picks)}")
    
    start_index = len(hydrated)  # 0-based
    new_picks = all_picks[start_index:]
    
    for i, pick in enumerate(new_picks, start=len(hydrated)+1):
        player_name = pick.get("player") or pick.get("player_name")
        stat = pick.get("stat")
        
        print(f"\n[{i}/{len(all_picks)}] {player_name} - {stat}...", end=" ", flush=True)
        
        try:
            # Get player ID
            player_dict = nba_players.find_players_by_full_name(player_name)
            if not player_dict:
                print(f"❌ Not found")
                pick["mu"] = pick["line"]
                pick["sigma"] = 5.0
                hydrated.append(pick)
                continue
            
            player_id = player_dict[0]["id"]

            # Get current season game log and take last 10 games (with retries)
            df = _fetch_player_gamelog_with_retries(player_id=player_id, season="2024-25")
            if df is None:
                print(f"⏭️  SKIP (timeout/error)")
                pick["mu"] = pick["line"]
                pick["sigma"] = 5.0
                hydrated.append(pick)
                continue
            # Most recent games first; take last 10 by chronological order
            last_games = df.iloc[::-1].tail(10)
            
            if len(last_games) == 0:
                print(f"⚠️  No data")
                pick["mu"] = pick["line"]
                pick["sigma"] = 5.0
                hydrated.append(pick)
                continue
            
            # Calculate stat column
            if stat == "points":
                stat_col = "PTS"
            elif stat == "rebounds":
                stat_col = "REB"
            elif stat == "assists":
                stat_col = "AST"
            elif stat in ("3pm", "3PM", "fg3m"):
                stat_col = "FG3M"
            elif stat == "pts+reb+ast" or stat == "pra":
                last_games["combo"] = last_games["PTS"] + last_games["REB"] + last_games["AST"]
                stat_col = "combo"
            else:
                print(f"⚠️  Unknown stat: {stat}")
                pick["mu"] = pick["line"]
                pick["sigma"] = 5.0
                hydrated.append(pick)
                continue
            
            values = last_games[stat_col].dropna().astype(float)
            
            if len(values) == 0:
                print(f"⚠️  No values")
                pick["mu"] = pick["line"]
                pick["sigma"] = 5.0
            else:
                mu = values.mean()
                sigma = values.std(ddof=1) if len(values) > 1 else 0.0

                # Attach recency / usage metadata so downstream governance
                # can treat long-absent players more conservatively. Use the
                # game dates from the full season log, not just the 10-game
                # window, to compute days since last appearance.
                try:
                    # NBA API uses "GAME_DATE" as a string like "OCT 24, 2024".
                    # We parse the max date across the full DataFrame.
                    if "GAME_DATE" in df.columns:
                        parsed_dates = [
                            datetime.strptime(d, "%b %d, %Y")
                            for d in df["GAME_DATE"].dropna().unique()
                        ]
                        if parsed_dates:
                            last_game_date = max(parsed_dates)
                            days_since_last_game = (datetime.now(timezone.utc).date() - last_game_date.date()).days
                        else:
                            last_game_date = None
                            days_since_last_game = None
                    else:
                        last_game_date = None
                        days_since_last_game = None
                except Exception:
                    last_game_date = None
                    days_since_last_game = None

                pick["recent_values"] = [float(v) for v in values.tolist()]
                pick["mu"] = round(float(mu), 1)
                pick["sigma"] = round(float(sigma), 2)
                if days_since_last_game is not None:
                    pick["days_since_last_game"] = days_since_last_game
                print(f"✓ avg={mu:.1f}, std={sigma:.2f}, n={len(values)}")
            
            hydrated.append(pick)
            time.sleep(0.5)
        
        except Exception as e:
            # Catch anything unexpected and skip gracefully
            print(f"⏭️  SKIP ({type(e).__name__})")
            pick["mu"] = pick["line"]
            pick["sigma"] = 5.0
            hydrated.append(pick)
    
    # If nothing new was added, attempt a repair sweep for malformed entries
    if len(new_picks) == 0 and hydrated:
        print("\n🧼 No new picks detected; performing repair sweep for malformed entries...")
        fixed = 0
        for idx, pick in enumerate(hydrated):
            try:
                player_name = pick.get("player") or pick.get("player_name")
                stat = pick.get("stat")
                line = pick.get("line")
                recent = pick.get("recent_values") or []
                mu = pick.get("mu")
                # Heuristics: empty recent values OR suspiciously large mu
                suspicious_mu = isinstance(mu, (int, float)) and mu is not None and mu > 100.0 and stat in ("points","rebounds","assists","3pm","pts+reb+ast")
                if len(recent) == 0 or suspicious_mu:
                    player_dict = nba_players.find_players_by_full_name(player_name)
                    if not player_dict:
                        continue
                    df = _fetch_player_gamelog_with_retries(player_id=player_dict[0]["id"], season="2024-25")
                    last_games = df.iloc[::-1].tail(10)
                    if stat == "points":
                        stat_col = "PTS"
                    elif stat == "rebounds":
                        stat_col = "REB"
                    elif stat == "assists":
                        stat_col = "AST"
                    elif stat in ("3pm", "3PM", "fg3m"):
                        stat_col = "FG3M"
                    elif stat == "pts+reb+ast" or stat == "pra":
                        last_games["combo"] = last_games["PTS"] + last_games["REB"] + last_games["AST"]
                        stat_col = "combo"
                    else:
                        continue
                    values = last_games[stat_col].dropna().astype(float)
                    if len(values) == 0:
                        continue
                    mu2 = values.mean()
                    sigma2 = values.std(ddof=1) if len(values) > 1 else 0.0
                    hydrated[idx]["recent_values"] = [float(v) for v in values.tolist()]
                    hydrated[idx]["mu"] = round(float(mu2), 1)
                    hydrated[idx]["sigma"] = round(float(sigma2), 2)
                    fixed += 1
                    print(f"  • Repaired {player_name} {stat}: avg={mu2:.1f}, std={sigma2:.2f}")
            except Exception as e:
                print(f"  ! Repair failed for {pick.get('player')} {pick.get('stat')}: {e}")
                continue
        print(f"✓ Repair sweep complete. Fixed {fixed} entries.")

    # Save hydrated picks
    with open(hydrated_file, "w", encoding="utf-8") as f:
        json.dump(hydrated, f, indent=2)

    # Save meta for tonight filtering
    end_index = len(hydrated)
    meta = {
        "start": start_index + 1,  # 1-based inclusive
        "end": end_index,          # 1-based inclusive
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    with open(".hydration_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✓ Saved {len(hydrated)} hydrated picks to {hydrated_file}")
    print(f"✓ Wrote hydration meta: {meta}")

if __name__ == "__main__":
    hydrate_new_picks()
