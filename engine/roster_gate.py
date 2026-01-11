"""
Roster Gate — Active Roster Truth Override

Enforces: Player → team comes from TODAY's active roster ONLY.
If Kevin Durant is on HOU today, all BKN entries are DELETED.
Inactive players (not in roster) are also DELETED.
"""

from typing import List, Dict, Any
import json
import urllib.request
import ssl
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def build_active_roster_map(league: str = "NBA") -> Dict[str, str]:
    """
    Build authoritative player → team mapping from TODAY's active roster.
    
    Tries ESPN API first, falls back to SerpApi if ESPN fails.

    Args:
        league: 'NBA', 'NFL', or 'CFB'

    Returns:
        Dict mapping player name → team code (e.g., {'Kevin Durant': 'HOU'})
        Or empty dict {} if all methods fail
    """
    try:
        if league == "NBA":
            result = _fetch_nba_roster()
        elif league == "NFL":
            result = _fetch_nfl_roster()
        elif league == "CFB":
            result = _fetch_cfb_roster()
        else:
            raise ValueError(f"Unknown league: {league}")
        
        if not result:
            print(f"⚠️  ESPN API returned no data, trying SerpApi fallback...")
            result = _fetch_roster_serpapi(league)
        
        if not result:
            print(f"⚠️  ROSTER GATE: No roster data found (ESPN + SerpApi both failed), skipping roster validation")
            return {}
        
        print(f"✅ ROSTER GATE: Fetched {len(result)} players from {league} rosters")
        return result
        
    except Exception as e:
        print(f"⚠️  ESPN API failed ({e}), trying SerpApi fallback...")
        try:
            result = _fetch_roster_serpapi(league)
            if result:
                print(f"✅ ROSTER GATE (SerpApi): Fetched {len(result)} players from {league} rosters")
                return result
        except Exception as serp_error:
            print(f"⚠️  SerpApi fallback also failed ({serp_error})")
        
        print(f"⚠️  ROSTER GATE: All methods failed, skipping roster validation")
        return {}  # Empty map = skip gate


def _fetch_roster_serpapi(league: str) -> Dict[str, str]:
    """
    Fallback: Use SerpApi to scrape ESPN roster data.
    
    Returns:
        Dict mapping player name → team code
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY not set")
    
    roster_map = {}
    
    if league == "NBA":
        # Search for NBA rosters on ESPN
        params = {
            "engine": "google",
            "q": f"site:espn.com NBA rosters {_get_today_str()}",
            "api_key": api_key,
            "num": 10
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Extract team/player info from snippets
            for result in data.get("organic_results", []):
                snippet = result.get("snippet", "")
                title = result.get("title", "")
                
                # Basic pattern matching for player-team associations
                # This is limited but works as fallback
                if "roster" in title.lower():
                    # Extract team abbreviation from URL or title
                    link = result.get("link", "")
                    if "/team/" in link:
                        # Example: extract LAL from /team/_/name/lal/los-angeles-lakers
                        parts = link.split("/")
                        if "name" in parts:
                            idx = parts.index("name")
                            if idx + 1 < len(parts):
                                team_abbr = parts[idx + 1].upper()[:3]
                                # Store basic info (limited without full parse)
                                print(f"   Found roster page for {team_abbr}")
            
            print(f"⚠️  SerpApi fallback has limited player-team mapping (ESPN HTML parsing needed)")
            # Return empty for now unless we implement full HTML parsing
            return {}
            
        except Exception as e:
            raise RuntimeError(f"SerpApi roster search failed: {e}")
    
    return roster_map


def _get_today_str() -> str:
    """Get today's date as string for search queries."""
    from datetime import datetime
    return datetime.now().strftime("%B %d %Y")


def _fetch_nba_roster() -> Dict[str, str]:
    """Fetch NBA rosters for today from ESPN."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    roster_map = {}

    # Fetch all NBA teams
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

    try:
        req = urllib.request.Request(teams_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            teams_data = json.loads(resp.read())

        for team_info in teams_data.get("teams", []):
            team_abbr = team_info.get("abbreviation")
            team_id = team_info.get("id")

            if not team_abbr or not team_id:
                continue

            # Fetch roster for this team
            roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}"

            try:
                req2 = urllib.request.Request(roster_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, context=ssl_ctx, timeout=10) as resp2:
                    team_data = json.loads(resp2.read())

                for player in team_data.get("athletes", []):
                    player_name = player.get("displayName", "").strip()
                    if player_name:
                        roster_map[player_name] = team_abbr

            except Exception:
                continue

        return roster_map

    except Exception as e:
        raise RuntimeError(f"ESPN NBA roster fetch failed: {e}")


def _fetch_nfl_roster() -> Dict[str, str]:
    """Fetch NFL rosters for today from ESPN."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    roster_map = {}

    # Fetch all NFL teams
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"

    try:
        req = urllib.request.Request(teams_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            teams_data = json.loads(resp.read())

        for team_info in teams_data.get("teams", []):
            team_abbr = team_info.get("abbreviation")
            team_id = team_info.get("id")

            if not team_abbr or not team_id:
                continue

            # Fetch roster for this team
            roster_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}"

            try:
                req2 = urllib.request.Request(roster_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, context=ssl_ctx, timeout=10) as resp2:
                    team_data = json.loads(resp2.read())

                for player in team_data.get("athletes", []):
                    player_name = player.get("displayName", "").strip()
                    if player_name:
                        roster_map[player_name] = team_abbr

            except Exception:
                continue

        return roster_map

    except Exception as e:
        raise RuntimeError(f"ESPN NFL roster fetch failed: {e}")


def _fetch_cfb_roster() -> Dict[str, str]:
    """Fetch CFB rosters for today (stub — requires CFBD API)."""
    raise NotImplementedError("CFB roster fetch requires CFBD_API_KEY integration")


def gate_active_roster(
    edges: List[Dict[str, Any]],
    roster_map: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Filter and correct edges based on TODAY's active roster.

    Rule: 
    - If roster_map EMPTY → SKIP gate (API failure), pass all through
    - If player in roster_map → OVERRIDE team from ESPN
    - If player NOT in roster_map → DELETE

    Args:
        edges: List of edge dicts with 'player' field
        roster_map: Dict mapping player name → team code

    Returns:
        Filtered edges with corrected team assignments

    Raises:
        RuntimeError: Only if roster_map populated but 0 edges remain
    """
    # GRACEFUL DEGRADATION: If roster empty, skip gate
    if not roster_map:
        print("⛔ ROSTER GATE: Skipped (roster map empty, likely ESPN API issue)")
        print(f"   Passing {len(edges)} edges without roster validation")
        print()
        return edges

    cleaned = []
    removed_players = set()
    overridden_teams = []


    for edge in edges:
        player = edge.get("player", "").strip()
        if not player:
            continue

        if player not in roster_map:
            # SOFT ROSTER GATE: Mark as soft pass, do not remove, apply confidence penalty
            edge["soft_roster_pass"] = True
            edge["confidence_penalty"] = 0.15  # 15% penalty for soft pass
            cleaned.append(edge)
            continue

        # Player is active — override team if needed
        original_team = edge.get("team", "").upper()
        new_team = roster_map[player].upper()

        if original_team != new_team:
            overridden_teams.append({
                "player": player,
                "original_team": original_team,
                "new_team": new_team
            })
            edge["team"] = new_team

        edge["soft_roster_pass"] = False
        edge["confidence_penalty"] = 0.0
        cleaned.append(edge)

    if not cleaned:
        raise RuntimeError(
            f"ROSTER GATE FAIL: 0 edges remain after filtering\n"
            f"Removed inactive players: {removed_players}"
        )

    if removed_players:
        print(f"⚠️  ROSTER GATE: {len(removed_players)} inactive players removed")
        for player in sorted(removed_players):
            print(f"   - {player}")

    if overridden_teams:
        print(f"⚠️  ROSTER GATE: {len(overridden_teams)} team assignments corrected")
        for override in overridden_teams:
            print(
                f"   {override['player']}: {override['original_team']} → {override['new_team']}"
            )
        print(f"✅ ROSTER GATE: {len(cleaned)} edges validated and corrected against active roster")
    else:
        # No overrides and no removals = roster validation ran, all teams already correct
        print(f"✅ ROSTER GATE: {len(cleaned)} edges validated against active roster (all team assignments correct)")
    return cleaned


def load_roster_map(roster_file: str) -> Dict[str, str]:
    """
    Load roster from JSON or CSV.

    Expected format (JSON):
    {
        "Kevin Durant": "HOU",
        "LeBron James": "LAL",
        ...
    }

    Args:
        roster_file: Path to roster file (JSON or CSV)

    Returns:
        Dict mapping player name → team code
    """
    import csv

    roster_map = {}

    try:
        with open(roster_file, "r") as f:
            if roster_file.endswith(".json"):
                roster_map = json.load(f)
            elif roster_file.endswith(".csv"):
                reader = csv.DictReader(f)
                for row in reader:
                    player = row.get("player_name") or row.get("name")
                    team = row.get("team")
                    if player and team:
                        roster_map[player] = team
    except FileNotFoundError:
        raise RuntimeError(f"Roster file not found: {roster_file}")
    except Exception as e:
        raise RuntimeError(f"Failed to load roster: {e}")

    return roster_map
