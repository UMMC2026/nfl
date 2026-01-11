"""
Authoritative NBA roster builder (resilient).
Uses TEAM rosters with retries + cache fallback.
SOP v2.1 compliant.
"""

import json
import time
from pathlib import Path

from nba_api.stats.endpoints import commonteamroster
from nba_api.stats.static import teams


# ===================== CONFIG =====================

SEASON = "2024-25"

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "nba_roster_context.json"
OLLAMA_PROMPT_FILE = CACHE_DIR / "ollama_roster_prompt.txt"

API_TIMEOUT = 60
RATE_LIMIT_SLEEP = 0.9
MAX_RETRIES = 3
MIN_PLAYER_THRESHOLD = 400

NBA_HEADERS = {
    "Host": "stats.nba.com",
    "Connection": "keep-alive",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-token": "true",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/",
    "Accept-Language": "en-US,en;q=0.9",
}


# ===================== CORE =====================

def fetch_team_roster(team_id, team_abbrev):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            roster = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=SEASON,
                headers=NBA_HEADERS,
                timeout=API_TIMEOUT
            ).get_normalized_dict()

            players = {
                p["PLAYER"].strip().lower(): team_abbrev
                for p in roster["CommonTeamRoster"]
            }

            return players

        except Exception as e:
            print(f"⚠️ {team_abbrev} attempt {attempt}/{MAX_RETRIES} failed: {e}")
            time.sleep(2 + attempt)

    print(f"❌ {team_abbrev} skipped after retries")
    return {}


def build_nba_roster_knowledge(force_refresh=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force_refresh:
        print("📦 Loading NBA roster context from cache")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print("🏀 Fetching ACTIVE NBA TEAM ROSTERS (resilient mode)...")

    roster_kb = {}
    failed_teams = []

    for team in teams.get_teams():
        team_id = team["id"]
        team_abbrev = team["abbreviation"]

        team_players = fetch_team_roster(team_id, team_abbrev)

        if not team_players:
            failed_teams.append(team_abbrev)
        else:
            roster_kb.update(team_players)

        time.sleep(RATE_LIMIT_SLEEP)

    print(f"ℹ️ Teams failed this run: {failed_teams or 'None'}")
    print(f"ℹ️ Players collected: {len(roster_kb)}")

    if len(roster_kb) < MIN_PLAYER_THRESHOLD:
        raise RuntimeError(
            f"Roster build FAILED ({len(roster_kb)} players < {MIN_PLAYER_THRESHOLD})"
        )

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(roster_kb, f, indent=2)

    generate_ollama_roster_context(roster_kb)

    print("✅ NBA roster context READY")
    return roster_kb


# ===================== OLLAMA =====================

def generate_ollama_roster_context(roster_kb):
    lines = [
        f"AUTHORITATIVE NBA ROSTERS ({SEASON})",
        "Source: NBA TEAM ROSTERS",
        "Rules:",
        "- No inference",
        "- Team mismatch → INVALID",
        "- UNKNOWN team → INVALID",
        ""
    ]

    for player, team in sorted(roster_kb.items()):
        lines.append(f"- {player.title()}: {team}")

    with open(OLLAMA_PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_ollama_prompt_with_context(pick, roster_kb):
    player = pick["player"].lower()
    team = roster_kb.get(player, "UNKNOWN")

    return f"""
AUTHORITATIVE NBA ROSTER CHECK

Player: {player.title()}
Verified Team: {team}

Pick Team Listed: {pick.get("team")}
Stat: {pick["stat"]}
Line: {pick["mu"]}

Return JSON only:
{{"status":"VALID|INVALID","correct_team":"{team}","notes":"..."}}
"""


# ===================== CLI =====================

if __name__ == "__main__":
    roster_kb = build_nba_roster_knowledge(force_refresh=True)

    test = {
        "player": "Kevin Durant",
        "team": "PHX",
        "stat": "points",
        "mu": 26.5
    }

    print("\n" + "=" * 80)
    print("KD SANITY CHECK")
    print("=" * 80)
    print(generate_ollama_prompt_with_context(test, roster_kb))
