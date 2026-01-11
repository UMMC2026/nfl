"""
Schedule Gate — Hard Truth Gate for Today's Games

Enforces: If a game is not in today's official schedule → DELETE IT
"""

from typing import List, Dict, Any, Set, Tuple
from datetime import date, datetime


def get_today_games_from_espn(league: str = "NBA") -> List[Dict[str, str]]:
    """
    Fetch today's official schedule from ESPN API.

    Args:
        league: 'NBA', 'NFL', or 'CFB'

    Returns:
        List of dicts: [{"home": "LAL", "away": "BOS", "game_id": "...", ...}, ...]

    Raises:
        RuntimeError: If ESPN API fails or no games found
    """
    try:
        if league == "NBA":
            return _fetch_nba_today()
        elif league == "NFL":
            return _fetch_nfl_today()
        elif league == "CFB":
            return _fetch_cfb_today()
        else:
            raise ValueError(f"Unknown league: {league}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {league} schedule: {e}")


def _fetch_nba_today() -> List[Dict[str, str]]:
    """Fetch NBA schedule for today from ESPN."""
    import json
    import urllib.request
    import ssl
    from datetime import datetime

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())

        games = []
        for event in data.get("events", []):
            comp = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            
            home = ""
            away = ""
            for team in competitors:
                abbr = team.get("team", {}).get("abbreviation", "")
                if team.get("homeAway") == "home":
                    home = abbr
                else:
                    away = abbr
            
            if home and away:
                game_id = event.get("id", "")
                games.append({"home": home, "away": away, "game_id": game_id})

        return games
    except Exception as e:
        raise RuntimeError(f"ESPN NBA fetch failed: {e}")


def _fetch_nfl_today() -> List[Dict[str, str]]:
    """Fetch NFL schedule for today from ESPN."""
    import json
    import urllib.request
    import ssl
    from datetime import datetime

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={today}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())

        games = []
        for event in data.get("events", []):
            comp = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            
            home = ""
            away = ""
            for team in competitors:
                abbr = team.get("team", {}).get("abbreviation", "")
                if team.get("homeAway") == "home":
                    home = abbr
                else:
                    away = abbr
            
            if home and away:
                game_id = event.get("id", "")
                games.append({"home": home, "away": away, "game_id": game_id})

        return games
    except Exception as e:
        raise RuntimeError(f"ESPN NFL fetch failed: {e}")


def _fetch_cfb_today() -> List[Dict[str, str]]:
    """Fetch CFB schedule for today from ESPN."""
    import json
    import urllib.request
    import ssl
    from datetime import datetime

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates={today}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())

        games = []
        for event in data.get("events", []):
            home = event["competitions"][0]["home"]["team"]["name"]
            away = event["competitions"][0]["away"]["team"]["name"]
            game_id = event["id"]
            games.append({"home": home, "away": away, "game_id": game_id})

        return games
    except Exception as e:
        raise RuntimeError(f"ESPN CFB fetch failed: {e}")


def gate_today_games(
    edges: List[Dict[str, Any]],
    today_games: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Filter edges to ONLY teams that are playing today.
    
    CRITICAL: Also CORRECTS game_id from ESPN (don't trust normalization).
    Normalization may use wrong date; ESPN gives TRUE today's game_id.

    Args:
        edges: List of edge dicts with 'team' field (opponent optional)
        today_games: List of game dicts with 'home', 'away', and 'game_id' fields

    Returns:
        Filtered edges with CORRECTED game_id from ESPN

    Raises:
        RuntimeError: If no edges remain after filtering
    """
    if not today_games:
        raise RuntimeError("No games in today's schedule")

    # Build set of teams playing today AND map each team to their opponent + game_id
    teams_playing = set()
    team_opponent_map = {}  # {team: (opponent, espn_game_id)}
    
    for game in today_games:
        home = game.get("home", "").upper()
        away = game.get("away", "").upper()
        espn_game_id = game.get("game_id", "")
        
        teams_playing.add(home)
        teams_playing.add(away)
        
        team_opponent_map[home] = (away, espn_game_id)
        team_opponent_map[away] = (home, espn_game_id)

    print(f"⛔ SCHEDULE GATE: {len(today_games)} games on ESPN today")
    print(f"   Teams playing: {sorted(teams_playing)}")
    print()

    filtered = []
    dropped_games = set()
    game_id_corrections = 0

    for edge in edges:
        team = edge.get("team", "").upper()

        # Check if this team is playing today
        if team not in teams_playing:
            dropped_games.add(team)
            continue

        # ⚠️  CRITICAL FIX: Override game_id + opponent with ESPN's TRUE game_id for today
        opponent, espn_game_id = team_opponent_map[team]
        
        old_game_id = edge.get("game_id", "")
        if old_game_id != espn_game_id:
            edge["game_id"] = espn_game_id
            game_id_corrections += 1
            
            # Set opponent if missing
            if not edge.get("opponent"):
                edge["opponent"] = opponent
            else:
                # Update if wrong
                edge["opponent"] = opponent
        
        # Also fix edge_key and edge_id (they reference game_id)
        player = edge.get("player", "UNKNOWN_PLAYER")
        stat = edge.get("stat", "UNKNOWN_STAT")
        direction = edge.get("direction", "UNKNOWN")
        line = str(edge.get("line", "X")).replace(".", "_")
        
        edge["edge_key"] = f"{espn_game_id}_{player}_{stat}_{direction}".upper().replace(" ", "_")
        edge["edge_id"] = f"{edge['edge_key']}_LINE_{line}"
        
        filtered.append(edge)

    if not filtered:
        raise RuntimeError(
            f"SCHEDULE GATE FAIL: 0 edges match today's games\n"
            f"Dropped teams: {dropped_games}\n"
            f"Today's teams: {sorted(teams_playing)}"
        )

    if dropped_games:
        print(f"⚠️  SCHEDULE GATE: Dropped {len(dropped_games)} teams not playing today")
        for team in sorted(dropped_games):
            print(f"   - {team}")

    print(f"✅ SCHEDULE GATE: {len(filtered)} edges for {len(set(e.get('team') for e in filtered))} teams playing today")
    if game_id_corrections > 0:
        print(f"   🔄 Corrected {game_id_corrections} game_id + edge_key/edge_id from ESPN")
    print()
    
    return filtered
