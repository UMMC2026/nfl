import json
import requests
import time

# --- CONFIG ---
PICKS_FILE = "scripts/props_orl_tor_cle_sas_lar_atl.json"
OUTPUT_FILE = "scripts/props_orl_tor_cle_sas_lar_atl_filled.json"
NUM_GAMES = 8  # Number of recent games to fetch

# --- Simple Basketball Reference Scraper (NBA only, demo) ---
def fetch_nba_stat(player_name, stat, num_games=8):
    # This is a placeholder. For real use, use an NBA stats API or a robust scraper.
    # Here, we just return random plausible values for demonstration.
    import random
    stat_map = {
        "Points": (10, 35),
        "Rebounds": (3, 15),
        "Assists": (2, 12),
        "Pts+Rebs+Asts": (15, 50),
        "Receiving Yards": (30, 120),
        "Rush Yards": (20, 120),
        "Receptions": (1, 10),
    }
    low, high = stat_map.get(stat, (5, 30))
    return [random.randint(low, high) for _ in range(num_games)]

# --- Main ---
def main():
    with open(PICKS_FILE, "r") as f:
        picks = json.load(f)

    for pick in picks:
        stat = pick["stat"]
        player = pick["player"]
        league = pick.get("league", "NBA")
        # For demo: only NBA, random values. Replace with real API calls for production.
        if league == "NBA":
            pick["recent_values"] = fetch_nba_stat(player, stat, NUM_GAMES)
        else:
            # For NFL, you would use a different API or logic
            pick["recent_values"] = fetch_nba_stat(player, stat, NUM_GAMES)
        time.sleep(0.2)  # Be nice to APIs if using real ones

    with open(OUTPUT_FILE, "w") as f:
        json.dump(picks, f, indent=2)
    print(f"Filled picks saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
