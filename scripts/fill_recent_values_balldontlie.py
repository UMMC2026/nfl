import json
import requests
import time

PICKS_FILE = "scripts/props_orl_tor_cle_sas_lar_atl.json"
OUTPUT_FILE = "scripts/props_orl_tor_cle_sas_lar_atl_filled.json"
NUM_GAMES = 8
BALLEDONTLIE_PLAYER_SEARCH = "https://www.balldontlie.io/api/v1/players?search={name}"
BALLEDONTLIE_STATS = "https://www.balldontlie.io/api/v1/stats?player_ids[]={player_id}&per_page={num_games}"

STAT_MAP = {
    "Points": "pts",
    "Rebounds": "reb",
    "Assists": "ast",
    "Pts+Rebs+Asts": None,  # Special handling
}

def get_player_id(name):
    resp = requests.get(BALLEDONTLIE_PLAYER_SEARCH.format(name=name.replace(" ", "+")))
    data = resp.json()
    if data["data"]:
        return data["data"][0]["id"]
    return None

def get_recent_stat(player_id, stat, num_games=8):
    resp = requests.get(BALLEDONTLIE_STATS.format(player_id=player_id, num_games=num_games))
    data = resp.json()
    games = data.get("data", [])
    if not games:
        return []
    if stat == "Pts+Rebs+Asts":
        return [g["pts"] + g["reb"] + g["ast"] for g in games]
    stat_key = STAT_MAP.get(stat, None)
    if stat_key:
        return [g[stat_key] for g in games]
    return []

def main():
    with open(PICKS_FILE, "r") as f:
        picks = json.load(f)
    for pick in picks:
        league = pick.get("league", "NBA")
        if league != "NBA":
            continue  # Only NBA for this script
        player = pick["player"]
        stat = pick["stat"]
        player_id = get_player_id(player)
        if not player_id:
            print(f"Player not found: {player}")
            continue
        values = get_recent_stat(player_id, stat, NUM_GAMES)
        if values:
            pick["recent_values"] = values
        else:
            print(f"No recent values for {player} {stat}")
        time.sleep(0.5)  # Be nice to the API
    with open(OUTPUT_FILE, "w") as f:
        json.dump(picks, f, indent=2)
    print(f"Filled picks saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
